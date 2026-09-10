'use client'

import { McpServersManager } from '@/components/mcp/mcp-servers-manager'

export default function ClientMcpServersPage() {
  return (
    <McpServersManager
      title="MCP Servers"
      description="Connect external MCP servers — stdio, HTTP, SSE, WebSocket, or OAuth. Attach individual tools to your agents from each agent's MCP Servers step."
    />
  )
}
