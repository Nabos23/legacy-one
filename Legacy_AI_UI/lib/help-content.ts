import type { LucideIcon } from 'lucide-react'
import {
  Bot, Wrench, Package, Plug, PlugZap, Database, Terminal, Activity,
  Users, Building2, ShieldCheck, Settings,
} from 'lucide-react'

export interface HelpTopic {
  category: string
  icon: LucideIcon
  color: 'primary' | 'success' | 'warning' | 'danger' | 'info' | 'neutral'
  title: string
  description: string
  href?: string
}

/** Topics available to every workspace member. */
export const CLIENT_HELP_TOPICS: HelpTopic[] = [
  {
    category: 'Agents',
    icon: Bot,
    color: 'primary',
    title: 'Building an agent',
    description:
      'Use the Agent Wizard to name your agent, write its system prompt, and pick which Tools, Connectors and MCP servers it can call. A supervisor agent can route work to specialist sub-agents automatically.',
    href: '/client/agents/create',
  },
  {
    category: 'Agents',
    icon: Bot,
    color: 'primary',
    title: 'Active / inactive agents',
    description:
      'Toggle an agent inactive to stop it from running without deleting its configuration — useful while you iterate on a prompt or investigate an issue.',
    href: '/client/agents',
  },
  {
    category: 'Tools',
    icon: Wrench,
    color: 'info',
    title: 'Tools vs. the Tool Registry',
    description:
      'The Tool Registry holds reusable templates (a database query, an HTTP call, a RAG source). A "Tool" is that template configured and attached to one specific agent — the same template can back many tools.',
    href: '/client/tools',
  },
  {
    category: 'Connectors',
    icon: PlugZap,
    color: 'success',
    title: 'Connecting third-party services',
    description:
      'Authenticate a service (Slack, Gmail, Notion, GitHub, and 50+ others) with OAuth or an API key, then attach it to an agent. Connected services are exposed to the agent as callable tools — it can send, update, or fetch data, not just read it.',
    href: '/client/connectors',
  },
  {
    category: 'Data',
    icon: Database,
    color: 'warning',
    title: 'Database Connections',
    description:
      'Store an encrypted connection string for SQL, MongoDB, or other databases. ONE-AI previews the schema and lets you describe each table so agents query it accurately and safely.',
    href: '/client/db-connections',
  },
  {
    category: 'Testing',
    icon: Terminal,
    color: 'neutral',
    title: 'Playground',
    description:
      'Chat directly with any of your agents outside of production. Ideal for testing prompt changes, new tools, or connector behavior before rolling them out.',
    href: '/client/playground',
  },
  {
    category: 'Observability',
    icon: Activity,
    color: 'info',
    title: 'Tracing & sessions',
    description:
      'Every agent run is captured as a trace — see each step, tool call, token count, and latency. Group traces by session to follow a full conversation end-to-end.',
    href: '/client/tracing',
  },
  {
    category: 'Team',
    icon: Users,
    color: 'primary',
    title: 'Users & roles',
    description:
      'Invite teammates and assign a role — User, Org Manager, or Org Admin — that determines what they can view and change. Role permissions are enforced by the backend, not just hidden in the UI.',
    href: '/client/users',
  },
  {
    category: 'Account',
    icon: Settings,
    color: 'neutral',
    title: 'Your account',
    description:
      'Update your display name and profile picture, change your password, manage notification preferences, and review which services are connected to your account from Settings.',
    href: '/client/settings',
  },
]

/** Additional topics only relevant to the platform-admin dashboard. */
export const ADMIN_HELP_TOPICS: HelpTopic[] = [
  {
    category: 'Organizations',
    icon: Building2,
    color: 'primary',
    title: 'Managing organizations',
    description:
      'Create organizations, assign their administrators, and oversee every tenant on the platform from one place. Each organization is fully isolated — agents, tools, and data never cross org boundaries.',
    href: '/admin/organizations',
  },
  {
    category: 'Tools',
    icon: Package,
    color: 'info',
    title: 'Curating the Tool Registry',
    description:
      'Define the catalog of tool templates every organization can use — database, HTTP, RAG, or custom types — with a JSON schema for their configurable fields.',
    href: '/admin/tool-registry',
  },
  {
    category: 'Tools',
    icon: Plug,
    color: 'warning',
    title: 'MCP Servers',
    description:
      'Register Model Context Protocol servers (stdio, SSE, or WebSocket) as an additional tool source. Discover their available tools and attach them to agents — distinct from Connectors (OAuth SaaS logins) and the Tool Registry (custom functions).',
    href: '/admin/mcp-servers',
  },
  {
    category: 'Connectors',
    icon: PlugZap,
    color: 'success',
    title: 'Connector visibility',
    description:
      'Control which of the 55+ built-in connectors are visible to organizations, independent of whether they are currently active in the underlying registry.',
    href: '/admin/connectors',
  },
  {
    category: 'Team',
    icon: ShieldCheck,
    color: 'danger',
    title: 'Platform-wide RBAC',
    description:
      'Super admins can see and manage users across every organization, not just their own. Role permissions (create_agent, view_trace, etc.) are resolved server-side per request.',
    href: '/admin/users',
  },
  ...CLIENT_HELP_TOPICS,
]

export interface HelpFaq {
  q: string
  a: string
}

/** Common usage questions, shared by both dashboards. */
export const CLIENT_FAQS: HelpFaq[] = [
  {
    q: "What's the difference between Tools, Connectors, and MCP Servers?",
    a: 'Tools are custom functions or API calls you register yourself via the Tool Registry. Connectors are pre-built OAuth/API-key integrations with real SaaS products (Slack, Gmail, Notion...). MCP Servers expose tools from any Model Context Protocol-compatible server. All three end up as callable tools on an agent — they just differ in where the capability comes from.',
  },
  {
    q: 'Why can’t an agent use a connector I just connected?',
    a: 'Connecting a service authorizes your account, but the agent still needs that connector explicitly attached in its configuration (the "Connectors" step of the Agent Wizard). Only connectors with an active connection will actually execute at runtime.',
  },
  {
    q: 'Why can’t I change my email, organization, or role myself?',
    a: 'Those fields are considered identity/security-sensitive and are locked to admin changes to prevent account takeover or accidental privilege changes. Use "Request Changes" in Settings to ask your administrator.',
  },
  {
    q: 'What happens when I mark an agent inactive?',
    a: 'An inactive agent stops responding to new requests but keeps its full configuration, tools, and history intact. It’s reversible at any time and is the recommended way to pause an agent instead of deleting it.',
  },
  {
    q: 'Where do I see what an agent actually did?',
    a: 'Open Observability (Tracing). Every run produces a trace with each step, tool call, token count, and latency, grouped into sessions so you can follow a full conversation.',
  },
  {
    q: 'Do my notification preferences sync across devices?',
    a: 'Not yet — they’re currently saved to the browser you set them in via local storage, not to your account on the server.',
  },
]

export const ADMIN_FAQS: HelpFaq[] = [
  {
    q: 'What’s the difference between the Tool Registry and MCP Servers?',
    a: 'The Tool Registry is a catalog of tool templates you define yourself (a SQL query shape, an HTTP call, a RAG source). MCP Servers are external processes speaking the Model Context Protocol that expose their own tools — you register the server, not the individual tool.',
  },
  {
    q: 'Are organizations isolated from each other?',
    a: 'Yes. Agents, tools, connectors, and data connections are always scoped to a single organization_id. Only a super_admin can see or act across multiple organizations.',
  },
  {
    q: 'What does toggling a connector’s visibility do?',
    a: 'It hides or shows that connector in the org-facing Connectors page without touching whether it’s active in the registry — useful for staged rollouts of a new integration.',
  },
  {
    q: 'How are role permissions enforced?',
    a: 'Every protected endpoint checks the caller’s resolved permissions server-side (e.g. create_agent, view_trace) — hiding a button in the UI is a convenience, not the actual security boundary.',
  },
]

export interface GlossaryTerm {
  term: string
  definition: string
}

/** Core vocabulary used across the product — shared by both dashboards. */
export const GLOSSARY: GlossaryTerm[] = [
  { term: 'Agent', definition: 'An LLM configured with a system prompt and a set of tools it can call to complete tasks.' },
  { term: 'Supervisor', definition: 'An agent that routes an incoming request to the right specialist sub-agent instead of handling it directly.' },
  { term: 'Tool', definition: 'A specific capability attached to one agent — backed by a Tool Registry template, a Connector, or an MCP server.' },
  { term: 'Tool Registry', definition: 'The catalog of reusable tool templates (database, HTTP, RAG, custom) that a Tool is configured from.' },
  { term: 'Connector', definition: 'A pre-built OAuth or API-key integration with a real third-party service (Slack, Gmail, Notion, and 50+ others).' },
  { term: 'MCP Server', definition: 'An external process speaking the Model Context Protocol, registered so its tools become available to agents.' },
  { term: 'Trace', definition: 'A recorded run of an agent — every step, tool call, token, and the latency of each.' },
  { term: 'Session', definition: 'A group of traces belonging to the same ongoing conversation.' },
  { term: 'Playground', definition: 'A sandbox to chat with an agent directly, outside of production, to test prompts and tools.' },
  { term: 'RBAC', definition: 'Role-Based Access Control — permissions (like create_agent) are resolved from a user’s role on every request.' },
]
