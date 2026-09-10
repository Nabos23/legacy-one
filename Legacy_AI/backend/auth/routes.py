import httpx
from typing import Optional
from backend.organization.schemas import OrganizationPublic
from fastapi import APIRouter, Cookie, Depends, HTTPException, status
from fastapi.responses import JSONResponse, RedirectResponse
from itsdangerous import BadSignature, SignatureExpired
from pydantic import BaseModel, EmailStr
from pymongo.errors import PyMongoError
from datetime import datetime, timezone

from backend.auth import services
from backend.auth.permissions import (
    get_effective_permissions_for_user,
    get_permissions_for_role,
    is_org_admin,
    is_super_admin,
    list_all_roles,
    list_assignable_roles,
)
from backend.auth.schemas import (
    AdminCreateUserRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    PermissionPublic,
    ResetPasswordRequest,
    SignupPassword,
    SignupRequest,
    TokenResponse,
    UserPublic,
    VerifyOtpRequest,
    RegisterRequest,
    UserApprovalRequest,
)
from backend.dependencies import get_current_admin, get_current_user, require_permission
from backend.core.config import settings
from backend.db.database import organizations_collection
from backend.core.softdelete import NOT_DELETED

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_oauth_state_cookie(response, state: str) -> None:
    response.set_cookie("login_oauth_state", state, max_age=600, httponly=True,
                        secure=not settings.BACKEND_BASE_URL.startswith("http://localhost"),
                        samesite="lax", path="/auth/oauth")


@router.get("/oauth/{provider}")
async def oauth_start(provider: str) -> RedirectResponse:
    client_id, client_secret, redirect_uri = services.oauth_provider_config(provider)
    if not client_id or not client_secret:
        raise HTTPException(status_code=503, detail=f"{provider.title()} sign-in is not configured.")
    state = services.create_oauth_state(provider)
    response = RedirectResponse(services.oauth_authorize_url(provider, client_id, redirect_uri, state))
    _set_oauth_state_cookie(response, state)
    return response


@router.post("/oauth/{provider}/link")
async def oauth_link_start(
    provider: str,
    current_user: UserPublic = Depends(get_current_user),
) -> JSONResponse:
    """Start linking `provider` to the caller's own account.

    Unlike `/oauth/{provider}`, this requires an authenticated session and
    binds the resulting identity to that exact account (see `oauth_link`) --
    it never authenticates as, or merges into, a different account. Returns
    the provider's consent URL; the frontend should navigate the browser to
    it directly rather than following a redirect from here, so the caller's
    JWT never appears in a URL sent to us or to the provider.
    """
    client_id, client_secret, redirect_uri = services.oauth_provider_config(provider)
    if not client_id or not client_secret:
        raise HTTPException(status_code=503, detail=f"{provider.title()} sign-in is not configured.")
    state = services.create_oauth_state(provider, link_user_id=current_user.id)
    response = JSONResponse({"authorize_url": services.oauth_authorize_url(provider, client_id, redirect_uri, state)})
    _set_oauth_state_cookie(response, state)
    return response


@router.get("/oauth/{provider}/callback")
async def oauth_callback(provider: str, code: str = "", state: str = "", error: str = "",
                         login_oauth_state: str | None = Cookie(default=None)) -> RedirectResponse:
    if error:
        return services.frontend_oauth_redirect(error="Sign-in was cancelled or denied.")
    try:
        state_data = services.verify_oauth_state(provider, state, login_oauth_state)
    except (BadSignature, SignatureExpired):
        return services.frontend_oauth_redirect(error="This sign-in request expired. Please try again.")

    try:
        provider_id, email, name = await services.oauth_exchange(provider, code)
        link_user_id = state_data.get("link_user_id")
        if link_user_id:
            token, user, _ids = await services.oauth_link(
                provider=provider, provider_user_id=provider_id, email=email, user_id=link_user_id
            )
        else:
            token, user, _ids = await services.oauth_authenticate(
                provider=provider, provider_user_id=provider_id, email=email, name=name
            )
        return services.frontend_oauth_redirect(access_token=token, role=user.role)
    except services.OAuthAccountExists:
        return services.frontend_oauth_redirect(
            error=(
                f"An account already exists for this email. Log in and connect "
                f"{provider.title()} from account settings instead."
            )
        )
    except services.OAuthNoAccount:
        return services.frontend_oauth_redirect(
            error="No account found for this email. Ask an admin to invite you, or sign up first."
        )
    except ValueError as exc:
        return services.frontend_oauth_redirect(error=str(exc))
    except (httpx.HTTPError, KeyError, PyMongoError):
        return services.frontend_oauth_redirect(error=f"Unable to sign in with {provider.title()}.")


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest) -> TokenResponse:
    """Self-service registration: register user under a selected organization for admin approval."""
    token, user, db_conn_ids = await services.register(
        name=payload.name,
        email=payload.email,
        password=payload.password,
        organization_id=payload.organization_id,
    )
    return TokenResponse(access_token=token, user=user, db_conn_ids=db_conn_ids)


@router.get("/organizations", response_model=list[OrganizationPublic])
async def list_organizations_public() -> list[OrganizationPublic]:
    """Retrieve all non-deleted organizations for self-service signup selection."""
    cursor = organizations_collection.find(NOT_DELETED).sort("name", 1)
    docs = await cursor.to_list(length=1000)
    return [
        OrganizationPublic(
            id=str(doc["_id"]),
            name=doc["name"],
            description=doc.get("description"),
            created_by=doc.get("created_by"),
            created_at=doc.get("created_at") or datetime.now(timezone.utc),
            updated_at=doc.get("updated_at"),
        )
        for doc in docs
    ]


@router.post("/logout", response_model=MessageResponse)
async def logout() -> MessageResponse:
    """Stateless logout — client should discard the token."""
    return MessageResponse(message="Logged out successfully.")


@router.post("/users", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: SignupRequest,
    admin: UserPublic = Depends(get_current_admin),
) -> TokenResponse:
    """Create a new user against an organization and return a JWT.

    Requires a valid Bearer JWT whose role carries the ``create_user`` permission.
    """
    token, user, db_conn_ids = await services.create_user(payload, admin)
    return TokenResponse(access_token=token, user=user, db_conn_ids=db_conn_ids)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest) -> TokenResponse:
    """Authenticate an existing user and return a JWT."""
    token, user, db_conn_ids = await services.login(payload)
    return TokenResponse(access_token=token, user=user, db_conn_ids=db_conn_ids)

@router.post("/admin/users", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def create_user_as_admin(
    payload: AdminCreateUserRequest,
    admin: UserPublic = Depends(get_current_admin),
) -> UserPublic:
    """Admin-only: create a user in an organization. Returns no token.
    """
    org_id = (
        payload.organization_id or admin.organization_id
        if is_super_admin(admin.role)
        else admin.organization_id
    )
    return await services.create_user_as_admin(
        payload, organization_id=org_id, admin=admin
    )


@router.post("/approval", response_model=UserPublic)
async def update_user_approval(
    payload: UserApprovalRequest,
    admin: UserPublic = Depends(get_current_admin),
) -> UserPublic:
    """Admin endpoint to approve or disapprove a user's organization registration request."""
    return await services.update_user_approval_status(
        admin=admin, target_user_id=payload.user_id, new_status=payload.status
    )


@router.get("/pending-approvals", response_model=list[UserPublic])
async def list_pending_approvals(
    admin: UserPublic = Depends(get_current_admin),
) -> list[UserPublic]:
    """Admin endpoint to retrieve users pending registration approval in their organization."""
    return await services.list_pending_approvals(admin)


@router.get("/me", response_model=UserPublic)
async def me(current_user: UserPublic = Depends(get_current_user)) -> UserPublic:
    """Return the currently authenticated user."""
    return current_user


@router.get("/roles")
async def list_roles(admin: UserPublic = Depends(get_current_admin)) -> list[dict]:
    """Roles the caller may assign to a new user, resolved from the DB.

    Backs the Create User role picker: new roles or permission changes made
    in the role_permissions collection / /admin panel are reflected here
    immediately with no client-side change needed.
    """
    return await list_assignable_roles(admin)


@router.get("/roles/all")
async def list_roles_all(current_user: UserPublic = Depends(get_current_user)) -> list[dict]:
    """Every DB-defined role's name/label/is_admin, unfiltered by assignability.

    For display purposes only (e.g. badging a user's role as admin-tier in a
    user list), where the viewer may not have permission to assign every role
    that could appear in that list.
    """
    return await list_all_roles()


@router.get("/me/permissions")
async def me_permissions(current_user: UserPublic = Depends(get_current_user)) -> dict:
    """Debug: return the current user's role and effective resolved permissions (including team permissions)."""
    perms = await get_effective_permissions_for_user(current_user)
    return {
        "user_id": current_user.id,
        "role_stored": current_user.role,
        "is_super_admin": is_super_admin(current_user.role),
        "is_org_admin": is_org_admin(current_user.role),
        "resolved_permissions": perms,
    }


@router.get("/permissions", response_model=list[PermissionPublic])
async def list_permissions(
    current_user: UserPublic = Depends(require_permission("view_role_permissions")),
) -> list[PermissionPublic]:
    """The full permission catalog available for org-level role customization
    (excludes permissions that can never be granted via an org override)."""
    return await services.list_permission_catalog()


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(payload: ForgotPasswordRequest) -> MessageResponse:
    """Request a password-reset OTP. Always returns a generic message."""
    otp = await services.forgot_password(payload)
    return MessageResponse(
        message="If the email exists, an OTP has been sent.",
        otp=otp if settings.OTP_RETURN_IN_RESPONSE else None,
    )


@router.post("/verify-otp", response_model=MessageResponse)
async def verify_otp(payload: VerifyOtpRequest) -> MessageResponse:
    """Verify a password-reset OTP."""
    await services.verify_otp(payload)
    return MessageResponse(message="OTP verified.")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(payload: ResetPasswordRequest) -> MessageResponse:
    """Reset the password using a valid OTP."""
    await services.reset_password(payload)
    return MessageResponse(message="Password has been reset successfully.")
