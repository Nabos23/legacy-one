import { isConnectorLogoId } from '@/components/connectors/connector-logo'

export interface AgentBrandIcon {
  id: string
  label: string
}

export interface AgentBrandCategory {
  title: string
  brands: AgentBrandIcon[]
}

/** Platform brand icons — same provider IDs as connector logos (Gmail, Slack, etc.). */
export const AGENT_BRAND_CATEGORIES: AgentBrandCategory[] = [
  {
    title: 'Email',
    brands: [
      { id: 'gmail', label: 'Gmail' },
      { id: 'outlook', label: 'Outlook' },
    ],
  },
  {
    title: 'Messaging & Chat',
    brands: [
      { id: 'slack', label: 'Slack' },
      { id: 'teams', label: 'Microsoft Teams' },
      { id: 'google-meet', label: 'Google Meet' },
      { id: 'telegram', label: 'Telegram' },
      { id: 'discord', label: 'Discord' },
      { id: 'whatsapp', label: 'WhatsApp' },
      { id: 'zoom', label: 'Zoom' },
    ],
  },
  {
    title: 'Cloud & Files',
    brands: [
      { id: 'google-drive', label: 'Google Drive' },
      { id: 'onedrive', label: 'OneDrive' },
      { id: 'dropbox', label: 'Dropbox' },
      { id: 'box', label: 'Box' },
      { id: 'sharepoint', label: 'SharePoint' },
      { id: 'google-cloud-storage', label: 'Google Cloud Storage' },
      { id: 'aws-s3', label: 'Amazon S3' },
    ],
  },
  {
    title: 'Productivity & Docs',
    brands: [
      { id: 'google-calendar', label: 'Google Calendar' },
      { id: 'google-sheets', label: 'Google Sheets' },
      { id: 'excel', label: 'Microsoft Excel' },
      { id: 'word', label: 'Microsoft Word' },
      { id: 'notion', label: 'Notion' },
      { id: 'airtable', label: 'Airtable' },
      { id: 'confluence', label: 'Confluence' },
      { id: 'docusign', label: 'DocuSign' },
    ],
  },
  {
    title: 'CRM & Support',
    brands: [
      { id: 'hubspot', label: 'HubSpot' },
      { id: 'salesforce', label: 'Salesforce' },
      { id: 'pipedrive', label: 'Pipedrive' },
      { id: 'zoho-crm', label: 'Zoho CRM' },
      { id: 'intercom', label: 'Intercom' },
      { id: 'zendesk', label: 'Zendesk' },
      { id: 'servicenow', label: 'ServiceNow' },
    ],
  },
  {
    title: 'Project Management',
    brands: [
      { id: 'jira', label: 'Jira' },
      { id: 'clickup', label: 'ClickUp' },
      { id: 'asana', label: 'Asana' },
      { id: 'monday', label: 'Monday.com' },
      { id: 'linear', label: 'Linear' },
    ],
  },
  {
    title: 'Developer Tools',
    brands: [
      { id: 'github', label: 'GitHub' },
      { id: 'gitlab', label: 'GitLab' },
      { id: 'sentry', label: 'Sentry' },
      { id: 'datadog', label: 'Datadog' },
      { id: 'pagerduty', label: 'PagerDuty' },
    ],
  },
  {
    title: 'Finance & Payments',
    brands: [
      { id: 'stripe', label: 'Stripe' },
      { id: 'paypal', label: 'PayPal' },
      { id: 'quickbooks', label: 'QuickBooks' },
      { id: 'xero', label: 'Xero' },
      { id: 'freshbooks', label: 'FreshBooks' },
      { id: 'wave', label: 'Wave' },
    ],
  },
  {
    title: 'Marketing & Social',
    brands: [
      { id: 'mailchimp', label: 'Mailchimp' },
      { id: 'sendgrid', label: 'SendGrid' },
      { id: 'linkedin', label: 'LinkedIn' },
      { id: 'twitter', label: 'Twitter / X' },
      { id: 'facebook', label: 'Facebook' },
      { id: 'instagram', label: 'Instagram' },
      { id: 'tiktok', label: 'TikTok' },
      { id: 'google-analytics', label: 'Google Analytics' },
    ],
  },
  {
    title: 'HR & Freelance',
    brands: [
      { id: 'bamboohr', label: 'BambooHR' },
      { id: 'greenhouse', label: 'Greenhouse' },
      { id: 'upwork', label: 'Upwork' },
      { id: 'fiverr', label: 'Fiverr' },
    ],
  },
  {
    title: 'E-commerce & Design',
    brands: [
      { id: 'shopify', label: 'Shopify' },
      { id: 'figma', label: 'Figma' },
    ],
  },
  {
    title: 'Health & Fitness',
    brands: [
      { id: 'fitbit', label: 'Fitbit' },
      { id: 'strava', label: 'Strava' },
      { id: 'withings', label: 'Withings' },
    ],
  },
  {
    title: 'Communication APIs',
    brands: [{ id: 'twilio', label: 'Twilio' }],
  },
]

export const DEFAULT_BRAND_ICON_ID = 'gmail'

export const ALL_BRAND_ICONS = AGENT_BRAND_CATEGORIES.flatMap(category => category.brands)

export const BRAND_ICON_COUNT = ALL_BRAND_ICONS.length

const BRAND_BY_ID = new Map(ALL_BRAND_ICONS.map(brand => [brand.id, brand] as const))

export function isBrandIconId(id: string | null | undefined): id is string {
  return !!id && isConnectorLogoId(id) && BRAND_BY_ID.has(id)
}

export function getBrandIcon(id: string): AgentBrandIcon | undefined {
  return BRAND_BY_ID.get(id)
}
