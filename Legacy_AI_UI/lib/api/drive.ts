import { api } from './client'
import type {
  GoogleAuthUrlResponse,
  AuthStatusResponse,
  DriveCredentialsStatus,
  DriveFile,
  CreateDriveFilePayload,
  RenameDriveFilePayload,
  ShareDriveFilePayload,
} from '@/types'

export const driveApi = {
  /** Get the Google OAuth URL to redirect the user to */
  getAuthUrl: () => api.get<GoogleAuthUrlResponse>('/api/auth/google/url'),

  /** Save Google OAuth client credentials and return the auth URL */
  configure: (clientId: string, clientSecret: string) =>
    api.post<GoogleAuthUrlResponse>('/api/auth/google/configure', {
      client_id: clientId,
      client_secret: clientSecret,
    }),

  /** Get saved credential info (has_credentials, client_id, redirect_uri) */
  getCredentials: () => api.get<DriveCredentialsStatus>('/api/drive/credentials'),

  /** Check if the current user has connected their Google Drive */
  getStatus: () => api.get<AuthStatusResponse>('/api/auth/status'),

  /** Disconnect the user's Google Drive */
  disconnect: () => api.post<void>('/api/auth/disconnect', {}),

  /** List all Drive files */
  listFiles: () => api.get<DriveFile[]>('/api/drive/files'),

  /** Create a new Drive file */
  createFile: (payload: CreateDriveFilePayload) =>
    api.post<DriveFile>('/api/drive/files', payload),

  /** Rename/update a Drive file */
  renameFile: (id: string, payload: RenameDriveFilePayload) =>
    api.put<DriveFile>(`/api/drive/files/${id}`, payload),

  /** Delete a Drive file */
  deleteFile: (id: string) => api.delete<void>(`/api/drive/files/${id}`),

  /** Share a Drive file with another user */
  shareFile: (id: string, payload: ShareDriveFilePayload) =>
    api.post<void>(`/api/drive/files/${id}/share`, payload),
}
