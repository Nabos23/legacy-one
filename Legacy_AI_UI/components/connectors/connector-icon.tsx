'use client'

import { cn } from '@/lib/utils'

const PROVIDER_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  // Storage
  'google-drive':         { bg: 'bg-blue-500',    text: 'text-white', label: 'GD' },
  'onedrive':             { bg: 'bg-cyan-600',    text: 'text-white', label: 'OD' },
  'dropbox':              { bg: 'bg-blue-600',    text: 'text-white', label: 'DB' },
  'box':                  { bg: 'bg-blue-800',    text: 'text-white', label: 'BX' },
  'sharepoint':           { bg: 'bg-teal-600',    text: 'text-white', label: 'SP' },
  'google-cloud-storage': { bg: 'bg-orange-500',  text: 'text-white', label: 'GS' },
  'aws-s3':               { bg: 'bg-orange-600',  text: 'text-white', label: 'S3' },
  // Email
  'gmail':                { bg: 'bg-red-500',     text: 'text-white', label: 'GM' },
  'outlook':              { bg: 'bg-blue-700',    text: 'text-white', label: 'OL' },
  // Messaging
  'slack':                { bg: 'bg-purple-600',  text: 'text-white', label: 'SL' },
  'teams':                { bg: 'bg-indigo-600',  text: 'text-white', label: 'TM' },
  'telegram':             { bg: 'bg-sky-500',     text: 'text-white', label: 'TG' },
  'discord':              { bg: 'bg-indigo-500',  text: 'text-white', label: 'DC' },
  'whatsapp':             { bg: 'bg-green-500',   text: 'text-white', label: 'WA' },
  // Productivity
  'google-calendar':      { bg: 'bg-blue-400',    text: 'text-white', label: 'GC' },
  'google-sheets':        { bg: 'bg-green-600',   text: 'text-white', label: 'GS' },
  'notion':               { bg: 'bg-gray-900',    text: 'text-white', label: 'NT' },
  'airtable':             { bg: 'bg-yellow-500',  text: 'text-white', label: 'AT' },
  // CRM
  'hubspot':              { bg: 'bg-orange-500',  text: 'text-white', label: 'HS' },
  'salesforce':           { bg: 'bg-sky-600',     text: 'text-white', label: 'SF' },
  'pipedrive':            { bg: 'bg-green-600',   text: 'text-white', label: 'PD' },
  // Support
  'zendesk':              { bg: 'bg-green-700',   text: 'text-white', label: 'ZD' },
  'intercom':             { bg: 'bg-blue-500',    text: 'text-white', label: 'IC' },
  // Developer Tools
  'jira':                 { bg: 'bg-blue-600',    text: 'text-white', label: 'JI' },
  'github':               { bg: 'bg-gray-900',    text: 'text-white', label: 'GH' },
  // Payments
  'stripe':               { bg: 'bg-indigo-600',  text: 'text-white', label: 'ST' },
  // Communication
  'twilio':               { bg: 'bg-red-600',     text: 'text-white', label: 'TW' },
  // Project Management
  'asana':                { bg: 'bg-pink-600',    text: 'text-white', label: 'AS' },
  'monday':               { bg: 'bg-yellow-500',  text: 'text-white', label: 'MN' },
  // Finance
  'quickbooks':           { bg: 'bg-green-500',   text: 'text-white', label: 'QB' },
  // Documents
  'docusign':             { bg: 'bg-yellow-600',  text: 'text-white', label: 'DS' },
  // ITSM
  'servicenow':           { bg: 'bg-green-500',   text: 'text-white', label: 'SN' },
  // Analytics
  'google-analytics':     { bg: 'bg-orange-500',  text: 'text-white', label: 'GA' },
  // Design
  'figma':                { bg: 'bg-purple-500',  text: 'text-white', label: 'FG' },
  // E-Commerce
  'shopify':              { bg: 'bg-green-600',   text: 'text-white', label: 'SH' },
  // Knowledge Base
  'confluence':           { bg: 'bg-blue-600',    text: 'text-white', label: 'CF' },
  // Freelance
  'upwork':               { bg: 'bg-green-600',   text: 'text-white', label: 'UW' },
  'fiverr':               { bg: 'bg-emerald-500', text: 'text-white', label: 'FV' },
  // Finance (extended)
  'xero':                 { bg: 'bg-sky-500',     text: 'text-white', label: 'XR' },
  'paypal':               { bg: 'bg-blue-800',    text: 'text-white', label: 'PP' },
  'freshbooks':           { bg: 'bg-blue-600',    text: 'text-white', label: 'FB' },
  'wave':                 { bg: 'bg-blue-700',    text: 'text-white', label: 'WV' },
  // Health
  'fitbit':               { bg: 'bg-teal-500',    text: 'text-white', label: 'FT' },
  'strava':               { bg: 'bg-orange-600',  text: 'text-white', label: 'SV' },
  'withings':             { bg: 'bg-slate-700',   text: 'text-white', label: 'WH' },
  // Developer Tools (extended)
  'gitlab':               { bg: 'bg-orange-500',  text: 'text-white', label: 'GL' },
  'sentry':               { bg: 'bg-purple-700',  text: 'text-white', label: 'SE' },
  // Project Management (extended)
  'linear':               { bg: 'bg-indigo-500',  text: 'text-white', label: 'LN' },
  // ITSM (extended)
  'pagerduty':            { bg: 'bg-green-500',   text: 'text-white', label: 'PG' },
  // Video
  'zoom':                 { bg: 'bg-blue-500',    text: 'text-white', label: 'ZM' },
  // Marketing
  'mailchimp':            { bg: 'bg-yellow-400',  text: 'text-gray-900', label: 'MC' },
  'sendgrid':             { bg: 'bg-blue-500',    text: 'text-white', label: 'SG' },
  // Social Media
  'linkedin':             { bg: 'bg-blue-700',    text: 'text-white', label: 'LI' },
  'twitter':              { bg: 'bg-gray-900',    text: 'text-white', label: 'TX' },
  'facebook':             { bg: 'bg-blue-600',    text: 'text-white', label: 'FB' },
  'instagram':            { bg: 'bg-pink-600',    text: 'text-white', label: 'IG' },
  'tiktok':               { bg: 'bg-gray-900',    text: 'text-white', label: 'TT' },
  // CRM (extended)
  'zoho-crm':             { bg: 'bg-red-500',     text: 'text-white', label: 'ZC' },
  // HR
  'bamboohr':             { bg: 'bg-green-600',   text: 'text-white', label: 'BH' },
  'greenhouse':           { bg: 'bg-emerald-600', text: 'text-white', label: 'GR' },
  // Monitoring
  'datadog':              { bg: 'bg-purple-600',  text: 'text-white', label: 'DD' },
}

const FALLBACK = { bg: 'bg-gray-500', text: 'text-white', label: '??' }

interface ConnectorIconProps {
  providerId: string
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

const sizes = {
  sm:  'w-8 h-8 rounded-lg text-[10px]',
  md:  'w-11 h-11 rounded-xl text-[12px]',
  lg:  'w-14 h-14 rounded-2xl text-[14px]',
}

export function ConnectorIcon({ providerId, size = 'md', className }: ConnectorIconProps) {
  const style = PROVIDER_STYLES[providerId] ?? FALLBACK
  return (
    <div
      className={cn(
        'flex items-center justify-center font-bold shrink-0',
        style.bg,
        style.text,
        sizes[size],
        className,
      )}
    >
      {style.label}
    </div>
  )
}
