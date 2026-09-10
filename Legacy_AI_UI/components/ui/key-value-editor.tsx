import { Input } from './input'
import { Button } from './button'
import { Trash2, Plus } from 'lucide-react'

interface KVPair {
  key: string
  value: string
}

interface KeyValueEditorProps {
  items: KVPair[]
  onChange: (items: KVPair[]) => void
  label?: string
}

export function KeyValueEditor({
  items,
  onChange,
  label,
}: KeyValueEditorProps) {
  const updateItem = (index: number, key: string, value: string) => {
    const newItems = [...items]
    newItems[index] = { key, value }
    onChange(newItems)
  }

  const removeItem = (index: number) => {
    onChange(items.filter((_, i) => i !== index))
  }

  const addItem = () => {
    onChange([...items, { key: '', value: '' }])
  }

  return (
    <div className="space-y-3">
      {label && <label className="text-[14px] font-medium">{label}</label>}
      <div className="space-y-2">
        {items.map((item, index) => (
          <div key={index} className="flex gap-2 items-center">
            <Input
              placeholder="Key"
              value={item.key}
              onChange={(e) => updateItem(index, e.target.value, item.value)}
              className="flex-1"
            />
            <span className="text-[var(--text-3)]">:</span>
            <Input
              placeholder="Value"
              value={item.value}
              onChange={(e) => updateItem(index, item.key, e.target.value)}
              className="flex-1"
            />
            <Button
              variant="ghost"
              size="xs"
              onClick={() => removeItem(index)}
            >
              <Trash2 className="w-4 h-4" />
            </Button>
          </div>
        ))}
      </div>
      <Button
        variant="ghost"
        size="sm"
        onClick={addItem}
        className="w-full border border-dashed border-[var(--border-2)]"
      >
        <Plus className="w-4 h-4" /> Add field
      </Button>
    </div>
  )
}
