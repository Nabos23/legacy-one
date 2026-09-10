import { api } from './client'

export interface PromptGeneratorResponse {
  prompt: string
  guardrails?: string
  model: string
}

export const promptGeneratorApi = {
  generate: (agent_name: string, agent_description: string) =>
    api.post<PromptGeneratorResponse>('/generate-prompt', {
      agent_name,
      agent_description,
    }),
  generateForAgent: (agent_id: string) =>
    api.post<PromptGeneratorResponse>('/generate-prompt', { agent_id }),
}
