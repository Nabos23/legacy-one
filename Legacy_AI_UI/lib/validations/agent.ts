import { z } from 'zod'

export const createAgentSchema = z.object({
  name: z.string().min(2, 'Name must be at least 2 characters'),
  description: z.string().optional(),
  prompt: z.string().min(10, 'System prompt must be at least 10 characters'),
  guardrails: z.string().min(10, 'Guardrails must be at least 10 characters'),
  tool_ids: z.array(z.string()).optional(),
})

export type CreateAgentInput = z.infer<typeof createAgentSchema>
