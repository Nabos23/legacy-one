"""starlette-admin panel backed by MongoDB via ODMantic.

Mounted at /admin. Login uses the existing `users` collection; only users with
role == "admin" may sign in.

IMPORTANT: each ODMantic model declares EVERY stored field, because ODMantic's
save() replaces the whole document — undeclared fields would be dropped on edit.
Sensitive fields (password, otp_hash, connection_string) are hidden from the UI.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import json
from bson import ObjectId
_original_default = json.JSONEncoder.default
def _patched_default(self, obj):
    if isinstance(obj, ObjectId):
        return str(obj)
    return _original_default(self, obj)
json.JSONEncoder.default = _patched_default
from odmantic import AIOEngine, Field, Model
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette_admin import BooleanField, IntegerField, StringField
from starlette_admin.auth import AdminUser, AuthProvider
from starlette_admin.contrib.odmantic import Admin, ModelView
from starlette_admin.exceptions import LoginFailed

from backend.auth.permissions import can_access_admin_panel
from backend.core.config import settings
from backend.core.security import verify_password
from backend.core.softdelete import NOT_DELETED
from backend.db.database import DATABASE_NAME, client, users_collection

engine = AIOEngine(client=client, database=DATABASE_NAME)
def _serialize(obj):
    """Recursively convert ObjectId to str in dicts/lists."""
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize(i) for i in obj]
    return obj


class SafeModelView(ModelView):
    """ModelView that converts ObjectId → str before JSON serialization."""

    async def serialize_field_value(self, value, field, action, request):
        value = await super().serialize_field_value(value, field, action, request)
        return _serialize(value)
    
class Organization(Model):
    name: Optional[str] = None
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    is_deleted: Optional[bool] = False
    deleted_at: Optional[datetime] = None
    model_config = {"collection": "organizations"}


class User(Model):
    organization_id: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None  # hashed; hidden from UI
    created_at: Optional[datetime] = None
    model_config = {"collection": "users"}


class Agent(Model):
    organization_id: Optional[str] = None
    name: Optional[str] = None
    prompt: Optional[str] = None
    guardrails: Optional[str] = None
    description: Optional[str] = None
    user_description: Optional[str] = None
    instructions: Optional[str] = None
    tool_ids: List[str] = []
    rag_ids: List[str] = []
    avatar_type: Optional[str] = None
    avatar_value: Optional[str] = None
    avatar_url: Optional[str] = None
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    is_deleted: Optional[bool] = False
    deleted_at: Optional[datetime] = None
    model_config = {"collection": "agents"}


class Tool(Model):
    organization_id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    user_description: Optional[str] = None
    db_conn_id: Optional[str] = None
    tool_id: Optional[str] = None
    created_at: Optional[datetime] = None
    is_deleted: Optional[bool] = False
    deleted_at: Optional[datetime] = None
    model_config = {"collection": "tools"}


class DbConnection(Model):
    organization_id: Optional[str] = None
    tool_id: Optional[str] = None
    connection_string: Optional[str] = None  # encrypted; hidden from UI
    db_schema: Optional[Dict[str, Any]] = Field(default=None, key_name="schema")
    schema_gridfs_id: Optional[str] = None  # set when schema is offloaded to GridFS
    created_at: Optional[datetime] = None
    is_deleted: Optional[bool] = False
    deleted_at: Optional[datetime] = None
    model_config = {"collection": "db_connections"}


class ToolRegistry(Model):
    name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    is_active: Optional[bool] = True
    tool_schema: Optional[Dict[str, Any]] = None  # JSON schema for the tool
    # auto-stamped on create (admin form doesn't ask for it)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_deleted: Optional[bool] = False
    model_config = {"collection": "tool_registry"}


class Role(Model):
    """A role and the permission flags it grants.

    `permissions` is a simple flag map (e.g. {"view": true, "edit": false, ...})
    so access can be tuned directly from the DB / admin panel.
    """

    name: Optional[str] = None  # identifier, e.g. "org_manager"
    label: Optional[str] = None  # human-friendly name, e.g. "Org Manager"
    description: Optional[str] = None
    permissions: Dict[str, bool] = {}
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_deleted: Optional[bool] = False
    model_config = {"collection": "roles"}


class Permission(Model):
    """A single permission definition."""

    name: str  # slug, e.g. "create_agent"
    label: str
    description: str
    resource: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_deleted: Optional[bool] = False
    model_config = {"collection": "permissions"}


class RolePermission(Model):
    """Role-to-permission mapping."""

    role: str  # slug, e.g. "org_admin"
    label: str
    description: str
    permission_names: List[str] = []
    # Permission a caller must hold to assign *this* role to a user.
    # Leave blank to allow anyone holding the general `create_user` permission.
    assign_permission: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_deleted: Optional[bool] = False
    model_config = {"collection": "role_permissions"}


class RateLimitConfig(Model):
    name: Optional[str] = None  # identifier; the active doc is "global"
    enabled: Optional[bool] = True
    max_requests: Optional[int] = 100
    window_seconds: Optional[int] = 60
    model_config = {"collection": "rate_limit_config"}


class QuotaConfig(Model):
    name: Optional[str] = None  # identifier; the active doc is "global"
    enabled: Optional[bool] = True
    max_orgs_per_day: Optional[int] = 10
    max_tools_per_org: Optional[int] = 100
    model_config = {"collection": "quota_config"}


class AdminAuthProvider(AuthProvider):
    """Authenticate admin users against the `users` collection."""

    async def login(self, username, password, remember_me, request, response):
        user = await users_collection.find_one({"email": username, **NOT_DELETED})
        if not user or not verify_password(password, user.get("password", "")):
            raise LoginFailed("Invalid email or password.")
        if not await can_access_admin_panel(user.get("role", "")):
            raise LoginFailed("Admin privileges required.")
        request.session.update({"admin_id": str(user["_id"]), "admin_name": user["name"]})
        return response

    async def is_authenticated(self, request) -> bool:
        admin_id = request.session.get("admin_id")
        if not admin_id:
            return False
        request.state.admin_name = request.session.get("admin_name", "Admin")
        return True

    def get_admin_user(self, request: Request) -> AdminUser:
        return AdminUser(username=getattr(request.state, "admin_name", "Admin"))

    async def logout(self, request: Request, response: Response) -> Response:
        request.session.clear()
        return response


admin = Admin(
    engine,
    title="Legacy AI Admin",
    auth_provider=AdminAuthProvider(),
    middlewares=[
        Middleware(SessionMiddleware, secret_key=settings.JWT_SECRET_KEY)
    ],
)

class UserView(SafeModelView):
    """User admin view that never exposes the password hash."""

    exclude_fields_from_list = ["password"]
    exclude_fields_from_detail = ["password"]
    exclude_fields_from_create = ["password"]
    exclude_fields_from_edit = ["password"]


class DbConnectionView(SafeModelView):
    """DB-connection view that hides the encrypted connection string."""

    exclude_fields_from_list = ["connection_string"]
    exclude_fields_from_detail = ["connection_string"]
    exclude_fields_from_create = ["connection_string"]
    exclude_fields_from_edit = ["connection_string"]


admin.add_view(SafeModelView(Organization, icon="fa fa-building"))
admin.add_view(UserView(User, icon="fa fa-user"))
admin.add_view(SafeModelView(Agent, icon="fa fa-robot"))
admin.add_view(SafeModelView(Tool, icon="fa fa-wrench"))
class RateLimitConfigView(SafeModelView):
    """Editable, clearly-labelled rate-limit settings."""

    fields = [
        StringField("name", label="Config name", read_only=True,
                    help_text="Leave as 'global'."),
        BooleanField("enabled", label="Rate limiting enabled?",
                     help_text="Turn API rate limiting on or off."),
        IntegerField("max_requests", label="Max requests per window",
                     help_text="How many requests one client (IP) may make per window."),
        IntegerField("window_seconds", label="Window length (seconds)",
                     help_text="The time window the request count resets over, e.g. 60 = per minute."),
    ]


class QuotaConfigView(SafeModelView):
    """Editable, clearly-labelled business quotas."""

    fields = [
        StringField("name", label="Config name", read_only=True,
                    help_text="Leave as 'global'."),
        BooleanField("enabled", label="Quotas enabled?",
                     help_text="Turn all the quotas below on or off."),
        IntegerField("max_orgs_per_day", label="Max organizations per user per day",
                     help_text="A single user cannot create more than this many "
                     "organizations within one day."),
        IntegerField("max_tools_per_org", label="Max tools per organization",
                     help_text="An organization cannot have more than this many tools at once."),
    ]


class RoleView(SafeModelView):
    """Roles and their permission flags — managed directly from the admin."""

    label = "Roles (Legacy)"
    exclude_fields_from_create = ["created_at", "is_deleted"]
    exclude_fields_from_edit = ["created_at", "is_deleted"]
    exclude_fields_from_list = ["is_deleted"]
    exclude_fields_from_detail = ["is_deleted"]


class PermissionView(SafeModelView):
    """Catalog of all available permissions."""

    label = "Permissions"
    exclude_fields_from_create = ["created_at", "is_deleted"]
    exclude_fields_from_edit = ["created_at", "is_deleted"]
    exclude_fields_from_list = ["is_deleted"]
    exclude_fields_from_detail = ["is_deleted"]


class RolePermissionView(SafeModelView):
    """Modern Role-to-Permission mapping (list of permission names)."""

    label = "Role Permissions"
    exclude_fields_from_create = ["created_at", "updated_at", "is_deleted"]
    exclude_fields_from_edit = ["created_at", "updated_at", "is_deleted"]
    exclude_fields_from_list = ["is_deleted"]
    exclude_fields_from_detail = ["is_deleted"]


class ToolRegistryView(SafeModelView):
    """Tool registry catalog — created/managed from the admin."""

    label = "Tool Registry"
    exclude_fields_from_create = ["created_at", "is_deleted"]
    exclude_fields_from_edit = ["created_at", "is_deleted"]
    exclude_fields_from_list = ["is_deleted"]
    exclude_fields_from_detail = ["is_deleted"]


admin.add_view(DbConnectionView(DbConnection, icon="fa fa-database"))
admin.add_view(ToolRegistryView(ToolRegistry, icon="fa fa-list"))
admin.add_view(PermissionView(Permission, name="Permissions", icon="fa fa-key"))
admin.add_view(RolePermissionView(RolePermission, name="Role Permissions", icon="fa fa-user-lock"))
admin.add_view(RoleView(Role, name="Roles (Legacy)", icon="fa fa-user-shield"))
admin.add_view(RateLimitConfigView(RateLimitConfig, name="Rate Limit", icon="fa fa-gauge-high"))
admin.add_view(QuotaConfigView(QuotaConfig, name="Quotas / Limits", icon="fa fa-sliders"))