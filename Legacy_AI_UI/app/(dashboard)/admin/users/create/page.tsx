'use client'

import { UserCreateForm } from '@/components/users/user-create-form'

export default function CreateUserPage() {
  return <UserCreateForm successPath="/admin/users" cancelPath="/admin/users" />
}
