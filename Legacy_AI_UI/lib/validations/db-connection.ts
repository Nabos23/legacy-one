import { z } from 'zod'

const dbConnectionMetadataSchema = z.object({
  name: z.string().min(1, 'Connection name is required').optional(),
  connection_type: z.string().min(1, 'Connection type is required').optional(),
})

export const createDbConnectionSchema = z.object({
  organization_id: z.string().min(1, 'Organization ID is required'),
  ...dbConnectionMetadataSchema.shape,
  connection_string: z
    .string()
    .min(10, 'Connection string must be at least 10 characters'),
})

export const firebaseDbConnectionSchema = z.object({
  organization_id: z.string().min(1, 'Organization ID is required'),
  ...dbConnectionMetadataSchema.shape,
  firebase: z.object({
    service_account: z.record(z.string(), z.unknown()),
    database_id: z.string().min(1, 'Database ID is required').default('(default)'),
  }),
})

export const previewDbConnectionSchema = createDbConnectionSchema

export type CreateDbConnectionInput = z.infer<typeof createDbConnectionSchema>
export type FirebaseDbConnectionInput = z.infer<typeof firebaseDbConnectionSchema>
export type PreviewDbConnectionInput = z.infer<typeof previewDbConnectionSchema>
