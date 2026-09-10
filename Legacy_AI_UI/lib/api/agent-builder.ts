import { api } from './client'

export interface BuilderOption { value: string; label: string; description?: string }
export interface BuilderQuestion { id: string; text: string; options: BuilderOption[] }
export interface AgentBlueprint {
  name: string
  description: string
  system_prompt: string
  guardrails: string
  connector_ids: string[]
  connector_names: string[]
  mcp_registry_keys: string[]
  mcp_names: string[]
  tool_ids: string[]
  tool_names: string[]
  db_tool_ids: string[]
  requires_db_connection: boolean
  questions: BuilderQuestion[]
  ready: boolean
  unmatched_capabilities: string[]
  available_options: BuilderOption[]
}

export const agentBuilderApi = {
  blueprint: (prompt: string, answers: Record<string, string> = {}) =>
    api.post<AgentBlueprint>('/agent-builder/blueprint', { prompt, answers }),
}
