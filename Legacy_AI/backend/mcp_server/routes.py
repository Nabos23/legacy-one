from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import HTMLResponse, RedirectResponse

from backend.agent import services as agent_services
from backend.auth.permissions import assert_org_access
from backend.auth.schemas import UserPublic
from backend.core.config import settings
from backend.core.pagination import Page, Pagination, build_page, pagination_params
from backend.dependencies import get_current_user, require_permission
from backend.mcp_server import services
from backend.mcp_server.services import OAuthError
from backend.mcp_server.schemas import (
    McpAgentToolAttachRequest,
    McpAgentToolPublic,
    McpCatalogEntry,
    McpOAuthStartRequest,
    McpOAuthStartResponse,
    McpServerCreate,
    McpServerPublic,
    McpServerUpdate,
    McpToolSpec,
    McpTestConnectionRequest,
    McpTestConnectionResult,
)

router = APIRouter(
    prefix="/mcp-servers",
    tags=["mcp-servers"],
    dependencies=[Depends(get_current_user)],
)

# Separate router WITHOUT the auth dependency for the OAuth redirect callback:
# the browser arrives from the provider with no JWT; the opaque `state` (bound to
# the stored flow) is the CSRF protection, per the OAuth spec.
oauth_callback_router = APIRouter(prefix="/mcp-servers", tags=["mcp-servers"])


# --- static paths (declared before /{server_id}) --------------------------

@router.get("/catalog", response_model=List[McpCatalogEntry])
async def list_catalog(
    q: Optional[str] = Query(None, description="search term"),
    current_user: UserPublic = Depends(require_permission("view_tool")),
) -> List[McpCatalogEntry]:
    """Browse connectable MCP servers (curated seed + official registry)."""
    return await services.list_catalog(query=q)


@router.post("/test-connection", response_model=McpTestConnectionResult)
async def test_connection(
    payload: McpTestConnectionRequest,
    current_user: UserPublic = Depends(require_permission("view_tool")),
) -> McpTestConnectionResult:
    """Probe a connection string and report its tools — without saving anything."""
    return await services.test_connection(payload)


@router.post("/oauth/start", response_model=McpOAuthStartResponse)
async def oauth_start(
    payload: McpOAuthStartRequest,
    current_user: UserPublic = Depends(require_permission("create_tool")),
) -> McpOAuthStartResponse:
    """
    Begin OAuth authorization for an OAuth-protected remote MCP server (e.g. Jira).

    Returns an `authorization_url` the user opens in a browser to consent. After
    consent the provider redirects to the callback, which finalizes the connection.
    """
    assert_org_access(current_user, payload.organization_id)
    try:
        result = await services.start_authorization(
            connection_string=payload.connection_string,
            organization_id=payload.organization_id,
            agent_id=payload.agent_id,
            name=payload.name,
            user_description=payload.user_description,
            scope=payload.scope,
        )
    except OAuthError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return McpOAuthStartResponse(**result)


@oauth_callback_router.get("/oauth/callback", response_class=HTMLResponse)
async def oauth_callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
) -> HTMLResponse:
    """OAuth redirect target. Finalizes the MCP connection using the flow `state`."""
    if error:
        return HTMLResponse(f"<h3>Authorization failed</h3><p>{error}: {error_description or ''}</p>", status_code=400)
    if not code or not state:
        return HTMLResponse("<h3>Authorization failed</h3><p>Missing code or state.</p>", status_code=400)

    try:
        server = await services.complete_authorization(code=code, state=state)
    except OAuthError as exc:
        return HTMLResponse(f"<h3>Authorization failed</h3><p>{exc}</p>", status_code=400)

    if settings.MCP_OAUTH_SUCCESS_REDIRECT:
        return RedirectResponse(url=settings.MCP_OAUTH_SUCCESS_REDIRECT, status_code=302)
    return HTMLResponse(
        f"<h3>Connected</h3><p>MCP server <b>{server.name}</b> is now attached "
        f"({server.tool_count} tool(s), status: {server.status}). You can close this window.</p>"
    )


@router.get("/agent/{agent_id}", response_model=Page[McpServerPublic])
async def list_by_agent(
    agent_id: str,
    pg: Pagination = Depends(pagination_params),
    current_user: UserPublic = Depends(require_permission("view_tool")),
) -> Page[McpServerPublic]:
    """List MCP instances attached to a specific agent (paginated)."""
    items, total = await services.list_mcp_servers_by_agent(agent_id, skip=pg.skip, limit=pg.limit)
    return build_page(items, total, pg)


# --- CRUD ------------------------------------------------------------------

@router.post("", response_model=McpServerPublic, status_code=status.HTTP_201_CREATED)
async def create_mcp_server(
    payload: McpServerCreate,
    current_user: UserPublic = Depends(require_permission("create_tool")),
) -> McpServerPublic:
    """Connect an MCP server to an agent: probe the connection, discover + cache its tools."""
    assert_org_access(current_user, payload.organization_id)
    return await services.create_mcp_server(payload)


@router.get("", response_model=Page[McpServerPublic])
async def list_mcp_servers(
    pg: Pagination = Depends(pagination_params),
    search: Optional[str] = Query(default=None, description="Filter by name (case-insensitive)"),
    status: Optional[str] = Query(default=None, description="Filter by connection status (connected/error/pending)"),
    agent_id: Optional[str] = Query(default=None, description="Filter by attached agent"),
    current_user: UserPublic = Depends(require_permission("view_tool")),
) -> Page[McpServerPublic]:
    """List MCP instances for the current org (paginated), with optional search/status/agent filters."""
    items, total = await services.list_mcp_servers(
        organization_id=current_user.organization_id,
        skip=pg.skip,
        limit=pg.limit,
        search=search,
        status_filter=status,
        agent_id=agent_id,
    )
    return build_page(items, total, pg)


@router.get("/{server_id}", response_model=McpServerPublic)
async def get_mcp_server(
    server_id: str,
    current_user: UserPublic = Depends(require_permission("view_tool")),
) -> McpServerPublic:
    """Retrieve a single MCP instance by id."""
    server = await services.get_mcp_server(server_id)
    assert_org_access(current_user, server.organization_id)
    return server


@router.put("/{server_id}", response_model=McpServerPublic)
async def update_mcp_server(
    server_id: str,
    payload: McpServerUpdate,
    current_user: UserPublic = Depends(require_permission("edit_tool")),
) -> McpServerPublic:
    """Update an MCP instance. Changing the connection_string re-probes it."""
    server = await services.get_mcp_server(server_id)
    assert_org_access(current_user, server.organization_id)
    return await services.update_mcp_server(server_id, payload)


@router.post("/{server_id}/discover", response_model=McpServerPublic)
async def discover_mcp_server(
    server_id: str,
    current_user: UserPublic = Depends(require_permission("edit_tool")),
) -> McpServerPublic:
    """Re-connect to the server and refresh its cached tool list."""
    server = await services.get_mcp_server(server_id)
    assert_org_access(current_user, server.organization_id)
    return await services.discover_mcp_server(server_id)


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mcp_server(
    server_id: str,
    current_user: UserPublic = Depends(require_permission("delete_tool")),
) -> None:
    """Soft-delete an MCP instance."""
    server = await services.get_mcp_server(server_id)
    assert_org_access(current_user, server.organization_id)
    await services.delete_mcp_server(server_id)


# --- per-tool agent attachment ---------------------------------------------

@router.get("/{server_id}/tools", response_model=List[McpToolSpec])
async def list_server_tools(
    server_id: str,
    current_user: UserPublic = Depends(require_permission("view_tool")),
) -> List[McpToolSpec]:
    """List this server's discovered tools (for the agent-side tool picker)."""
    server = await services.get_mcp_server(server_id)
    assert_org_access(current_user, server.organization_id)
    return server.tools


@router.post(
    "/{server_id}/agents/{agent_id}/tools",
    response_model=List[McpAgentToolPublic],
    status_code=status.HTTP_201_CREATED,
)
async def attach_mcp_tools(
    server_id: str,
    agent_id: str,
    payload: McpAgentToolAttachRequest,
    current_user: UserPublic = Depends(require_permission("create_tool")),
) -> List[McpAgentToolPublic]:
    """Attach one or more of this server's discovered tools to an agent."""
    server = await services.get_mcp_server(server_id)
    assert_org_access(current_user, server.organization_id)
    return await services.attach_mcp_tools(
        organization_id=server.organization_id,
        agent_id=agent_id,
        mcp_server_id=server_id,
        tool_names=payload.tool_names,
        created_by=current_user.id,
    )


@router.delete(
    "/{server_id}/agents/{agent_id}/tools/{tool_name}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def detach_mcp_tool(
    server_id: str,
    agent_id: str,
    tool_name: str,
    current_user: UserPublic = Depends(require_permission("delete_tool")),
) -> None:
    """Detach a single tool from an agent."""
    server = await services.get_mcp_server(server_id)
    assert_org_access(current_user, server.organization_id)
    await services.detach_mcp_tool(agent_id, server_id, tool_name)


@router.get("/{server_id}/tools/{tool_name}/agents", response_model=Page[McpAgentToolPublic])
async def list_agents_by_mcp_tool(
    server_id: str,
    tool_name: str,
    pg: Pagination = Depends(pagination_params),
    current_user: UserPublic = Depends(require_permission("view_tool")),
) -> Page[McpAgentToolPublic]:
    """List which agents have this specific tool attached (paginated)."""
    server = await services.get_mcp_server(server_id)
    assert_org_access(current_user, server.organization_id)
    items, total = await services.list_agents_by_mcp_tool(
        server_id, tool_name, skip=pg.skip, limit=pg.limit
    )
    return build_page(items, total, pg)


@router.get("/agent/{agent_id}/tools", response_model=Page[McpAgentToolPublic])
async def list_agent_mcp_tools(
    agent_id: str,
    pg: Pagination = Depends(pagination_params),
    current_user: UserPublic = Depends(require_permission("view_tool")),
) -> Page[McpAgentToolPublic]:
    """List the individual MCP tools attached to this agent (paginated)."""
    agent = await agent_services.get_agent(agent_id)
    assert_org_access(current_user, agent.organization_id)
    await agent_services.assert_agent_visible(current_user.id, agent)
    items, total = await services.list_mcp_tools_by_agent(agent_id, skip=pg.skip, limit=pg.limit)
    return build_page(items, total, pg)
