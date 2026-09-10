'use client'

import { UserCreateForm } from '@/components/users/user-create-form'

export default function CreateUserPage() {
  return <UserCreateForm successPath="/client/users" cancelPath="/client/users" />
}
