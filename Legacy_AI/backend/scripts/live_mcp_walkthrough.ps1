# Live MCP flow walkthrough — drives the running API at $BASE end to end.
# Run the whole thing:   pwsh -File backend/scripts/live_mcp_walkthrough.ps1
# Or paste section-by-section into a pwsh prompt (variables persist).
#
# Requires the server running:  uv run uvicorn backend.main:app --port 8000
# Live MCP parts use `uvx mcp-server-fetch` (no creds; returns "Example Domain").

$ErrorActionPreference = "Stop"
$BASE = "http://127.0.0.1:8000"

function Show($label, $obj) {
    Write-Host "`n=== $label ===" -ForegroundColor Cyan
    $obj | ConvertTo-Json -Depth 6
}
# Helper for calls we EXPECT to fail (422/404) — prints the status code.
function ExpectFail($label, $script) {
    try { & $script; Write-Host "[$label] UNEXPECTED SUCCESS" -ForegroundColor Red }
    catch {
        $code = $_.Exception.Response.StatusCode.value__
        Write-Host "[$label] rejected with HTTP $code (expected)" -ForegroundColor Green
    }
}

# 1) Register -> token + org -------------------------------------------------
$email = "live+$([guid]::NewGuid().ToString('N').Substring(0,8))@test.example.com"
$reg = Invoke-RestMethod -Uri "$BASE/auth/register" -Method Post -ContentType "application/json" `
    -Body (@{ name = "Live QA"; email = $email; password = "Password123" } | ConvertTo-Json)
$TOKEN = $reg.access_token
$ORG   = $reg.user.organization_id
$H     = @{ Authorization = "Bearer $TOKEN" }
Show "1. registered" @{ email = $email; org = $ORG }

# 2) Create an agent ---------------------------------------------------------
$agent = Invoke-RestMethod -Uri "$BASE/agents" -Method Post -Headers $H -ContentType "application/json" `
    -Body (@{
        organization_id = $ORG
        name            = "Live Web Agent"
        prompt          = "You are a web assistant. When asked about a URL you MUST use your fetch tool, then answer from the content."
        guardrails      = ""
    } | ConvertTo-Json)
$AGENT = $agent.id
Show "2. agent created" @{ agent_id = $AGENT }

# 3) Browse the catalog (reads mcp_server_registry) --------------------------
$cat = Invoke-RestMethod -Uri "$BASE/mcp-servers/catalog?q=fetch" -Headers $H
Show "3. catalog q=fetch (first 5 keys)" ($cat | Select-Object -First 5 key, name, transport)

# 4) test-connection (stateless probe) ---------------------------------------
$bad = Invoke-RestMethod -Uri "$BASE/mcp-servers/test-connection" -Method Post -Headers $H -ContentType "application/json" `
    -Body (@{ connection_string = "just gibberish" } | ConvertTo-Json)
Show "4a. test-connection gibberish" @{ ok = $bad.ok; error = $bad.error }
$good = Invoke-RestMethod -Uri "$BASE/mcp-servers/test-connection" -Method Post -Headers $H -ContentType "application/json" `
    -Body (@{ connection_string = "uvx mcp-server-fetch"; timeout = 90 } | ConvertTo-Json)
Show "4b. test-connection uvx mcp-server-fetch" @{ ok = $good.ok; transport = $good.transport; tools = $good.tools.name }

# 5) Flow A — connect FROM CATALOG via registry_key --------------------------
$flowA = Invoke-RestMethod -Uri "$BASE/mcp-servers" -Method Post -Headers $H -ContentType "application/json" `
    -Body (@{
        organization_id  = $ORG
        agent_id         = $AGENT
        registry_key     = "fetch"
        user_description = "Fetch via catalog."
        timeout          = 90
    } | ConvertTo-Json)
$SID_A = $flowA.id
Show "5. Flow A (registry_key=fetch)" @{ id = $SID_A; registry_key = $flowA.registry_key; name = $flowA.name; status = $flowA.status; tools = $flowA.tools.name }

# 6) Flow B — bring-your-own raw connection_string ---------------------------
$flowB = Invoke-RestMethod -Uri "$BASE/mcp-servers" -Method Post -Headers $H -ContentType "application/json" `
    -Body (@{
        organization_id   = $ORG
        agent_id          = $AGENT
        connection_string = "uvx mcp-server-fetch"
        user_description  = "Fetch custom."
        timeout           = 90
    } | ConvertTo-Json)
$SID_B = $flowB.id
Show "6. Flow B (raw connection_string)" @{ id = $SID_B; registry_key = $flowB.registry_key; name = $flowB.name; status = $flowB.status }

# 7) Validation (expected failures) ------------------------------------------
ExpectFail "7a. neither source -> 422" {
    Invoke-RestMethod -Uri "$BASE/mcp-servers" -Method Post -Headers $H -ContentType "application/json" `
        -Body (@{ organization_id = $ORG; agent_id = $AGENT } | ConvertTo-Json)
}
ExpectFail "7b. both sources -> 422" {
    Invoke-RestMethod -Uri "$BASE/mcp-servers" -Method Post -Headers $H -ContentType "application/json" `
        -Body (@{ organization_id = $ORG; agent_id = $AGENT; registry_key = "fetch"; connection_string = "uvx mcp-server-fetch" } | ConvertTo-Json)
}
ExpectFail "7c. bad registry_key -> 404" {
    Invoke-RestMethod -Uri "$BASE/mcp-servers" -Method Post -Headers $H -ContentType "application/json" `
        -Body (@{ organization_id = $ORG; agent_id = $AGENT; registry_key = "no-such-key" } | ConvertTo-Json)
}

# 8) GET / list / list-by-agent ----------------------------------------------
Show "8a. GET one"           (Invoke-RestMethod -Uri "$BASE/mcp-servers/$SID_A" -Headers $H | Select-Object id, name, status, tool_count)
Show "8b. list (org)"        ((Invoke-RestMethod -Uri "$BASE/mcp-servers" -Headers $H).items | Select-Object id, name)
$byAgent = (Invoke-RestMethod -Uri "$BASE/mcp-servers/agent/$AGENT" -Headers $H).items
Show "8c. list-by-agent (both servers should appear)" ($byAgent | Select-Object id, name, registry_key)

# 9) Update + re-discover ----------------------------------------------------
$upd = Invoke-RestMethod -Uri "$BASE/mcp-servers/$SID_A" -Method Put -Headers $H -ContentType "application/json" `
    -Body (@{ user_description = "Renamed via API." } | ConvertTo-Json)
Show "9a. update description" @{ user_description = $upd.user_description }
$disc = Invoke-RestMethod -Uri "$BASE/mcp-servers/$SID_A/discover" -Method Post -Headers $H
Show "9b. re-discover" @{ status = $disc.status; tool_count = $disc.tool_count }

# 10) AGENT-USES-MCP — multi-agent chat path ---------------------------------
$session = Invoke-RestMethod -Uri "$BASE/chat/session" -Method Post -Headers $H
$THREAD = $session.thread_id
Show "10a. chat session" @{ thread_id = $THREAD; agents = $session.available_agents.name }
$msg = Invoke-RestMethod -Uri "$BASE/chat/message" -Method Post -Headers $H -ContentType "application/json" `
    -Body (@{ thread_id = $THREAD; message = "Fetch https://example.com and tell me the page title in one short sentence." } | ConvertTo-Json)
Show "10b. chat reply (should mention 'Example Domain')" @{ response = $msg.response }

# 11) AGENT-USES-MCP — direct single-agent path ------------------------------
$direct = Invoke-RestMethod -Uri "$BASE/chat" -Method Post -Headers $H -ContentType "application/json" `
    -Body (@{ agent_id = $AGENT; message = "Fetch https://example.com and give me its title." } | ConvertTo-Json)
Show "11. direct chat reply" @{ reply = $direct.reply }

# 12) Delete -> 404 after -----------------------------------------------------
Invoke-RestMethod -Uri "$BASE/mcp-servers/$SID_A" -Method Delete -Headers $H | Out-Null
Invoke-RestMethod -Uri "$BASE/mcp-servers/$SID_B" -Method Delete -Headers $H | Out-Null
ExpectFail "12. GET deleted -> 404" { Invoke-RestMethod -Uri "$BASE/mcp-servers/$SID_A" -Headers $H }
$after = (Invoke-RestMethod -Uri "$BASE/mcp-servers/agent/$AGENT" -Headers $H).items
Show "12b. list-by-agent after delete (should be empty)" @{ count = $after.Count }

Write-Host "`nDONE — full MCP flow exercised against the live API." -ForegroundColor Green
