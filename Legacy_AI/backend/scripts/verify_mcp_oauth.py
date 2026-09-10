"""
Verify the non-interactive parts of MCP OAuth (Phase 2):
  1. Encrypted token storage round-trip (MongoTokenStorage).
  2. Runtime bearer resolution (resolve_oauth_headers) + missing-token error.
  3. Client metadata / redirect URI construction.
  4. Best-effort: live OAuth metadata DISCOVERY against Atlassian's well-known
     endpoints (read-only GETs; no client registration, no token exchange).

The interactive consent + token exchange need a real browser login and can't be
automated here. Usage:  uv run python -m backend.scripts.verify_mcp_oauth
"""

import asyncio
import uuid

from dotenv import load_dotenv

load_dotenv()


def ok(m): print(f"  [OK]   {m}")
def bad(m): print(f"  [FAIL] {m}")
def info(m): print(f"  [..]   {m}")


def test_storage_and_runtime() -> None:
    from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
    from backend.mcp_server.services import (
        MongoTokenStorage,
        OAuthNotAuthorized, build_client_metadata, redirect_uri, resolve_oauth_headers,
    )

    key = f"verify-oauth-{uuid.uuid4().hex[:8]}"
    storage = MongoTokenStorage(key)
    try:
        client_info = OAuthClientInformationFull(
            client_id="test-client", client_secret="test-secret",
            redirect_uris=[redirect_uri()], token_endpoint_auth_method="client_secret_post",
        )
        tokens = OAuthToken(access_token="ACCESS123", token_type="Bearer",
                            expires_in=3600, refresh_token="REFRESH123")
        storage.save_runtime_meta(
            client_info=client_info, tokens=tokens,
            token_endpoint="https://auth.example.com/token", resource="https://mcp.example.com",
        )

        # round-trip
        ci = storage.read_client_info_sync()
        tk = storage.read_tokens_sync()
        meta = storage.read_meta_sync()
        assert ci.client_id == "test-client" and ci.client_secret == "test-secret", "client_info round-trip"
        assert tk.access_token == "ACCESS123" and tk.refresh_token == "REFRESH123", "tokens round-trip"
        assert meta["token_endpoint"] == "https://auth.example.com/token", "meta round-trip"
        ok("token storage round-trip (encrypted client_info + tokens + meta)")

        # encrypted at rest?
        from backend.db.database import mcp_oauth_tokens_sync
        raw = mcp_oauth_tokens_sync.find_one({"storage_key": key})
        assert "ACCESS123" not in str(raw.get("tokens")), "tokens must be encrypted at rest"
        assert "test-secret" not in str(raw.get("client_info")), "client_info must be encrypted at rest"
        ok("secrets are encrypted at rest (no plaintext token/secret in Mongo)")

        # runtime bearer (valid token, not near expiry -> no refresh)
        headers = resolve_oauth_headers(key)
        assert headers == {"Authorization": "Bearer ACCESS123"}, f"bearer header, got {headers}"
        ok("resolve_oauth_headers returns the Bearer header for a valid token")

        # missing token -> explicit error
        try:
            resolve_oauth_headers(f"nonexistent-{uuid.uuid4().hex[:6]}")
            bad("missing token did not raise")
        except OAuthNotAuthorized:
            ok("resolve_oauth_headers raises OAuthNotAuthorized when not authorized")

        # client metadata / redirect uri
        cm = build_client_metadata("read:jira-work")
        assert str(cm.redirect_uris[0]).endswith("/mcp-servers/oauth/callback"), "redirect uri path"
        assert "authorization_code" in cm.grant_types and "refresh_token" in cm.grant_types, "grant types"
        ok(f"client metadata built (redirect_uri={redirect_uri()})")
    finally:
        storage.delete()


async def test_live_discovery() -> None:
    """Best-effort: confirm Atlassian advertises OAuth metadata our flow can discover."""
    import httpx
    from mcp.client.auth.utils import (
        build_oauth_authorization_server_metadata_discovery_urls,
        build_protected_resource_metadata_discovery_urls,
        create_oauth_metadata_request,
        handle_auth_metadata_response,
        handle_protected_resource_response,
    )

    server_url = "https://mcp.atlassian.com/v1/mcp"
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as http:
            prm = None
            for url in build_protected_resource_metadata_discovery_urls(None, server_url):
                resp = await http.send(create_oauth_metadata_request(url))
                prm = await handle_protected_resource_response(resp)
                if prm:
                    info(f"PRM found at {url}")
                    break
            # Mirror start_authorization: if PRM is absent, still run ASM discovery
            # with auth_server=None (falls back to the MCP host's root well-known).
            auth_server = str(prm.authorization_servers[0]) if (prm and prm.authorization_servers) else None
            if not auth_server:
                info("no PRM (Atlassian) — falling back to ASM root well-known, like the real flow")
            asm = None
            for url in build_oauth_authorization_server_metadata_discovery_urls(auth_server, server_url):
                resp = await http.send(create_oauth_metadata_request(url))
                _ok, asm = await handle_auth_metadata_response(resp)
                if asm:
                    break
            if asm and asm.authorization_endpoint and asm.token_endpoint:
                ok(f"LIVE Atlassian discovery: auth={asm.authorization_endpoint} token={asm.token_endpoint}")
            else:
                info("Atlassian ASM endpoints not discovered — discovery inconclusive")
    except Exception as exc:  # noqa: BLE001
        info(f"live discovery skipped (network/endpoint): {exc}")


async def main() -> None:
    print("\n=== MCP OAuth (Phase 2) verification ===")
    test_storage_and_runtime()
    await test_live_discovery()
    print("=== done (interactive consent + token exchange require a real browser login) ===\n")


if __name__ == "__main__":
    asyncio.run(main())
