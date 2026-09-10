'use client'

import { Cloud } from 'lucide-react'
import StorageManager from '@/components/storage/storage-manager'
import { driveApi } from '@/lib/api/drive'
import type { StorageProviderConfig } from '@/components/storage/storage-manager'

const googleDriveConfig: StorageProviderConfig = {
  id: 'google-drive',
  name: 'Google Drive',
  icon: Cloud,
  description:
    "Connect your Google Drive to manage files directly from this dashboard. You'll be redirected to Google's sign-in page to authorize access.",
  securityNote: 'Your credentials are stored securely and never shared.',
  credentialTitle: 'Google Drive credentials required',
  credentialDescription: 'Enter your Google OAuth Client ID and Secret to enable Drive access.',
  credentialHelpUrl: 'https://console.cloud.google.com/apis/credentials',
  credentialHelpLabel: 'Google Cloud Console',
  credentialHelpSteps: [
    'Create an OAuth 2.0 Client ID (Web application type)',
    'Under Authorized redirect URIs, add the URL below',
    'Copy the Client ID and Client Secret into the fields below',
  ],
  clientIdPlaceholder: 'xxxxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx.apps.googleusercontent.com',
  clientSecretPlaceholder: 'GOCSPX-xxxxxxxxxxxxxxxxxxxxx',
  getStatus: () => driveApi.getStatus(),
  getAuthUrl: () => driveApi.getAuthUrl(),
  configure: (clientId, clientSecret) => driveApi.configure(clientId, clientSecret),
  getSetupInfo: () => driveApi.getCredentials().then(r => ({ has_credentials: r.has_credentials, redirect_uri: r.redirect_uri })),
  disconnect: () => driveApi.disconnect(),
  listFiles: () => driveApi.listFiles(),
  createFile: (payload) => driveApi.createFile(payload),
  renameFile: (id, payload) => driveApi.renameFile(id, payload),
  deleteFile: (id) => driveApi.deleteFile(id),
  shareFile: (id, payload) => driveApi.shareFile(id, payload),
}

export default function DrivePage() {
  return <StorageManager config={googleDriveConfig} />
}
