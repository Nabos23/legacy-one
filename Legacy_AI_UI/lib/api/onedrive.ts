import { api } from './client'
import type {
  MicrosoftAuthUrlResponse,
  MicrosoftAuthStatusResponse,
  MicrosoftCredentialsStatus,
  DriveFile,
  CreateDriveFilePayload,
  RenameDriveFilePayload,
  ShareDriveFilePayload,
} from '@/types'

export const oneDriveApi = {
  /** Get the Microsoft OAuth URL to redirect the user to */
  getAuthUrl: () => api.get<MicrosoftAuthUrlResponse>('/api/auth/microsoft/url'),

  /** Check if the current user has connected their OneDrive */
  getStatus: () => api.get<MicrosoftAuthStatusResponse>('/api/auth/microsoft/status'),

  /** Disconnect the user's OneDrive */
  disconnect: () => api.post<void>('/api/auth/microsoft/disconnect', {}),

  /** Save Microsoft OAuth client credentials and return the auth URL */
  configure: (clientId: string, clientSecret: string) =>
    api.post<MicrosoftAuthUrlResponse>('/api/auth/microsoft/configure', {
      client_id: clientId,
      client_secret: clientSecret,
    }),

  /** Get saved credential info (has_credentials, client_id, redirect_uri) */
  getCredentials: () => api.get<MicrosoftCredentialsStatus>('/api/onedrive/credentials'),

  /** List all OneDrive files */
  listFiles: () => api.get<DriveFile[]>('/api/onedrive/files'),

  /** Create a new OneDrive file */
  createFile: (payload: CreateDriveFilePayload) =>
    api.post<DriveFile>('/api/onedrive/files', payload),

  /** Rename/update a OneDrive file */
  renameFile: (id: string, payload: RenameDriveFilePayload) =>
    api.put<DriveFile>(`/api/onedrive/files/${id}`, payload),

  /** Delete a OneDrive file */
  deleteFile: (id: string) => api.delete<void>(`/api/onedrive/files/${id}`),

  /** Share a OneDrive file with another user */
  shareFile: (id: string, payload: ShareDriveFilePayload) =>
    api.post<void>(`/api/onedrive/files/${id}/share`, payload),
}
