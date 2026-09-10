import { useState } from 'react'
import { X } from 'lucide-react'

interface TagInputProps {
  tags: string[]
  onChange: (tags: string[]) => void
  placeholder?: string
  label?: string
}

export function TagInput({
  tags,
  onChange,
  placeholder = 'Add tags...',
  label,
}: TagInputProps) {
  const [input, setInput] = useState('')

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && input.trim()) {
      e.preventDefault()
      const newTag = input.trim()
      if (!tags.includes(newTag)) {
        onChange([...tags, newTag])
      }
      setInput('')
    } else if (e.key === 'Backspace' && !input && tags.length > 0) {
      onChange(tags.slice(0, -1))
    }
  }

  const removeTag = (index: number) => {
    onChange(tags.filter((_, i) => i !== index))
  }

  return (
    <div className="space-y-2">
      {label && <label className="text-[14px] font-medium">{label}</label>}
      <div className="glass flex flex-wrap gap-1.5 p-2 min-h-[44px] rounded-[var(--radius-md)] border border-[var(--border)]">
        {tags.map((tag, index) => (
          <div
            key={index}
            className="bg-violet-900/50 text-violet-300 rounded-full px-2.5 py-1 text-[12px] flex items-center gap-1"
          >
            {tag}
            <button
              onClick={() => removeTag(index)}
              className="hover:text-violet-200 transition-colors duration-[120ms]"
            >
              <X className="w-3 h-3" />
            </button>
          </div>
        ))}
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className="flex-1 min-w-[120px] bg-transparent text-[14px] placeholder-[var(--text-3)] focus:outline-none"
        />
      </div>
    </div>
  )
}
