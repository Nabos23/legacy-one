import * as React from 'react'
import { cn } from '@/lib/utils'

interface LogoProps {
  size?: number
  className?: string
}

// ── Google Drive ──────────────────────────────────────────────────────────────
const GoogleDriveLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 87.3 78" xmlns="http://www.w3.org/2000/svg">
    <path d="m6.6 66.85 3.85 6.65c.8 1.4 1.95 2.5 3.3 3.3l13.75-23.8h-27.5c0 1.55.4 3.1 1.2 4.5z" fill="#0066da"/>
    <path d="m43.65 25-13.75-23.8c-1.35.8-2.5 1.9-3.3 3.3l-25.4 44a9.06 9.06 0 0 0-1.2 4.5h27.5z" fill="#00ac47"/>
    <path d="m73.55 76.8c1.35-.8 2.5-1.9 3.3-3.3l1.6-2.75 7.65-13.25c.8-1.4 1.2-2.95 1.2-4.5h-27.5l5.85 11.5z" fill="#ea4335"/>
    <path d="m43.65 25 13.75-23.8c-1.35-.8-2.9-1.2-4.5-1.2h-18.5c-1.6 0-3.15.45-4.5 1.2z" fill="#00832d"/>
    <path d="m59.8 53h-32.3l-13.75 23.8c1.35.8 2.9 1.2 4.5 1.2h50.8c1.6 0 3.15-.45 4.5-1.2z" fill="#2684fc"/>
    <path d="m73.4 26.5-12.7-22c-.8-1.4-1.95-2.5-3.3-3.3l-13.75 23.8 16.15 28h27.45c0-1.55-.4-3.1-1.2-4.5z" fill="#ffba00"/>
  </svg>
)

// ── OneDrive ──────────────────────────────────────────────────────────────────
const OneDriveLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <path d="M28 20.5c1.4-3.3 4.6-5.5 8.3-5.5 5 0 9 4 9 9 0 .4 0 .8-.1 1.2C47.1 26 48 27.4 48 29c0 2.8-2.2 5-5 5H14c-3.9 0-7-3.1-7-7 0-3.7 2.8-6.7 6.4-7C14.1 14.9 18.5 12 23.5 12c2.7 0 5.1.9 7 2.5" fill="#0078d4"/>
    <path d="M6.5 26C5.6 24.8 5 23.4 5 22c0-3.9 3.1-7 7-7 .3 0 .6 0 .9.1C14.1 11.9 18.5 9 23.5 9c4.3 0 8.1 2 10.6 5.1-1.1-.1-2.2 0-3.2.2-1.4-1.5-3.5-2.3-5.7-2.3-4.2 0-7.7 3-8.3 7-.2 0-.5-.1-.7-.1-2.4 0-4.4 1.5-5.2 3.6L6.5 26z" fill="#1490df"/>
    <path d="M43 25.2C42.7 25.1 42.4 25 42 25c-.6 0-1.1.1-1.6.3.1-.4.1-.9.1-1.3 0-4.4-3.6-8-8-8-3 0-5.6 1.7-7 4.1-.8-.5-1.7-.8-2.7-.8-2.9 0-5.3 2.4-5.3 5.3 0 .2 0 .4.1.6C15.7 25.7 14 27.6 14 30c0 2.8 2.2 5 5 5h24c2.8 0 5-2.2 5-5 0-2.2-1.5-4.1-5-4.8z" fill="#28a8e8"/>
  </svg>
)

// ── Dropbox ───────────────────────────────────────────────────────────────────
const DropboxLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <path d="M12 6L0 13.5l12 7.5 12-7.5zM36 6L24 13.5l12 7.5 12-7.5zM0 28.5L12 36l12-7.5-12-7.5zM36 21l-12 7.5 12 7.5 12-7.5zM12 37.5L24 45l12-7.5-12-7.5z" fill="#0061ff"/>
  </svg>
)

// ── Box ───────────────────────────────────────────────────────────────────────
const BoxLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <circle cx="24" cy="24" r="24" fill="#0061D5"/>
    <path d="M24 14c-2.8 0-5.2 1.5-6.6 3.7C16.1 16.7 14.1 16 12 16c-4.4 0-8 3.6-8 8s3.6 8 8 8c2.1 0 4.1-.8 5.4-2.1V31h3v-7.6c.5.1.9.1 1.6.1s1.1 0 1.6-.1V31h3v-1.1C27.9 31.2 29.9 32 32 32c4.4 0 8-3.6 8-8s-3.6-8-8-8c-2.1 0-4.1.8-5.4 2.1C25.5 16.8 24.8 14 24 14zm0 3c2.8 0 5 2.2 5 5s-2.2 5-5 5-5-2.2-5-5 2.2-5 5-5zm-12 2c2.8 0 5 2.2 5 5s-2.2 5-5 5-5-2.2-5-5 2.2-5 5-5zm24 0c2.8 0 5 2.2 5 5s-2.2 5-5 5-5-2.2-5-5 2.2-5 5-5z" fill="white"/>
  </svg>
)

// ── SharePoint ────────────────────────────────────────────────────────────────
const SharePointLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <circle cx="18" cy="18" r="14" fill="#038387"/>
    <circle cx="30" cy="24" r="13" fill="#1a9ba1"/>
    <circle cx="22" cy="32" r="12" fill="#37c6d0"/>
    <rect x="8" y="30" width="20" height="12" rx="2" fill="#1490df"/>
    <path d="M14 33h8m-8 3h6" stroke="white" strokeWidth="2" strokeLinecap="round"/>
  </svg>
)

// ── Google Cloud Storage ──────────────────────────────────────────────────────
const GoogleCloudStorageLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <path d="M37.9 19.5c-.2-5.7-4.9-10.3-10.7-10.3-4.2 0-7.9 2.4-9.7 6-3.6.4-6.4 3.4-6.4 7.1 0 4 3.2 7.2 7.2 7.2h19.2c3.3 0 6-2.7 6-6 0-3.1-2.4-5.6-5.6-6z" fill="#4285f4"/>
    <path d="M31 30.5h-14l4-6h6z" fill="#aecbfa"/>
    <path d="M17 30.5l4-6h6l4 6" fill="#669df6"/>
    <rect x="19" y="30" width="10" height="8" rx="1" fill="#4285f4"/>
    <path d="M22 34h4" stroke="white" strokeWidth="1.5" strokeLinecap="round"/>
  </svg>
)

// ── AWS S3 ────────────────────────────────────────────────────────────────────
const AWSS3Logo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <path d="M24 6l18 9v18l-18 9L6 33V15z" fill="#e25444"/>
    <path d="M24 6l18 9-18 9L6 15z" fill="#f7a80d"/>
    <path d="M6 15l18 9v18L6 33z" fill="#c7371a"/>
    <path d="M42 15l-18 9v18l18-9z" fill="#e25444"/>
    <text x="24" y="28" textAnchor="middle" fill="white" fontSize="10" fontWeight="bold" fontFamily="sans-serif">S3</text>
  </svg>
)

// ── Gmail ─────────────────────────────────────────────────────────────────────
const GmailLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <path d="M4 10h40v28H4z" fill="#f2f2f2"/>
    <path d="M4 10l20 14L44 10" fill="none" stroke="#ea4335" strokeWidth="4"/>
    <path d="M4 10v28l9-14zM44 10v28l-9-14z" fill="#c5221f"/>
    <path d="M4 38l9-14 11 8 11-8 9 14" fill="#ea4335"/>
    <path d="M13 24L4 10h40L33 24l-9 6z" fill="#ea4335"/>
    <path d="M4 10l20 14L44 10z" fill="#ea4335"/>
    <path d="M4 10h40v4L24 28 4 14z" fill="#ea4335"/>
  </svg>
)

// ── Outlook ───────────────────────────────────────────────────────────────────
const OutlookLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <rect x="2" y="6" width="28" height="36" rx="3" fill="#0078d4"/>
    <rect x="18" y="14" width="28" height="22" rx="2" fill="#28a8e8"/>
    <path d="M18 14l10 11 18-11" fill="none" stroke="white" strokeWidth="1.5"/>
    <ellipse cx="13" cy="24" rx="6" ry="7" fill="white"/>
    <ellipse cx="13" cy="24" rx="4" ry="5" fill="#0078d4"/>
  </svg>
)

// ── Slack ─────────────────────────────────────────────────────────────────────
const SlackLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <path d="M13 30a4 4 0 0 1-4 4 4 4 0 0 1-4-4 4 4 0 0 1 4-4h4z" fill="#e01e5a"/>
    <path d="M15 30a4 4 0 0 1 4-4 4 4 0 0 1 4 4v10a4 4 0 0 1-4 4 4 4 0 0 1-4-4z" fill="#e01e5a"/>
    <path d="M19 13a4 4 0 0 1-4-4 4 4 0 0 1 4-4 4 4 0 0 1 4 4v4z" fill="#36c5f0"/>
    <path d="M19 15a4 4 0 0 1 4 4 4 4 0 0 1-4 4H9a4 4 0 0 1-4-4 4 4 0 0 1 4-4z" fill="#36c5f0"/>
    <path d="M36 19a4 4 0 0 1 4-4 4 4 0 0 1 4 4 4 4 0 0 1-4 4h-4z" fill="#2eb67d"/>
    <path d="M34 19a4 4 0 0 1-4 4 4 4 0 0 1-4-4V9a4 4 0 0 1 4-4 4 4 0 0 1 4 4z" fill="#2eb67d"/>
    <path d="M30 36a4 4 0 0 1 4 4 4 4 0 0 1-4 4 4 4 0 0 1-4-4v-4z" fill="#ecb22e"/>
    <path d="M30 34a4 4 0 0 1-4-4 4 4 0 0 1 4-4h10a4 4 0 0 1 4 4 4 4 0 0 1-4 4z" fill="#ecb22e"/>
  </svg>
)

// ── Microsoft Teams ───────────────────────────────────────────────────────────
const TeamsLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <path d="M28 18h10a4 4 0 0 1 4 4v10a4 4 0 0 1-4 4h-2v6l-8-6V22a4 4 0 0 0-4-4h4z" fill="#5059c9"/>
    <circle cx="35" cy="12" r="5" fill="#5059c9"/>
    <circle cx="22" cy="11" r="7" fill="#7b83eb"/>
    <path d="M8 20h28a4 4 0 0 1 4 4v12a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4V24a4 4 0 0 1 4-4z" fill="#7b83eb"/>
    <path d="M22 24v12M16 24v0m0 0h12" stroke="white" strokeWidth="2.5" strokeLinecap="round"/>
  </svg>
)

// ── Telegram ──────────────────────────────────────────────────────────────────
const TelegramLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <circle cx="24" cy="24" r="22" fill="#2CA5E0"/>
    <path d="M10 24l24-10-6 22-6-8-12-4z" fill="white" opacity=".5"/>
    <path d="M10 24l10 4 2 8 6-8 6-18z" fill="white"/>
    <path d="M10 24l10 4 6-4z" fill="#cee9f6"/>
  </svg>
)

// ── Discord ───────────────────────────────────────────────────────────────────
const DiscordLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <path d="M40.634 8.686A39.645 39.645 0 0 0 31.352 6a27.182 27.182 0 0 0-1.256 2.519 36.718 36.718 0 0 0-10.792 0A27.182 27.182 0 0 0 18.048 6a39.617 39.617 0 0 0-9.283 2.686C3.83 17.225 2.65 25.553 3.24 33.76a39.947 39.947 0 0 0 12.052 5.98 29.028 29.028 0 0 0 2.566-4.09 25.87 25.87 0 0 1-4.038-1.902c.34-.244.67-.497.99-.756 7.786 3.522 16.218 3.522 23.912 0 .322.259.652.512.991.756a25.87 25.87 0 0 1-4.038 1.902 29.028 29.028 0 0 0 2.566 4.09A39.89 39.89 0 0 0 44.76 33.76c.69-9.194-.99-17.455-6.127-25.074zm-22.96 20.022c-2.302 0-4.196-2.074-4.196-4.626 0-2.553 1.848-4.627 4.196-4.627 2.348 0 4.242 2.074 4.196 4.627 0 2.552-1.848 4.626-4.196 4.626zm15.552 0c-2.302 0-4.196-2.074-4.196-4.626 0-2.553 1.848-4.627 4.196-4.627 2.348 0 4.242 2.074 4.196 4.627 0 2.552-1.848 4.626-4.196 4.626z" fill="#5865F2"/>
  </svg>
)

// ── WhatsApp ──────────────────────────────────────────────────────────────────
const WhatsAppLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <circle cx="24" cy="24" r="22" fill="#25D366"/>
    <path d="M24 11c-7.2 0-13 5.8-13 13 0 2.4.6 4.6 1.8 6.5L11 38l7.7-1.8c1.8 1 3.9 1.6 6.3 1.6 7.2 0 13-5.8 13-13S31.2 11 24 11z" fill="white"/>
    <path d="M19.5 17h-.5c-.2 0-.5.1-.8.4l-.7.7c-.9 1-1.1 2.3-.4 3.7l.1.2c.8 1.7 2.2 3.5 3.8 5.1 1.6 1.6 3.4 3 5.1 3.8l.2.1c1.4.7 2.7.5 3.7-.4l.7-.7c.3-.3.4-.6.4-.8v-.4c0-.2-.1-.4-.3-.5l-3-2c-.2-.1-.4-.2-.6-.1l-1.4.5c-.2.1-.5 0-.6-.2-1-1.2-2.1-2.6-2.7-3.7-.1-.2 0-.4.1-.6l.5-1.4c.1-.2 0-.4-.1-.6l-2-3c-.1-.1-.3-.1-.5-.1z" fill="#25D366"/>
  </svg>
)

// ── Google Calendar ───────────────────────────────────────────────────────────
const GoogleCalendarLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <rect x="6" y="10" width="36" height="32" rx="3" fill="white" stroke="#e0e0e0" strokeWidth="1"/>
    <rect x="6" y="10" width="36" height="10" rx="3" fill="#1a73e8"/>
    <rect x="6" y="16" width="36" height="4" fill="#1a73e8"/>
    <circle cx="16" cy="10" r="3" fill="#1a73e8"/>
    <circle cx="32" cy="10" r="3" fill="#1a73e8"/>
    <rect x="14" y="8" width="4" height="6" rx="2" fill="#174ea6"/>
    <rect x="30" y="8" width="4" height="6" rx="2" fill="#174ea6"/>
    <text x="24" y="34" textAnchor="middle" fill="#1a73e8" fontSize="14" fontWeight="bold" fontFamily="sans-serif">31</text>
  </svg>
)

// ── Calendly ──────────────────────────────────────────────────────────────────
const CalendlyLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <rect x="5" y="8" width="38" height="34" rx="6" fill="#006bff"/>
    <rect x="5" y="8" width="38" height="9" rx="6" fill="#00419e"/>
    <circle cx="24" cy="27" r="10" fill="white"/>
    <path d="M20 27l3 3 5.5-6" stroke="#006bff" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
  </svg>
)

// ── Google Sheets ─────────────────────────────────────────────────────────────
const GoogleSheetsLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <path d="M28 4H12a4 4 0 0 0-4 4v32a4 4 0 0 0 4 4h24a4 4 0 0 0 4-4V16L28 4z" fill="#34a853"/>
    <path d="M28 4l12 12H28V4z" fill="#1e7e34" opacity=".7"/>
    <rect x="14" y="22" width="20" height="2" rx="1" fill="white"/>
    <rect x="14" y="27" width="20" height="2" rx="1" fill="white"/>
    <rect x="14" y="32" width="14" height="2" rx="1" fill="white"/>
    <rect x="14" y="22" width="1" height="12" fill="white" opacity=".5"/>
    <rect x="22" y="22" width="1" height="12" fill="white" opacity=".5"/>
    <rect x="30" y="22" width="1" height="12" fill="white" opacity=".5"/>
  </svg>
)

// ── Notion ────────────────────────────────────────────────────────────────────
const NotionLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <rect x="4" y="4" width="40" height="40" rx="6" fill="white" stroke="#e0e0e0" strokeWidth="1"/>
    <path d="M14 12c0-1 .8-1.8 1.7-1.6l18 2.6c.8.1 1.3.8 1.3 1.6v18.5c0 .9-.6 1.6-1.5 1.7l-4 .6c-.9.1-1.7-.5-1.9-1.4L26 26l-8 10.5c-.4.5-1 .7-1.6.6-.8-.1-1.4-.8-1.4-1.6V12z" fill="#1a1a1a"/>
    <path d="M23 14l2 1v16l-2-1V14z" fill="white" opacity=".2"/>
  </svg>
)

// ── Airtable ──────────────────────────────────────────────────────────────────
const AirtableLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <path d="M24 6l20 8v8l-20-8L4 22v-8z" fill="#FCB400"/>
    <path d="M4 22l20 8 .1 12-20-8z" fill="#18BFFF"/>
    <path d="M44 22L24 30l-.1 12 20-8z" fill="#F82B60" opacity=".9"/>
  </svg>
)

// ── HubSpot ───────────────────────────────────────────────────────────────────
const HubSpotLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <circle cx="34" cy="14" r="6" fill="#ff7a59"/>
    <circle cx="34" cy="14" r="3.5" fill="white"/>
    <path d="M22 28a10 10 0 1 0 0-12 10 10 0 0 0 0 12z" fill="#ff7a59"/>
    <circle cx="22" cy="22" r="5" fill="white"/>
    <path d="M28 22h6M34 14v8" stroke="#ff7a59" strokeWidth="2.5" strokeLinecap="round"/>
  </svg>
)

// ── Salesforce ────────────────────────────────────────────────────────────────
const SalesforceLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <path d="M20 10c2.6-2.8 6.3-4.5 10.4-4.5 5.5 0 10.3 3.1 12.8 7.7.8-.3 1.8-.5 2.7-.5 4.4 0 8.1 3.6 8.1 8s-3.6 8-8.1 8c-.3 0-.7 0-1-.1-2 3-5.3 5-9 5-1.7 0-3.3-.4-4.7-1.2-2 4-6.2 6.8-11 6.8-5.5 0-10.2-3.6-11.7-8.6C3 29.6 0 25.7 0 21c0-5.5 4.2-10.1 9.6-10.6C11 12.7 14.8 10 20 10z" fill="#009edb" transform="scale(0.8) translate(3, 3)"/>
    <path d="M20 10c2.6-2.8 6.3-4.5 10.4-4.5 5.5 0 10.3 3.1 12.8 7.7.8-.3 1.8-.5 2.7-.5 4.4 0 8.1 3.6 8.1 8s-3.6 8-8.1 8c-.3 0-.7 0-1-.1-2 3-5.3 5-9 5-1.7 0-3.3-.4-4.7-1.2-2 4-6.2 6.8-11 6.8-5.5 0-10.2-3.6-11.7-8.6C3 29.6 0 25.7 0 21c0-5.5 4.2-10.1 9.6-10.6C11 12.7 14.8 10 20 10z" fill="#00a1e0" transform="scale(0.75) translate(5, 5)"/>
  </svg>
)

// ── Zendesk ───────────────────────────────────────────────────────────────────
const ZendeskLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <path d="M24 8C15.2 8 8 15.2 8 24s7.2 16 16 16 16-7.2 16-16S32.8 8 24 8z" fill="#03363d"/>
    <path d="M15 19h12l-9 10h9" stroke="#87f0a4" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
    <path d="M22 29c0-1.1.9-2 2-2s2 .9 2 2v4l-4-2z" fill="#87f0a4"/>
  </svg>
)

// ── AWS S3 (simplified bucket) ────────────────────────────────────────────────
const AWSS3LogoV2 = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <rect x="4" y="4" width="40" height="40" rx="6" fill="#232f3e"/>
    <ellipse cx="24" cy="16" rx="14" ry="5" fill="#f90"/>
    <path d="M10 16v16c0 2.8 6.3 5 14 5s14-2.2 14-5V16" fill="none" stroke="#f90" strokeWidth="2.5"/>
    <path d="M10 24c0 2.8 6.3 5 14 5s14-2.2 14-5" fill="none" stroke="#f90" strokeWidth="1.5"/>
    <text x="24" y="20" textAnchor="middle" fill="#232f3e" fontSize="6" fontWeight="bold" fontFamily="sans-serif">S3</text>
  </svg>
)

// ── Jira ──────────────────────────────────────────────────────────────────────
const JiraLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="jira-g1" x1="100%" y1="0%" x2="31%" y2="69%">
        <stop offset="18%" stopColor="#0052cc"/>
        <stop offset="100%" stopColor="#2684ff"/>
      </linearGradient>
      <linearGradient id="jira-g2" x1="0%" y1="100%" x2="69%" y2="31%">
        <stop offset="18%" stopColor="#0052cc"/>
        <stop offset="100%" stopColor="#2684ff"/>
      </linearGradient>
    </defs>
    <path d="M24 5L5 24l7.5 7.5L24 20l11.5 11.5L43 24z" fill="url(#jira-g1)"/>
    <path d="M24 43l7.5-7.5L24 28l-7.5 7.5z" fill="url(#jira-g2)"/>
  </svg>
)

// ── GitHub ────────────────────────────────────────────────────────────────────
export const GitHubLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <path fillRule="evenodd" clipRule="evenodd" d="M24 4C12.95 4 4 13.17 4 24.47c0 9.05 5.74 16.72 13.7 19.43.99.19 1.36-.44 1.36-.98 0-.48-.02-2.08-.02-3.78-5.54 1.22-6.7-2.44-6.7-2.44-.9-2.34-2.2-2.96-2.2-2.96-1.8-1.25.14-1.23.14-1.23 1.99.14 3.04 2.08 3.04 2.08 1.77 3.1 4.63 2.2 5.77 1.68.18-1.3.69-2.2 1.26-2.7-4.42-.51-9.06-2.25-9.06-10.01 0-2.21.77-4.02 2.04-5.44-.2-.51-.89-2.57.19-5.35 0 0 1.67-.54 5.46 2.08a18.6 18.6 0 0 1 4.96-.68c1.68.01 3.38.23 4.96.68 3.79-2.62 5.46-2.08 5.46-2.08 1.08 2.78.39 4.84.19 5.35 1.27 1.42 2.04 3.23 2.04 5.44 0 7.78-4.65 9.49-9.08 9.99.72.63 1.36 1.87 1.36 3.76 0 2.7-.02 4.88-.02 5.55 0 .54.36 1.17 1.37.97C38.27 41.19 44 33.51 44 24.47 44 13.17 35.05 4 24 4z" fill="#1b1f23"/>
  </svg>
)

// ── Stripe ────────────────────────────────────────────────────────────────────
const StripeLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <rect width="48" height="48" rx="10" fill="#635bff"/>
    <path d="M22.1 18.6c0-1.3 1-1.8 2.7-1.8 2.4 0 5.5.7 7.9 2V12c-2.6-1-5.2-1.5-7.9-1.5-6.5 0-10.8 3.4-10.8 9 0 8.8 12 7.4 12 11.2 0 1.5-1.3 2-3.1 2-2.7 0-6.1-.9-8.9-2.4v7.1c3 1.3 6 1.8 8.9 1.8 6.7 0 11.3-3.3 11.3-9.1C34.2 21.2 22.1 22.9 22.1 18.6z" fill="white"/>
  </svg>
)

// ── Twilio ────────────────────────────────────────────────────────────────────
const TwilioLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <circle cx="24" cy="24" r="22" fill="#f22f46"/>
    <circle cx="24" cy="24" r="11" fill="none" stroke="white" strokeWidth="3.5"/>
    <circle cx="19" cy="19" r="3" fill="white"/>
    <circle cx="29" cy="19" r="3" fill="white"/>
    <circle cx="29" cy="29" r="3" fill="white"/>
    <circle cx="19" cy="29" r="3" fill="white"/>
  </svg>
)

// ── Asana ─────────────────────────────────────────────────────────────────────
const AsanaLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <circle cx="24" cy="16" r="9" fill="#fc636b"/>
    <circle cx="12" cy="32" r="9" fill="#fc636b"/>
    <circle cx="36" cy="32" r="9" fill="#fc636b"/>
  </svg>
)

// ── Monday.com ────────────────────────────────────────────────────────────────
const MondayLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <rect width="48" height="48" rx="10" fill="#1f1f1f"/>
    <ellipse cx="12" cy="30" rx="6" ry="7" fill="#ff3d57"/>
    <ellipse cx="24" cy="30" rx="6" ry="7" fill="#ffcb00"/>
    <ellipse cx="36" cy="30" rx="6" ry="7" fill="#00ca72"/>
  </svg>
)

// ── QuickBooks ────────────────────────────────────────────────────────────────
const QuickBooksLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <circle cx="24" cy="24" r="22" fill="#2ca01c"/>
    <path d="M14 24c0-5.5 4.5-10 10-10h2v4h-2c-3.3 0-6 2.7-6 6s2.7 6 6 6h2v4h-2c-5.5 0-10-4.5-10-10z" fill="white"/>
    <path d="M26 18h2c5.5 0 10 4.5 10 10s-4.5 10-10 10h-2v-4h2c3.3 0 6-2.7 6-6s-2.7-6-6-6h-2v-4z" fill="white"/>
    <rect x="22" y="20" width="4" height="8" rx="2" fill="#2ca01c"/>
  </svg>
)

// ── DocuSign ──────────────────────────────────────────────────────────────────
const DocuSignLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <rect width="48" height="48" rx="8" fill="#ffbc21"/>
    <path d="M12 14h16a6 6 0 0 1 6 6v4a6 6 0 0 1-6 6H12V14z" fill="white"/>
    <path d="M28 18c2.2 0 4 1.8 4 4v2c0 2.2-1.8 4-4 4H16V18h12z" fill="#25302e"/>
    <path d="M26 24c0 1.1-.9 2-2 2s-2-.9-2-2 .9-2 2-2 2 .9 2 2z" fill="white"/>
    <path d="M30 34l4 4" stroke="#25302e" strokeWidth="2.5" strokeLinecap="round"/>
    <circle cx="33" cy="37" r="1.5" fill="#25302e"/>
  </svg>
)

// ── Intercom ──────────────────────────────────────────────────────────────────
const IntercomLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <rect width="48" height="48" rx="10" fill="#1f8ded"/>
    <rect x="10" y="10" width="28" height="22" rx="5" fill="white"/>
    <circle cx="17" cy="21" r="3" fill="#1f8ded"/>
    <circle cx="24" cy="21" r="3" fill="#1f8ded"/>
    <circle cx="31" cy="21" r="3" fill="#1f8ded"/>
    <path d="M14 36l6-4h14" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
)

// ── Pipedrive ─────────────────────────────────────────────────────────────────
const PipedriveLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <circle cx="24" cy="24" r="22" fill="#1a1a2e"/>
    <circle cx="24" cy="20" r="9" fill="none" stroke="#22c55e" strokeWidth="3.5"/>
    <line x1="24" y1="29" x2="24" y2="42" stroke="#22c55e" strokeWidth="3.5" strokeLinecap="round"/>
    <circle cx="24" cy="20" r="4" fill="#22c55e"/>
  </svg>
)

// ── ServiceNow ────────────────────────────────────────────────────────────────
const ServiceNowLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <rect width="48" height="48" rx="10" fill="#62d84e"/>
    <path d="M24 10c-7.7 0-14 6.3-14 14s6.3 14 14 14 14-6.3 14-14S31.7 10 24 10zm0 4c5.5 0 10 4.5 10 10s-4.5 10-10 10S14 29.5 14 24s4.5-10 10-10z" fill="white"/>
    <path d="M24 18c-3.3 0-6 2.7-6 6s2.7 6 6 6 6-2.7 6-6-2.7-6-6-6zm0 4c1.1 0 2 .9 2 2s-.9 2-2 2-2-.9-2-2 .9-2 2-2z" fill="white"/>
  </svg>
)

// ── Google Analytics ──────────────────────────────────────────────────────────
const GoogleAnalyticsLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <rect x="28" y="10" width="10" height="28" rx="5" fill="#f9ab00"/>
    <rect x="15" y="22" width="10" height="16" rx="5" fill="#e37400"/>
    <circle cx="10" cy="34" r="5" fill="#e37400" opacity=".7"/>
  </svg>
)

// ── Figma ─────────────────────────────────────────────────────────────────────
const FigmaLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <rect x="14" y="6" width="20" height="12" rx="6" fill="#f24e1e"/>
    <rect x="14" y="18" width="10" height="12" rx="5" fill="#a259ff"/>
    <rect x="14" y="30" width="10" height="12" rx="5" fill="#0acf83"/>
    <rect x="24" y="18" width="10" height="12" rx="5" fill="#1abcfe"/>
    <circle cx="29" cy="24" r="5" fill="#1abcfe"/>
  </svg>
)

// ── Shopify ───────────────────────────────────────────────────────────────────
const ShopifyLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <rect width="48" height="48" rx="10" fill="#96bf48"/>
    <path d="M33 14.5c0-.2-.1-.3-.3-.3-.2 0-3.2-.2-3.2-.2s-2.1-2.1-2.3-2.3c-.2-.2-.7-.1-.9 0 0 0-.4.1-1.1.3-.6-1.8-1.7-3.4-3.6-3.4h-.2C21 7.7 20.3 7 19.5 7c-5.6 0-8.3 7-9.1 10.6L7 18.5l-1 12.5 20 3.5 10.5-2.2L33 14.5zM26.3 13c-.5.2-1.1.3-1.8.5-.4-1.5-1.2-2.9-2.8-3 1.8.1 3.5 1.1 4.6 2.5zm-6.8-4.8c.2 0 .4.1.5.2-1.3.6-2.7 2.2-3.3 5.3-.8.3-1.7.5-2.5.8.8-2.8 2.5-6.3 5.3-6.3zm1 12.5l-2.8-1.4c.2-2.6 1.4-3.8 2.4-4.2.1.5.4 1 .4 1.8v3.8zm2.5 1.3l-4.6-2.3c-.1-4.7 1.4-6.2 2.1-6.7 0 .8.5 1.5.5 2.8 0 2.4 2 6.2 2 6.2z" fill="white"/>
  </svg>
)

// ── Confluence ────────────────────────────────────────────────────────────────
const ConfluenceLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="conf-g1" x1="100%" y1="0%" x2="20%" y2="80%">
        <stop offset="0%" stopColor="#2684ff"/>
        <stop offset="100%" stopColor="#0052cc"/>
      </linearGradient>
      <linearGradient id="conf-g2" x1="0%" y1="100%" x2="80%" y2="20%">
        <stop offset="0%" stopColor="#0052cc"/>
        <stop offset="100%" stopColor="#2684ff"/>
      </linearGradient>
    </defs>
    <path d="M6 34.5c-.4.6-.1 1.4.6 1.7l8.8 4.3c.7.3 1.5.1 1.9-.6 2.8-4.7 6.6-7.2 11.7-7.2 4.2 0 7.8 1.7 10.5 4.4.5.5 1.3.6 1.9.2l7.5-5c.6-.4.8-1.3.3-1.9C44.4 25.1 36.6 20 27 20c-9.5 0-17.3 5.1-21 14.5z" fill="url(#conf-g1)"/>
    <path d="M42 13.5c.4-.6.1-1.4-.6-1.7L32.6 7.5c-.7-.3-1.5-.1-1.9.6-2.8 4.7-6.6 7.2-11.7 7.2-4.2 0-7.8-1.7-10.5-4.4-.5-.5-1.3-.6-1.9-.2L1.1 15.7c-.6.4-.8 1.3-.3 1.9C4.6 22.9 12.4 28 22 28c9.5 0 17.3-5.1 21-14.5z" fill="url(#conf-g2)"/>
  </svg>
)

// ── Fiverr ────────────────────────────────────────────────────────────────────
const FiverrLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <rect width="48" height="48" rx="10" fill="#1dbf73"/>
    <circle cx="34" cy="13" r="3.5" fill="white"/>
    <path d="M14 26h6v10h4V26h4v-4h-4v-2c0-1.1.9-2 2-2h2v-4h-2c-3.3 0-6 2.7-6 6v2h-6v4z" fill="white"/>
  </svg>
)

// ── Xero ──────────────────────────────────────────────────────────────────────
const XeroLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <circle cx="24" cy="24" r="22" fill="#13b5ea"/>
    <path d="M14 18l10 6-10 6M22 18h8M34 18l-10 6 10 6M22 30h8" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
    <path d="M14 18l5 3-5 3" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
    <circle cx="35" cy="24" r="6" fill="white" opacity=".15"/>
    <text x="24" y="28.5" textAnchor="middle" fill="white" fontSize="13" fontWeight="bold" fontFamily="sans-serif">xero</text>
  </svg>
)

// ── PayPal ────────────────────────────────────────────────────────────────────
const PayPalLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <rect width="48" height="48" rx="10" fill="#003087"/>
    <path d="M32.5 13H21c-.8 0-1.5.6-1.6 1.4L16 33h4.5l1-6h3.5c5.5 0 9.5-2.5 10.5-8 .5-2.8-.5-5-3-6z" fill="#009cde"/>
    <path d="M22 22h3c3.5 0 6-1.5 6.5-5 .3-1.7-.3-3-1.8-3.8C28.5 14.7 26.5 15 24 15h-3.5L22 22z" fill="white" opacity=".7"/>
    <path d="M13 20h3.5l-3.5 13H9l4-13z" fill="#009cde"/>
    <path d="M15 20h3.5c4.5 0 8-2 9-6.5.3-1.4 0-2.7-.7-3.7C25.5 9.3 23.5 9 21 9h-7c-.8 0-1.5.6-1.6 1.4L9 28h4.5L15 20z" fill="white"/>
  </svg>
)

// ── FreshBooks ────────────────────────────────────────────────────────────────
const FreshBooksLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <rect width="48" height="48" rx="10" fill="#0075dd"/>
    <path d="M12 14h16a6 6 0 0 1 0 12H16v8h-4V14z" fill="white"/>
    <path d="M16 18h10a2 2 0 0 1 0 4H16v-4z" fill="#0075dd"/>
    <path d="M30 26l6 8h-5l-4-5.5" fill="white" opacity=".85"/>
  </svg>
)

// ── Wave ──────────────────────────────────────────────────────────────────────
const WaveLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <rect width="48" height="48" rx="10" fill="#2a6ebb"/>
    <path d="M6 28c3-6 5-10 8-10s5 8 8 8 5-10 8-10 5 6 6 10" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
    <text x="24" y="42" textAnchor="middle" fill="white" fontSize="9" fontWeight="bold" fontFamily="sans-serif" opacity=".85">WAVE</text>
  </svg>
)

// ── Fitbit ────────────────────────────────────────────────────────────────────
const FitbitLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <rect width="48" height="48" rx="10" fill="#00B0B9"/>
    <circle cx="24" cy="14" r="3.5" fill="white"/>
    <circle cx="24" cy="24" r="4.5" fill="white"/>
    <circle cx="24" cy="35" r="3" fill="white"/>
    <circle cx="14" cy="19" r="3" fill="white"/>
    <circle cx="34" cy="19" r="3" fill="white"/>
    <circle cx="14" cy="29" r="3" fill="white"/>
    <circle cx="34" cy="29" r="3" fill="white"/>
  </svg>
)

// ── Strava ────────────────────────────────────────────────────────────────────
const StravaLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <rect width="48" height="48" rx="10" fill="#FC4C02"/>
    <path d="M20 38L14 26h8l-2-5 8-15 8 15h-8l-2 5h8L20 38z" fill="none"/>
    <path d="M24 8l-8 15h5l3 7 3-7h5z" fill="white"/>
    <path d="M29 23l-5 11-5-11h3l2 5 2-5z" fill="white" opacity=".75"/>
  </svg>
)

// ── Withings ──────────────────────────────────────────────────────────────────
const WithingsLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <rect width="48" height="48" rx="10" fill="#1c3d5a"/>
    <circle cx="24" cy="20" r="10" fill="none" stroke="white" strokeWidth="2.5"/>
    <circle cx="24" cy="20" r="4" fill="white"/>
    <path d="M18 32c0 3.3 2.7 6 6 6s6-2.7 6-6" stroke="white" strokeWidth="2.5" strokeLinecap="round" fill="none"/>
    <line x1="24" y1="30" x2="24" y2="32" stroke="white" strokeWidth="2.5" strokeLinecap="round"/>
  </svg>
)

// ── Upwork ────────────────────────────────────────────────────────────────────
const UpworkLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <rect width="48" height="48" rx="10" fill="#14a800"/>
    <path d="M30.5 12c-4.1 0-7.3 2.6-8.6 6.8L18 12H12v12.5c0 3 2.5 5.5 5.5 5.5s5.5-2.5 5.5-5.5V18l4.5 12h3.5l4.5-12v6.5c0 3 2.5 5.5 5.5 5.5V12h-10zm-13 15c-1.4 0-2.5-1.1-2.5-2.5V15h5v9.5c0 1.4-1.1 2.5-2.5 2.5z" fill="white"/>
  </svg>
)

// ── GitLab ────────────────────────────────────────────────────────────────────
const GitLabLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <rect width="48" height="48" rx="10" fill="#FC6D26"/>
    <path d="M24 38l7-21h-14z" fill="white"/>
    <path d="M24 38L10 17H17z" fill="white" opacity=".7"/>
    <path d="M24 38L38 17H31z" fill="white" opacity=".7"/>
    <path d="M10 17L7 26l3 3 7-12z" fill="white" opacity=".5"/>
    <path d="M38 17L41 26l-3 3-7-12z" fill="white" opacity=".5"/>
  </svg>
)

// ── Linear ────────────────────────────────────────────────────────────────────
const LinearLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <rect width="48" height="48" rx="10" fill="#5E6AD2"/>
    <path d="M10 32.5L15.5 38l22-22L32 10z" fill="white"/>
    <path d="M10 25L23 38h-4L10 29z" fill="white" opacity=".7"/>
    <path d="M19 10l19 19v-4L23 10z" fill="white" opacity=".7"/>
    <circle cx="35" cy="13" r="3" fill="white" opacity=".4"/>
  </svg>
)

// ── Sentry ────────────────────────────────────────────────────────────────────
const SentryLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <rect width="48" height="48" rx="10" fill="#362D59"/>
    <path d="M24 8l-16 27h8c0-8 3.5-15 8-20" fill="none" stroke="#FB4226" strokeWidth="2.5" strokeLinecap="round"/>
    <path d="M16 35h16c0-9-3.6-17-8-22" fill="none" stroke="#FB4226" strokeWidth="2.5" strokeLinecap="round"/>
    <circle cx="32" cy="11" r="2.5" fill="#FB4226"/>
  </svg>
)

// ── PagerDuty ─────────────────────────────────────────────────────────────────
const PagerDutyLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <rect width="48" height="48" rx="10" fill="#06AC38"/>
    <rect x="21" y="10" width="6" height="20" rx="3" fill="white"/>
    <rect x="21" y="33" width="6" height="6" rx="2" fill="white"/>
  </svg>
)

// ── Zoom ──────────────────────────────────────────────────────────────────────
const ZoomLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <rect width="48" height="48" rx="10" fill="#0B5CFF"/>
    <rect x="9" y="15" width="22" height="18" rx="4" fill="white"/>
    <path d="M31 20l8-5v18l-8-5z" fill="white"/>
  </svg>
)

// ── Mailchimp ─────────────────────────────────────────────────────────────────
const MailchimpLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <rect width="48" height="48" rx="10" fill="#FFE01B"/>
    <ellipse cx="24" cy="22" rx="10" ry="12" fill="#241C15"/>
    <ellipse cx="24" cy="20" rx="7" ry="9" fill="#FFE01B"/>
    <circle cx="21" cy="19" r="1.5" fill="#241C15"/>
    <circle cx="27" cy="19" r="1.5" fill="#241C15"/>
    <path d="M21 23c1 1.5 5 1.5 6 0" stroke="#241C15" strokeWidth="1.5" strokeLinecap="round" fill="none"/>
    <ellipse cx="24" cy="30" rx="6" ry="4" fill="#241C15"/>
    <ellipse cx="24" cy="29" rx="4" ry="3" fill="#FFE01B"/>
  </svg>
)

// ── SendGrid ──────────────────────────────────────────────────────────────────
const SendGridLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <rect width="48" height="48" rx="10" fill="#1A82E2"/>
    <rect x="10" y="10" width="28" height="9" rx="2" fill="white" opacity=".9"/>
    <rect x="10" y="21" width="14" height="9" rx="2" fill="white" opacity=".6"/>
    <rect x="24" y="21" width="14" height="9" rx="2" fill="white" opacity=".9"/>
    <rect x="10" y="32" width="28" height="6" rx="2" fill="white" opacity=".6"/>
  </svg>
)

// ── LinkedIn ──────────────────────────────────────────────────────────────────
const LinkedInLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <rect width="48" height="48" rx="10" fill="#0A66C2"/>
    <rect x="9" y="18" width="6" height="20" rx="1" fill="white"/>
    <circle cx="12" cy="12" r="4" fill="white"/>
    <path d="M21 18h6v3c1.5-2.5 4-3.5 7-3.5 5.5 0 5 5 5 8v12h-6V27c0-2-.5-4-3-4s-3 2-3 4v11h-6V18z" fill="white"/>
  </svg>
)

// ── Twitter / X ───────────────────────────────────────────────────────────────
export const TwitterLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <rect width="48" height="48" rx="10" fill="#000000"/>
    <path d="M11 11h8l5 7 6-7h4L26 22l13 15h-8l-6-8-7 8h-4l9-11z" fill="white"/>
  </svg>
)

// ── Facebook ──────────────────────────────────────────────────────────────────
const FacebookLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <rect width="48" height="48" rx="10" fill="#1877F2"/>
    <path d="M31 25h-5v13h-6V25h-4v-6h4v-3.5c0-4 2.2-6.5 6.7-6.5H30v5.5h-2.3c-1.3 0-1.7.6-1.7 1.8V19h4z" fill="white"/>
  </svg>
)

// ── Instagram ─────────────────────────────────────────────────────────────────
const InstagramLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="ig-grad" x1="0%" y1="100%" x2="100%" y2="0%">
        <stop offset="0%" stopColor="#FFDD55"/>
        <stop offset="40%" stopColor="#FF543E"/>
        <stop offset="70%" stopColor="#C837AB"/>
        <stop offset="100%" stopColor="#5851DB"/>
      </linearGradient>
    </defs>
    <rect width="48" height="48" rx="12" fill="url(#ig-grad)"/>
    <rect x="12" y="12" width="24" height="24" rx="7" fill="none" stroke="white" strokeWidth="2.5"/>
    <circle cx="24" cy="24" r="6.5" fill="none" stroke="white" strokeWidth="2.5"/>
    <circle cx="31.5" cy="16.5" r="1.7" fill="white"/>
  </svg>
)

// ── TikTok ────────────────────────────────────────────────────────────────────
const TikTokLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <rect width="48" height="48" rx="10" fill="#000000"/>
    <path d="M28 8h5c.3 3 2.3 5.6 5 6.5v5c-2.6 0-5-.8-7-2.2v11.2c0 5.8-4.7 9.5-10 9.5s-9-4-9-9c0-5 4-9 9-9 .5 0 1 0 1.5.1v5.2c-.5-.2-1-.3-1.5-.3-2.2 0-4 1.7-4 4s1.9 4.2 4 4.2c2.4 0 4.5-1.7 4.5-4.7V8z" fill="white"/>
    <path d="M28 8h5c.3 3 2.3 5.6 5 6.5v5c-2.6 0-5-.8-7-2.2v3.2c-2-1-3-2.8-3-5.2V8z" fill="#69C9D0"/>
    <path d="M17 24.6c-2.2.4-4 2.4-4 4.8 0 2.7 2.2 4.8 4.9 4.8.8 0 1.5-.2 2.1-.5-1.8-1-3-2.9-3-5.1 0-1.6.6-3 1.6-4z" fill="#EE1D52"/>
  </svg>
)

// ── Zoho CRM ──────────────────────────────────────────────────────────────────
const ZohoCRMLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <rect width="48" height="48" rx="10" fill="#E42527"/>
    <path d="M10 32L20 16h18v4H24L14 36H32v-4h4v8H10z" fill="white"/>
  </svg>
)

// ── BambooHR ──────────────────────────────────────────────────────────────────
const BambooHRLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <rect width="48" height="48" rx="10" fill="#73AA24"/>
    <rect x="21" y="10" width="6" height="28" rx="3" fill="white"/>
    <path d="M24 18c-6 0-10-3-10-7h4c0 2 2.5 3 6 3z" fill="white" opacity=".8"/>
    <path d="M24 26c6 0 10-3 10-7h-4c0 2-2.5 3-6 3z" fill="white" opacity=".8"/>
  </svg>
)

// ── Greenhouse ────────────────────────────────────────────────────────────────
const GreenhouseLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <rect width="48" height="48" rx="10" fill="#24A47F"/>
    <circle cx="24" cy="18" r="10" fill="none" stroke="white" strokeWidth="3"/>
    <rect x="21" y="24" width="6" height="14" rx="2" fill="white"/>
    <line x1="10" y1="33" x2="38" y2="33" stroke="white" strokeWidth="3" strokeLinecap="round"/>
  </svg>
)

// ── Datadog ───────────────────────────────────────────────────────────────────
const DatadogLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <rect width="48" height="48" rx="10" fill="#632CA6"/>
    <path d="M10 34l4-16 5 8 5-12 5 8 4-8 5 20" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
    <circle cx="14" cy="34" r="2" fill="white"/>
    <circle cx="38" cy="34" r="2" fill="white"/>
  </svg>
)

// ── Microsoft Excel ───────────────────────────────────────────────────────────
const ExcelLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <path d="M28 6H14c-1.1 0-2 .9-2 2v32c0 1.1.9 2 2 2h20c1.1 0 2-.9 2-2V14L28 6z" fill="#107C41"/>
    <path d="M28 6v8h8L28 6z" fill="#33C481"/>
    <path d="M4 14h24v20H4z" fill="#107C41"/>
    <path d="M11.5 19l2.8 4.7L11.2 29h2.6l1.6-3.1 1.7 3.1h2.7l-3.1-5.2 2.9-4.8h-2.5l-1.7 3.2-1.7-3.2h-2.5z" fill="white"/>
  </svg>
)

// ── Microsoft Word ────────────────────────────────────────────────────────────
const WordLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <path d="M28 6H14c-1.1 0-2 .9-2 2v32c0 1.1.9 2 2 2h20c1.1 0 2-.9 2-2V14L28 6z" fill="#185ABD"/>
    <path d="M28 6v8h8L28 6z" fill="#4B96E6"/>
    <path d="M4 14h24v20H4z" fill="#185ABD"/>
    <path d="M10.5 19l1.8 10h2.4l1.6-6.4 1.6 6.4h2.4l1.8-10h-2.3l-1 6.5-1.6-6.5h-1.8l-1.6 6.5-1-6.5h-2.3z" fill="white"/>
  </svg>
)

// ── ClickUp ───────────────────────────────────────────────────────────────────
const ClickUpLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <rect width="48" height="48" rx="10" fill="#7B2CBF"/>
    <path d="M12 25l6-5 6 5 6-5 6 5" fill="none" stroke="#FF007A" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round"/>
    <path d="M12 30c5.3 4 14.7 4 24 0" fill="none" stroke="#00F0FF" strokeWidth="4" strokeLinecap="round"/>
    <path d="M15 17l9-8 9 8" fill="none" stroke="#FFD600" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
)

// ── Google Meet ───────────────────────────────────────────────────────────────
const GoogleMeetLogo = ({ size = 32 }: LogoProps) => (
  <svg width={size} height={size} viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <path d="M29 14.5v19l8.5 6.5V8L29 14.5z" fill="#008237"/>
    <path d="M7 13.5v21c0 2.5 2 4.5 4.5 4.5h17.5V9H11.5C9 9 7 11 7 13.5z" fill="#00a852"/>
    <path d="M29 9H11.5c-1.3 0-2.5.5-3.3 1.4L18 20.2 29 11.5V9z" fill="#FFBA00"/>
    <path d="M7 34.5c0 1.3.5 2.5 1.4 3.3L18 27.8 7 19v15.5z" fill="#0066DA"/>
    <path d="M37.5 8L29 14.5v6.5l8.5-6.5V8z" fill="#EA4335"/>
  </svg>
)

// ── Logo map ──────────────────────────────────────────────────────────────────
const LOGOS: Record<string, (props: LogoProps) => React.ReactElement> = {
  'google-drive':         GoogleDriveLogo,
  'onedrive':             OneDriveLogo,
  'dropbox':              DropboxLogo,
  'box':                  BoxLogo,
  'sharepoint':           SharePointLogo,
  'google-cloud-storage': GoogleCloudStorageLogo,
  'aws-s3':               AWSS3LogoV2,
  'gmail':                GmailLogo,
  'outlook':              OutlookLogo,
  'slack':                SlackLogo,
  'teams':                TeamsLogo,
  'telegram':             TelegramLogo,
  'discord':              DiscordLogo,
  'whatsapp':             WhatsAppLogo,
  'google-calendar':      GoogleCalendarLogo,
  'calendly':             CalendlyLogo,
  'google-sheets':        GoogleSheetsLogo,
  'excel':                ExcelLogo,
  'microsoft-excel':      ExcelLogo,
  'microsoft_excel':      ExcelLogo,
  'word':                 WordLogo,
  'microsoft-word':       WordLogo,
  'microsoft_word':       WordLogo,
  'clickup':              ClickUpLogo,
  'google-meet':          GoogleMeetLogo,
  'google_meet':          GoogleMeetLogo,
  'googlemeet':           GoogleMeetLogo,
  'notion':               NotionLogo,
  'airtable':             AirtableLogo,
  'hubspot':              HubSpotLogo,
  'salesforce':           SalesforceLogo,
  'zendesk':              ZendeskLogo,
  'jira':                 JiraLogo,
  'github':               GitHubLogo,
  'stripe':               StripeLogo,
  'twilio':               TwilioLogo,
  'asana':                AsanaLogo,
  'monday':               MondayLogo,
  'quickbooks':           QuickBooksLogo,
  'docusign':             DocuSignLogo,
  'intercom':             IntercomLogo,
  'pipedrive':            PipedriveLogo,
  'servicenow':           ServiceNowLogo,
  'google-analytics':     GoogleAnalyticsLogo,
  'figma':                FigmaLogo,
  'shopify':              ShopifyLogo,
  'confluence':           ConfluenceLogo,
  'upwork':               UpworkLogo,
  'fiverr':               FiverrLogo,
  'xero':                 XeroLogo,
  'paypal':               PayPalLogo,
  'freshbooks':           FreshBooksLogo,
  'wave':                 WaveLogo,
  'fitbit':               FitbitLogo,
  'strava':               StravaLogo,
  'withings':             WithingsLogo,
  'gitlab':               GitLabLogo,
  'linear':               LinearLogo,
  'sentry':               SentryLogo,
  'pagerduty':            PagerDutyLogo,
  'zoom':                 ZoomLogo,
  'mailchimp':            MailchimpLogo,
  'sendgrid':             SendGridLogo,
  'linkedin':             LinkedInLogo,
  'twitter':              TwitterLogo,
  'facebook':             FacebookLogo,
  'instagram':            InstagramLogo,
  'tiktok':               TikTokLogo,
  'zoho-crm':             ZohoCRMLogo,
  'bamboohr':             BambooHRLogo,
  'greenhouse':           GreenhouseLogo,
  'datadog':              DatadogLogo,
}

export type ConnectorLogoId = keyof typeof LOGOS

export const CONNECTOR_LOGO_IDS = Object.keys(LOGOS) as ConnectorLogoId[]

export function isConnectorLogoId(id: string): id is ConnectorLogoId {
  return id in LOGOS
}

interface ConnectorLogoProps {
  providerId: string
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

const SIZE_PX = { sm: 20, md: 28, lg: 36 }
const CONTAINER_CLS = {
  sm: 'w-9 h-9 rounded-xl',
  md: 'w-12 h-12 rounded-2xl',
  lg: 'w-16 h-16 rounded-3xl',
}

export function ConnectorLogo({ providerId, size = 'md', className }: ConnectorLogoProps) {
  const Logo = LOGOS[providerId]
  const px = SIZE_PX[size]

  return (
    <div
      className={cn(
        'flex items-center justify-center shrink-0',
        'bg-white dark:bg-white/10',
        'shadow-sm ring-1 ring-black/[0.06] dark:ring-white/10',
        CONTAINER_CLS[size],
        className,
      )}
    >
      {Logo
        ? <Logo size={px} />
        : <span className="text-[11px] font-bold text-gray-400">{providerId.slice(0, 2).toUpperCase()}</span>
      }
    </div>
  )
}
