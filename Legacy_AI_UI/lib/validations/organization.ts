import { z } from 'zod'

export const createOrganizationSchema = z.object({
  name: z.string().min(2, 'Name must be at least 2 characters'),
  description: z.string().optional(),
})

export type CreateOrganizationInput = z.infer<typeof createOrganizationSchema>

export const createUserSchema = z.object({
  name: z.string().min(2, 'Name must be at least 2 characters'),
  email: z.string().email('Invalid email address'),
  password: z.string().min(6, 'Password must be at least 6 characters'),
  // Role names are DB-defined (role_permissions collection) and validated server-side;
  // don't hardcode an enum of allowed values here.
  role: z.string().min(1).optional(),
  organization_id: z.string().optional(),
})

export type CreateUserInput = z.infer<typeof createUserSchema>
