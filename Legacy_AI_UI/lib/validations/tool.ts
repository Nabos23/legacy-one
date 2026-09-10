import { z } from 'zod'

export const createToolSchema = z.object({
  organization_id: z.string().min(1, 'Organization ID is required'),
  agent_id: z.string().min(1, 'Agent ID is required'),
  tool_id: z.string().min(1, 'Tool registry ID is required'),
  user_description: z
    .string()
    .min(10, 'Tool description must be at least 10 characters'),
  name: z.string().optional(),
  enabled: z.boolean().optional(),
  db_conn_id: z.string().optional(),
})

export type CreateToolInput = z.infer<typeof createToolSchema>
