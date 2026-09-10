import { Check } from 'lucide-react'
import { cn } from '@/lib/utils'

interface StepperProps {
  steps: string[]
  currentStep: number
}

export function Stepper({ steps, currentStep }: StepperProps) {
  return (
    <div className="flex items-center w-full gap-3">
      {steps.map((step, index) => (
        <div key={index} className="flex flex-col items-center flex-1">
          {/* Step Circle */}
          <div className="flex items-center w-full gap-3">
            <div
              className={cn(
                'w-8 h-8 rounded-full flex items-center justify-center text-[12px] font-semibold relative transition-colors duration-200',
                index < currentStep
                  ? 'bg-violet-600 text-white'
                  : index === currentStep
                    ? 'border-2 border-violet-600 text-violet-400'
                    : 'border-2 border-[var(--border)] text-[var(--text-3)]'
              )}
            >
              {index < currentStep ? (
                <Check className="w-4 h-4" />
              ) : (
                <span>{index + 1}</span>
              )}
              {index === currentStep && (
                <div className="absolute inset-0 rounded-full border-2 border-violet-600 animate-pulse" />
              )}
            </div>
            {/* Connector Line — fills left-to-right as the step completes, rather
                than an instant color swap (AUDIT.md category 8). */}
            {index < steps.length - 1 && (
              <div className="relative flex-1 h-px mx-2 bg-[var(--border)]">
                <div
                  className="absolute inset-0 origin-left bg-violet-600 transition-transform duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]"
                  style={{ transform: `scaleX(${index < currentStep ? 1 : 0})` }}
                />
              </div>
            )}
          </div>
          {/* Step Label */}
          <span
            className={cn(
              'text-[12px] mt-2 text-center transition-colors duration-200',
              index < currentStep
                ? 'text-violet-400 font-medium'
                : index === currentStep
                  ? 'text-[var(--text-1)] font-semibold'
                  : 'text-[var(--text-3)]'
            )}
          >
            {step}
          </span>
        </div>
      ))}
    </div>
  )
}
