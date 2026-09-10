'use client'

import { useRef, useState } from 'react'
import { Loader2, Upload, X } from 'lucide-react'
import { widgetsApi } from '@/lib/api/widgets'
import { useToast } from '@/hooks/use-toast'

interface ImageUploadFieldProps {
  widgetId: string
  label: string
  value: string | null | undefined
  onChange: (url: string | null) => void
  hint?: string
}

/** Uploads through POST /widget-configs/{id}/upload-image (reuses the same
 * image validation as the user avatar uploader) and writes the returned URL
 * back via onChange -- the caller still owns saving that URL to the widget. */
export function ImageUploadField({ widgetId, label, value, onChange, hint }: ImageUploadFieldProps) {
  const { toast } = useToast()
  const inputRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)

  const handleFile = async (file: File | undefined) => {
    if (!file) return
    setUploading(true)
    try {
      const res = await widgetsApi.uploadImage(widgetId, file)
      onChange(res.url)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to upload image')
    } finally {
      setUploading(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  return (
    <div>
      <label className="text-[13px] font-medium block mb-2">{label}</label>
      {hint && <p className="text-[11px] text-[var(--text-3)] mb-2">{hint}</p>}
      <div className="flex items-center gap-3">
        {value ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={value} alt="" className="w-10 h-10 rounded-lg object-cover border border-[var(--border)]" />
        ) : (
          <div className="w-10 h-10 rounded-lg border border-dashed border-[var(--border)] flex items-center justify-center text-[var(--text-3)]">
            <Upload className="w-4 h-4" />
          </div>
        )}
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={uploading}
          className="text-[12.5px] px-3 py-1.5 rounded-lg border border-[var(--border)] hover:bg-[var(--surface-2)] transition-colors disabled:opacity-60"
        >
          {uploading ? <Loader2 className="w-3.5 h-3.5 animate-spin inline mr-1.5" /> : null}
          {value ? 'Replace' : 'Upload image'}
        </button>
        {value && (
          <button
            type="button"
            onClick={() => onChange(null)}
            className="text-[var(--text-3)] hover:text-red-500 dark:hover:text-red-400"
            aria-label="Remove image"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}
        <input
          ref={inputRef}
          type="file"
          accept="image/png,image/jpeg,image/gif,image/webp"
          className="hidden"
          onChange={e => handleFile(e.target.files?.[0])}
        />
      </div>
    </div>
  )
}
