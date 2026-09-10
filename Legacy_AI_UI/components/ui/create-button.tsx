import * as React from 'react'
import { Plus } from 'lucide-react'

import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'

interface CreateButtonProps extends Omit<React.ComponentProps<typeof Button>, 'variant'> {
  icon?: React.ComponentType<{ className?: string }>
}

function CreateButton({
  icon: Icon = Plus,
  size = 'default',
  className,
  children,
  ...props
}: CreateButtonProps) {
  return (
    <Button
      variant="primary"
      size={size}
      className={cn(
        'rounded-full pl-2.5 pr-4 shadow-sm shadow-violet-600/25 transition-shadow hover:shadow-md hover:shadow-violet-600/35',
        className,
      )}
      {...props}
    >
      <span className="mr-1.5 flex size-5 items-center justify-center rounded-full bg-white/25">
        <Icon className="size-3" />
      </span>
      {children}
    </Button>
  )
}

export { CreateButton }
