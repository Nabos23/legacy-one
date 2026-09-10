import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import httpx
from bson import ObjectId
from backend.auth.cache import invalidate_user
from fastapi import HTTPException, status
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, URLSafeTimedSerializer
from pymongo import ReturnDocument

from backend.notifications.services import create_notification
from backend.db.database import db_connections_collection, organizations_collection
from backend.auth.constants import NON_OVERRIDABLE_PERMISSIONS, ROLE_ORG_ADMIN, ROLE_USER
from backend.auth.models import User
from backend.auth.permissions import (
    EDITABLE_OVERRIDE_ROLES,
    assert_can_assign_role,
    invalidate_org_role_override_cache,
    is_super_admin,
)
from backend.auth.schemas import (
    AdminCreateUserRequest,
    ForgotPasswordRequest,
    LoginRequest,
    OrgRolePermissionPublic,
    PermissionPublic,
    ResetPasswordRequest,
    SignupRequest,
    UserPublic,
    VerifyOtpRequest,
)
from backend.core.config import settings
from backend.core.email import send_otp_email
from backend.core.security import create_access_token, hash_password, verify_password
from backend.core.softdelete import NOT_DELETED
from backend.db.database import (
    org_role_permissions_collection,
    password_resets_collection,
    permissions_collection,
    role_permissions_collection,
    users_collection,
)
from backend.organization.models import Organization

logger = logging.getLogger(__name__)

_oauth_state = URLSafeTimedSerializer(settings.JWT_SECRET_KEY, salt="user-login-oauth")


def frontend_oauth_redirect(**params: str) -> RedirectResponse:
    # Tokens are placed in the URL fragment: fragments are not sent in HTTP
    # requests and therefore do not appear in server/proxy logs.
    response = RedirectResponse(f"{settings.FRONTEND_URL.rstrip('/')}/auth/callback#{urlencode(params)}")
    response.delete_cookie("login_oauth_state", path="/auth/oauth")
    return response


def oauth_provider_config(provider: str) -> tuple[str, str, str]:
    """Return (client_id, client_secret, redirect_uri) for a provider, or raise 404."""
    if provider == "google":
        return (
            settings.GOOGLE_LOGIN_CLIENT_ID or settings.GOOGLE_CLIENT_ID,
            settings.GOOGLE_LOGIN_CLIENT_SECRET or settings.GOOGLE_CLIENT_SECRET,
            settings.GOOGLE_LOGIN_REDIRECT_URI,
        )
    if provider == "github":
        return (
            settings.GITHUB_LOGIN_CLIENT_ID,
            settings.GITHUB_LOGIN_CLIENT_SECRET,
            settings.GITHUB_LOGIN_REDIRECT_URI,
        )
    raise HTTPException(status_code=404, detail="Unknown OAuth provider.")


def oauth_authorize_url(provider: str, client_id: str, redirect_uri: str, state: str) -> str:
    """Build the provider's consent-screen URL for a given signed state."""
    if provider == "google":
        query = urlencode({"client_id": client_id, "redirect_uri": redirect_uri,
                           "response_type": "code", "scope": "openid email profile",
                           "state": state, "prompt": "select_account"})
        return f"https://accounts.google.com/o/oauth2/v2/auth?{query}"
    query = urlencode({"client_id": client_id, "redirect_uri": redirect_uri,
                       "scope": "read:user user:email", "state": state})
    return f"https://github.com/login/oauth/authorize?{query}"


def create_oauth_state(provider: str, link_user_id: str | None = None) -> str:
    """Sign a short-lived CSRF state token binding an auth attempt to a provider.

    When `link_user_id` is set, the callback attaches the provider identity to
    that already-authenticated account instead of authenticating/creating one --
    see `oauth_link`.
    """
    payload = {"provider": provider}
    if link_user_id:
        payload["link_user_id"] = link_user_id
    return _oauth_state.dumps(payload)


def verify_oauth_state(provider: str, state: str, cookie_state: str | None) -> dict:
    """Validate the callback's state against the cookie and its signature/age.

    Raises itsdangerous.BadSignature / SignatureExpired on any mismatch, tamper,
    or expiry (callers should treat both as "request expired, try again").
    Returns the decoded state payload (provider, optional link_user_id).
    """
    if not cookie_state or not secrets.compare_digest(state, cookie_state):
        raise BadSignature("browser state mismatch")
    state_data = _oauth_state.loads(state, max_age=600)
    if state_data.get("provider") != provider:
        raise BadSignature("provider mismatch")
    return state_data


async def oauth_exchange(provider: str, code: str) -> tuple[str, str, str]:
    """Exchange an authorization code for the provider's verified identity.

    Returns (provider_user_id, email, name). Raises httpx.HTTPError, KeyError, or
    ValueError (e.g. unverified email) on failure.
    """
    client_id, client_secret, redirect_uri = oauth_provider_config(provider)
    async with httpx.AsyncClient(timeout=15) as client:
        if provider == "google":
            token_res = await client.post("https://oauth2.googleapis.com/token", data={
                "code": code, "client_id": client_id, "client_secret": client_secret,
                "redirect_uri": redirect_uri, "grant_type": "authorization_code",
            })
            token_res.raise_for_status()
            profile_res = await client.get("https://openidconnect.googleapis.com/v1/userinfo",
                                           headers={"Authorization": f"Bearer {token_res.json()['access_token']}"})
            profile_res.raise_for_status()
            profile = profile_res.json()
            if not profile.get("email_verified"):
                raise ValueError("Google email is not verified")
            return str(profile["sub"]), profile["email"], profile.get("name", "")

        token_res = await client.post("https://github.com/login/oauth/access_token",
            data={"client_id": client_id, "client_secret": client_secret, "code": code,
                  "redirect_uri": redirect_uri}, headers={"Accept": "application/json"})
        token_res.raise_for_status()
        access_token = token_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"}
        profile_res = await client.get("https://api.github.com/user", headers=headers)
        emails_res = await client.get("https://api.github.com/user/emails", headers=headers)
        profile_res.raise_for_status(); emails_res.raise_for_status()
        profile = profile_res.json()
        verified = [e for e in emails_res.json() if e.get("verified")]
        primary = next((e for e in verified if e.get("primary")), verified[0] if verified else None)
        if not primary:
            raise ValueError("GitHub account has no verified email")
        return str(profile["id"]), primary["email"], profile.get("name") or profile.get("login", "")


def _to_public(doc: dict) -> UserPublic:
    """Map a MongoDB user document to the public schema."""
    return UserPublic(
        id=str(doc["_id"]),
        organization_id=doc["organization_id"],
        name=doc["name"],
        email=doc["email"],
        role=doc["role"],
        created_at=doc["created_at"],
        avatar_url=doc.get("avatar_url"),
        waiting_approval=doc.get("waiting_approval", "approved"),
    )


async def _org_db_conn_ids(organization_id: str) -> list[str]:
    """Return the IDs of the organization's active database connections."""

    cursor = db_connections_collection.find(
        {"organization_id": organization_id, "is_deleted": {"$ne": True}}
    )
    conn_docs = await cursor.to_list(length=50)
    return [str(c["_id"]) for c in conn_docs]


async def _insert_user(
    *, organization_id: str, name: str, email: str, role: str, password: str, waiting_approval: str = "approved"
) -> dict:
    """Insert a user, enforcing unique email. Returns the stored document."""
    existing = await users_collection.find_one({"email": email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    user = User(
        organization_id=organization_id,
        name=name,
        email=email,
        role=role,
        password=hash_password(password),
        waiting_approval=waiting_approval,
    )
    doc = user.model_dump(by_alias=True, exclude={"id"})
    result = await users_collection.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def request_org_approval(organization_id: str, user_doc: dict) -> list[str]:
    """Find all org admins of an organization and send them a request notification for user approval."""
    admin_cursor = users_collection.find(
        {
            "organization_id": organization_id,
            "role": ROLE_ORG_ADMIN,
            "is_deleted": {"$ne": True},
        }
    )
    admin_docs = await admin_cursor.to_list(length=100)
    admin_ids = [str(admin["_id"]) for admin in admin_docs]

    user_name = user_doc.get("name", "New User")
    user_email = user_doc.get("email", "")
    user_id = str(user_doc["_id"])

    if admin_ids:
        for admin_id in admin_ids:
            await create_notification(
                organization_id=organization_id,
                user_id=admin_id,
                type="org_approval_request",
                title="User Approval Requested",
                message=f"User {user_name} ({user_email}) requested to join your organization. (User ID: {user_id})",
            )
    else:
        await create_notification(
            organization_id=organization_id,
            user_id=None,
            type="org_approval_request",
            title="User Approval Requested",
            message=f"User {user_name} ({user_email}) requested to join your organization. (User ID: {user_id})",
        )
    return admin_ids


async def register(
    name: str,
    email: str,
    password: str,
    organization_id: Optional[str] = None,
) -> tuple[str, UserPublic, list[str]]:
    """Self-service registration: assigns user to a selected organization for admin approval."""

    if not organization_id or organization_id.strip().lower() in ("", "none", "null"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please select an organization.",
        )

    org_id = organization_id.strip()
    role = ROLE_USER

    from bson import ObjectId
    if not ObjectId.is_valid(org_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid organization ID format.",
        )
    org = await organizations_collection.find_one({"_id": ObjectId(org_id), "is_deleted": {"$ne": True}})
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Selected organization does not exist.",
        )
    waiting_approval = "waiting"

    doc = await _insert_user(
        organization_id=org_id,
        name=name,
        email=email,
        role=role,
        password=password,
        waiting_approval=waiting_approval,
    )

    if waiting_approval == "waiting":
        await request_org_approval(organization_id=org_id, user_doc=doc)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration successful! Your account is pending approval by an organization admin before you can log in.",
        )

    user = _to_public(doc)
    token = create_access_token(subject=str(doc["_id"]))
    return token, user, await _org_db_conn_ids(org_id)


async def create_user(payload: SignupRequest, admin: UserPublic) -> tuple[str, UserPublic, list[str]]:
    """Create a new user against an organization and return (access_token, public_user, db_conn_ids)."""
    await assert_can_assign_role(admin, payload.role)
    doc = await _insert_user(
        organization_id=payload.organization_id,
        name=payload.name,
        email=payload.email,
        role=payload.role,
        password=payload.password,
    )
    user = _to_public(doc)
    token = create_access_token(subject=str(doc["_id"]))
    return token, user, await _org_db_conn_ids(payload.organization_id)


async def create_user_as_admin(
    payload: AdminCreateUserRequest, organization_id: str, admin: UserPublic
) -> UserPublic:
    """Admin-driven user creation. Returns the user only (no token)."""
    await assert_can_assign_role(admin, payload.role)
    doc = await _insert_user(
        organization_id=organization_id,
        name=payload.name,
        email=payload.email,
        role=payload.role,
        password=payload.password,
    )
    return _to_public(doc)


async def login(payload: LoginRequest) -> tuple[str, UserPublic, list[str]]:
    """Authenticate a user and return (access_token, public_user, db_conn_ids)."""
    doc = await users_collection.find_one({"email": payload.email, **NOT_DELETED})
    if not doc or not verify_password(payload.password, doc["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    waiting_approval = doc.get("waiting_approval", "approved")
    if waiting_approval == "waiting":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account registration is pending admin approval for this organization.",
        )
    if waiting_approval == "disapproved":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your registration request for this organization was disapproved.",
        )

    user = _to_public(doc)
    token = create_access_token(subject=str(doc["_id"]))
    return token, user, await _org_db_conn_ids(doc["organization_id"])


async def update_user_approval_status(
    admin: UserPublic, target_user_id: str, new_status: str
) -> UserPublic:
    """Admin service to approve or disapprove a pending user registration."""
    if new_status not in ("approved", "disapproved", "waiting"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid status value. Must be 'approved', 'disapproved', or 'waiting'.",
        )

    if not ObjectId.is_valid(target_user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    target_doc = await users_collection.find_one({"_id": ObjectId(target_user_id)})
    if not target_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    if not is_super_admin(admin.role) and target_doc.get("organization_id") != admin.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot manage approval status of users in another organization.",
        )

    updated_doc = await users_collection.find_one_and_update(
        {"_id": ObjectId(target_user_id)},
        {"$set": {"waiting_approval": new_status}},
        return_document=ReturnDocument.AFTER,
    )
    invalidate_user(target_user_id)
    return _to_public(updated_doc)


async def list_pending_approvals(admin: UserPublic) -> list[UserPublic]:
    """List users in the admin's organization with waiting_approval == 'waiting'."""
    if not is_super_admin(admin.role) and admin.role != ROLE_ORG_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization admins can view pending approvals.",
        )
    cursor = users_collection.find(
        {
            "organization_id": admin.organization_id,
            "waiting_approval": "waiting",
        }
    )
    docs = await cursor.to_list(length=200)

    return [_to_public(doc) for doc in docs]


class OAuthAccountExists(Exception):
    """Raised when a provider-verified email matches an existing account that
    hasn't linked this provider yet. The caller must log in with their
    existing method and link the provider from account settings instead --
    auto-linking on email match alone would let anyone plant a placeholder
    account for a target's email (in an attacker-controlled org, with an
    attacker-chosen role) and have the real owner silently merged into it
    the first time they sign in with that provider."""


class OAuthNoAccount(Exception):
    """Raised when no account exists for this identity/email at all. OAuth is
    a login path only -- it never self-provisions an org/account. Accounts
    must be created via /auth/register or by an org admin, then the provider
    linked explicitly from account settings (see `oauth_link`)."""


async def oauth_authenticate(
    *, provider: str, provider_user_id: str, email: str, name: str
) -> tuple[str, UserPublic, list[str]]:
    """Log in via an already-linked provider identity. Never creates an account.

    Provider callbacks must verify the email before calling this function.
    Only an exact (provider, provider_user_id) match authenticates -- an email
    match alone is not enough (see `oauth_link` for the explicit, authenticated
    way to connect a provider to an account), and no match at all means there
    is simply no account to log into.
    """
    normalized_email = email.strip().lower()
    identity_key = f"oauth_identities.{provider}"
    doc = await users_collection.find_one({identity_key: provider_user_id, **NOT_DELETED})

    if not doc:
        existing = await users_collection.find_one(
            {"email": {"$regex": f"^{re.escape(normalized_email)}$", "$options": "i"}}
        )
        if existing:
            raise OAuthAccountExists(normalized_email)
        raise OAuthNoAccount(normalized_email)

    user = _to_public(doc)
    token = create_access_token(subject=str(doc["_id"]))
    return token, user, await _org_db_conn_ids(doc["organization_id"])


async def oauth_link(
    *, provider: str, provider_user_id: str, email: str, user_id: str
) -> tuple[str, UserPublic, list[str]]:
    """Attach a provider identity to the already-authenticated account `user_id`.

    This is the only path that may connect a new login method to an existing
    account, and it always runs against an account already proven via a valid
    session JWT (see routes: `/auth/oauth/{provider}/link`). Requires the
    provider-verified email to match the account's own email, and the
    provider identity to not already belong to a different account.
    """
    if not ObjectId.is_valid(user_id):
        raise ValueError("Your session is invalid. Please log in again.")
    doc = await users_collection.find_one({"_id": ObjectId(user_id)})
    if not doc:
        raise ValueError("Your account no longer exists.")

    normalized_email = email.strip().lower()
    if doc["email"].strip().lower() != normalized_email:
        raise ValueError(
            f"That {provider.title()} account's email doesn't match your account's email."
        )

    identity_key = f"oauth_identities.{provider}"
    other = await users_collection.find_one({identity_key: provider_user_id})
    if other and other["_id"] != doc["_id"]:
        raise ValueError(f"That {provider.title()} account is already linked to another user.")

    await users_collection.update_one(
        {"_id": doc["_id"]}, {"$set": {identity_key: provider_user_id}}
    )
    invalidate_user(str(doc["_id"]))
    doc.setdefault("oauth_identities", {})[provider] = provider_user_id

    user = _to_public(doc)
    token = create_access_token(subject=str(doc["_id"]))
    return token, user, await _org_db_conn_ids(doc["organization_id"])


async def get_user_by_id(user_id: str) -> Optional[UserPublic]:
    """Look up a user by its string id; returns None if not found/invalid."""
    if not ObjectId.is_valid(user_id):
        return None
    doc = await users_collection.find_one({"_id": ObjectId(user_id), **NOT_DELETED})
    return _to_public(doc) if doc else None


def _generate_otp() -> str:
    """Generate a 6-digit numeric OTP."""
    return f"{secrets.randbelow(1_000_000):06d}"


async def _get_valid_reset(email: str, otp: str) -> dict:
    """Return the reset record if the OTP is valid and unexpired, else raise."""
    record = await password_resets_collection.find_one({"email": email})
    if not record or not verify_password(otp, record["otp_hash"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP.",
        )
    expires_at = record["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP has expired. Please request a new one.",
        )
    return record


async def forgot_password(payload: ForgotPasswordRequest) -> Optional[str]:
    """Generate, store, and email an OTP for the given address.

    Always succeeds from the caller's perspective (no user enumeration); the OTP
    is only created and sent when the email actually belongs to a user.
    """
    user = await users_collection.find_one({"email": payload.email})
    if not user:
        return None

    otp = _generate_otp()
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.OTP_EXPIRE_MINUTES
    )
    await password_resets_collection.update_one(
        {"email": payload.email},
        {
            "$set": {
                "email": payload.email,
                "otp_hash": hash_password(otp),
                "expires_at": expires_at,
                "created_at": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )
    logger.debug("Password-reset OTP generated for %s", payload.email)
    try:
        await send_otp_email(payload.email, otp)
    except Exception:
        # Don't leak SMTP failures to the caller (would enable user
        # enumeration / expose infra details); the OTP is still valid and
        # can be retrieved via OTP_RETURN_IN_RESPONSE in dev.
        logger.exception("Failed to send password-reset OTP email to %s", payload.email)
    return otp


async def verify_otp(payload: VerifyOtpRequest) -> None:
    """Validate an OTP without consuming it; raises 400 if invalid/expired."""
    await _get_valid_reset(payload.email, payload.otp)


async def reset_password(payload: ResetPasswordRequest) -> None:
    """Verify the OTP, set the new password, and invalidate the OTP."""
    await _get_valid_reset(payload.email, payload.otp)
    await users_collection.update_one(
        {"email": payload.email},
        {"$set": {"password": hash_password(payload.new_password)}},
    )
    reset_doc = await users_collection.find_one({"email": payload.email}, {"_id": 1})
    if reset_doc:
        invalidate_user(str(reset_doc["_id"]))
    await password_resets_collection.delete_one({"email": payload.email})


async def list_permission_catalog() -> list[PermissionPublic]:
    """Every permission definition, excluding the ones no org override may
    ever grant (see NON_OVERRIDABLE_PERMISSIONS)."""
    cursor = permissions_collection.find(
        {**NOT_DELETED, "name": {"$nin": list(NON_OVERRIDABLE_PERMISSIONS)}}
    )
    return [
        PermissionPublic(
            id=str(doc["_id"]),
            name=doc["name"],
            label=doc.get("label", doc["name"]),
            description=doc.get("description", ""),
            resource=doc.get("resource", ""),
            created_at=doc["created_at"],
        )
        async for doc in cursor
    ]


def _assert_editable_role(role: str) -> None:
    if role not in EDITABLE_OVERRIDE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only the org_manager and user roles can be customized per organization.",
        )


async def get_org_role_permissions(organization_id: str, role: str) -> OrgRolePermissionPublic:
    """The effective permission_names for (organization_id, role): the org's
    override if one exists, otherwise the global default."""
    _assert_editable_role(role)
    global_doc = await role_permissions_collection.find_one({"role": role, **NOT_DELETED})
    if not global_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Role '{role}' not found.")

    override_doc = await org_role_permissions_collection.find_one(
        {"organization_id": organization_id, "role": role}
    )
    if override_doc:
        return OrgRolePermissionPublic(
            organization_id=organization_id,
            role=role,
            label=global_doc.get("label", role),
            permission_names=override_doc.get("permission_names", []),
            is_override=True,
            updated_at=override_doc.get("updated_at"),
        )
    return OrgRolePermissionPublic(
        organization_id=organization_id,
        role=role,
        label=global_doc.get("label", role),
        permission_names=global_doc.get("permission_names", []),
        is_override=False,
        updated_at=None,
    )


async def _validate_overridable_permission_names(permission_names: list[str]) -> list[str]:
    """Dedupe and validate every name both exists in the global catalog and
    is not in NON_OVERRIDABLE_PERMISSIONS (defense in depth -- the catalog
    endpoint already excludes them, but a raw API call could try anyway)."""
    unique_names = list(dict.fromkeys(n for n in permission_names if n))
    blocked = [n for n in unique_names if n in NON_OVERRIDABLE_PERMISSIONS]
    if blocked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"These permissions can never be granted via an org override: {', '.join(blocked)}.",
        )
    known = {
        doc["name"]
        async for doc in permissions_collection.find(NOT_DELETED, {"name": 1})
    }
    unknown = [n for n in unique_names if n not in known]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown permission(s): {', '.join(unknown)}.",
        )
    return unique_names


async def update_org_role_permissions(
    organization_id: str, role: str, permission_names: list[str]
) -> OrgRolePermissionPublic:
    """Upsert this org's override for `role`. Never touches the global
    `role_permissions` document that every other org falls back to."""
    _assert_editable_role(role)
    cleaned = await _validate_overridable_permission_names(permission_names)
    now = datetime.now(timezone.utc)
    await org_role_permissions_collection.update_one(
        {"organization_id": organization_id, "role": role},
        {
            "$set": {"permission_names": cleaned, "updated_at": now},
            "$setOnInsert": {"organization_id": organization_id, "role": role},
        },
        upsert=True,
    )
    invalidate_org_role_override_cache(organization_id, role)
    return await get_org_role_permissions(organization_id, role)


async def reset_org_role_permissions(organization_id: str, role: str) -> OrgRolePermissionPublic:
    """Remove this org's override for `role`, reverting it to the global default."""
    _assert_editable_role(role)
    await org_role_permissions_collection.delete_one({"organization_id": organization_id, "role": role})
    invalidate_org_role_override_cache(organization_id, role)
    return await get_org_role_permissions(organization_id, role)
