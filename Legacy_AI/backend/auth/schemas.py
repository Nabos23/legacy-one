from datetime import datetime
from typing import Annotated, Optional

from pydantic import AfterValidator, BaseModel, EmailStr, Field

from backend.auth.constants import ROLE_MEMBER, ROLE_USER
from backend.auth.validators import validate_email_address, validate_password_strength

SignupEmail = Annotated[EmailStr, AfterValidator(validate_email_address)]
SignupPassword = Annotated[str, AfterValidator(validate_password_strength)]


class SignupRequest(BaseModel):
    """Payload for registering a new user."""

    organization_id: str
    name: str
    email: SignupEmail
    password: SignupPassword
    role: str = ROLE_USER


class LoginRequest(BaseModel):
    """Payload for logging in."""

    email: EmailStr
    password: str


class AdminCreateUserRequest(BaseModel):
    """Payload for an admin creating a user."""

    name: str
    email: EmailStr
    password: str = Field(min_length=6)
    role: str = ROLE_MEMBER
    organization_id: Optional[str] = None


class UserPublic(BaseModel):
    """User data returned to clients (never includes the password)."""

    id: Optional[str] = None
    organization_id: str
    name: str
    email: EmailStr
    role: str
    created_at: datetime
    avatar_url: Optional[str] = None
    waiting_approval: Optional[str] = "approved"


class UpdateProfileRequest(BaseModel):
    """Payload for a user updating their own profile."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)


class UpdateUserRequest(BaseModel):
    """Payload for an admin updating another user's name and/or role."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    role: Optional[str] = None


class TokenResponse(BaseModel):
    """JWT issued on successful signup/login."""

    access_token: str
    token_type: str = "bearer"
    user: UserPublic
    db_conn_ids: list[str] = []


class ForgotPasswordRequest(BaseModel):
    """Request a password-reset OTP for an email."""

    email: EmailStr


class VerifyOtpRequest(BaseModel):
    """Verify a password-reset OTP."""

    email: EmailStr
    otp: str


class ResetPasswordRequest(BaseModel):
    """Reset the password using a valid OTP."""

    email: EmailStr
    otp: str
    new_password: SignupPassword


class MessageResponse(BaseModel):
    """Generic message response. `otp` is only populated in dev mode."""

    message: str
    otp: Optional[str] = None


class PermissionPublic(BaseModel):
    """Permission as returned to clients."""

    id: Optional[str] = None
    name: str
    label: str
    description: str
    resource: str
    created_at: datetime


class RolePermissionPublic(BaseModel):
    """Role-to-permissions mapping as returned to clients."""

    id: Optional[str] = None
    role: str
    label: str
    description: str
    permission_names: list[str]
    created_at: datetime
    updated_at: datetime


class OrgRolePermissionUpdate(BaseModel):
    """Payload for an org admin customizing a role's permissions in their org."""

    permission_names: list[str]


class OrgRolePermissionPublic(BaseModel):
    """A role's effective (possibly org-overridden) permissions, as returned to clients."""

    organization_id: str
    role: str
    label: str
    permission_names: list[str]
    is_override: bool
    updated_at: Optional[datetime] = None

class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: SignupPassword
    organization_id: Optional[str] = None

class UserApprovalRequest(BaseModel):
    user_id: str
    status: str = Field(description="Must be 'approved' or 'disapproved'")
