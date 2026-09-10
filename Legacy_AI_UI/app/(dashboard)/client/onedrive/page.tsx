'use client'

import { useSearchParams } from 'next/navigation'
import { HardDrive } from 'lucide-react'
import StorageManager from '@/components/storage/storage-manager'
import { oneDriveApi } from '@/lib/api/onedrive'
import type { StorageProviderConfig } from '@/components/storage/storage-manager'

const oneDriveConfig: StorageProviderConfig = {
  id: 'onedrive',
  name: 'OneDrive',
  icon: HardDrive,
  description:
    "Connect your OneDrive to manage files directly from this dashboard. You'll be redirected to Microsoft's sign-in page to authorize access.",
  securityNote: 'Your credentials are handled securely by Microsoft.',
  credentialTitle: 'Microsoft credentials required',
  credentialDescription: 'Enter your Microsoft OAuth Client ID and Secret to enable OneDrive access.',
  credentialHelpUrl: 'https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps',
  credentialHelpLabel: 'Azure Portal',
  credentialHelpSteps: [
    'Create a new App registration or select an existing one',
    'Under Authentication > Add a platform > Web, add the Redirect URI below',
    'Under Certificates & secrets, create a new Client secret',
    'Copy the Application (client) ID and the Client secret value into the fields below',
  ],
  clientIdPlaceholder: '00000000-0000-0000-0000-000000000000',
  clientSecretPlaceholder: 'your-client-secret',
  getStatus: () => oneDriveApi.getStatus(),
  getAuthUrl: () => oneDriveApi.getAuthUrl(),
  configure: (clientId, clientSecret) => oneDriveApi.configure(clientId, clientSecret),
  getSetupInfo: () => oneDriveApi.getCredentials().then(r => ({ has_credentials: r.has_credentials, redirect_uri: r.redirect_uri })),
  disconnect: () => oneDriveApi.disconnect(),
  listFiles: () => oneDriveApi.listFiles(),
  createFile: (payload) => oneDriveApi.createFile(payload),
  renameFile: (id, payload) => oneDriveApi.renameFile(id, payload),
  deleteFile: (id) => oneDriveApi.deleteFile(id),
  shareFile: (id, payload) => oneDriveApi.shareFile(id, payload),
}

export default function OneDrivePage() {
  const searchParams = useSearchParams()
  const initialError = searchParams.get('error') || undefined
  return <StorageManager config={oneDriveConfig} initialError={initialError} />
}
