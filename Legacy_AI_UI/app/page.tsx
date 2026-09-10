import type { Metadata } from 'next'
import { Landing } from '@/components/landing/landing'

export const metadata: Metadata = {
  title: 'ONE-AI | Build, orchestrate and scale AI agents',
  description:
    'The enterprise control plane to design, connect tools, trace and govern autonomous AI agents across your organization, securely and at scale.',
}

export default function HomePage() {
  return <Landing />
}
