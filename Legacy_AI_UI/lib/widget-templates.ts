import type {
  LeadField,
  WidgetAvailabilityInput,
  WidgetBehaviorInput,
  WidgetBrandingInput,
  WidgetTriggersInput,
} from '@/types'

export interface WidgetTemplate {
  key: string
  label: string
  description: string
  /** Pre-filled state applied over the blank defaults when the template is
   * picked. Every field stays fully editable afterwards. */
  branding?: WidgetBrandingInput
  behavior?: WidgetBehaviorInput
  triggers?: WidgetTriggersInput
  availability?: WidgetAvailabilityInput
  leadFields?: LeadField[]
}

const BUSINESS_HOURS_SCHEDULE: WidgetAvailabilityInput['schedule'] = {
  mon: { enabled: true, start: '09:00', end: '17:00' },
  tue: { enabled: true, start: '09:00', end: '17:00' },
  wed: { enabled: true, start: '09:00', end: '17:00' },
  thu: { enabled: true, start: '09:00', end: '17:00' },
  fri: { enabled: true, start: '09:00', end: '17:00' },
}

/** Starting-point templates shown at the top of the create form. "Blank" is
 * the no-op default; the others pre-fill copy, behavior, lead fields, and
 * triggers for a common use case. Colors are left to the theme presets. */
export const WIDGET_TEMPLATES: WidgetTemplate[] = [
  {
    key: 'blank',
    label: 'Blank',
    description: 'Start from the plain defaults and configure everything yourself.',
  },
  {
    key: 'support',
    label: 'Support',
    description: 'Help-desk copy, business hours, and feedback-friendly tone.',
    branding: {
      header_title: 'Support',
      header_subtitle: 'We usually reply in a few minutes',
      greeting_message: 'Hi there! How can we help you today?',
      input_placeholder: 'Describe your issue…',
      quick_replies: ['I need help with my account', 'Report a problem', 'Talk to a human'],
    },
    behavior: {
      response_language: 'auto',
      tone_instructions:
        'Be warm, patient, and solution-oriented. Ask clarifying questions when the issue is ambiguous, and invite the visitor to rate the answer when the problem is resolved.',
      welcome_sound: false,
    },
    availability: {
      enabled: true,
      timezone: 'UTC',
      schedule: BUSINESS_HOURS_SCHEDULE,
      offline_message: "We're offline right now. Leave a message and we'll get back to you on the next business day.",
    },
  },
  {
    key: 'sales',
    label: 'Sales & Leads',
    description: 'Lead capture (name + email) with a lead-gen greeting and quick replies.',
    branding: {
      header_title: 'Chat with sales',
      header_subtitle: 'Questions about pricing or plans?',
      greeting_message: "Hi! Happy to help you find the right plan. What brings you here today?",
      input_placeholder: 'Ask about pricing, plans, demos…',
      quick_replies: ['What are your pricing plans?', 'Book a demo', 'Compare plans'],
    },
    behavior: {
      response_language: 'auto',
      tone_instructions:
        'Be enthusiastic but honest. Focus on understanding what the visitor needs before recommending a plan, and offer to connect them with the sales team for anything custom.',
      welcome_sound: false,
    },
    leadFields: [
      { field_name: 'name', label: 'Your name', field_type: 'text', required: true },
      { field_name: 'email', label: 'Work email', field_type: 'email', required: true },
    ],
    triggers: {
      auto_open: false,
      auto_open_delay_ms: 4000,
      open_on_scroll_percent: null,
      targeted_greetings: [
        { path_pattern: '/pricing*', greeting: 'Questions about pricing? Ask away — or grab a demo.' },
      ],
    },
  },
  {
    key: 'docs',
    label: 'Docs Assistant',
    description: 'Minimal, mono-flavored look with documentation quick replies.',
    branding: {
      header_title: 'Docs assistant',
      header_subtitle: '',
      greeting_message: 'Ask me anything about the docs — I can point you to the right page.',
      input_placeholder: 'Search the docs…',
      font_family: "'Courier New', Courier, monospace",
      show_branding: false,
      quick_replies: ['How do I get started?', 'Show me the API reference', 'Authentication guide'],
    },
    behavior: {
      response_language: 'auto',
      tone_instructions:
        'Be concise and technical. Prefer code examples and direct links to the relevant documentation section over long prose.',
      welcome_sound: false,
    },
  },
]
