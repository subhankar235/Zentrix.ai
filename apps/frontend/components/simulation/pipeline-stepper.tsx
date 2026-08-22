import { Check } from 'lucide-react'
import type { PipelineStage } from '@/types/types'
import { cn } from '@/lib/utils'

export const PIPELINE_STAGES: PipelineStage[] = [
  'HypoPG filter',
  'ML prediction',
  'Shadow DB simulation',
  'Statistical verification',
  'Skeptic review',
  'Policy engine',
]

export function PipelineStepper({
  currentStage,
  completed,
}: {
  currentStage: PipelineStage
  completed: boolean
}) {
  const idx = PIPELINE_STAGES.indexOf(currentStage)

  return (
    <ol className="flex flex-wrap items-center gap-y-3">
      {PIPELINE_STAGES.map((stage, i) => {
        const done = completed || i < idx
        const current = !completed && i === idx
        return (
          <li key={stage} className="flex items-center">
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  'flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-[10px] font-semibold',
                  done && 'border-success/40 bg-success/15 text-success',
                  current && 'border-info/50 bg-info/15 text-info',
                  !done && !current && 'border-border text-muted-foreground',
                )}
              >
                {done ? (
                  <Check className="h-3 w-3" />
                ) : current ? (
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />
                ) : (
                  i + 1
                )}
              </span>
              <span
                className={cn(
                  'text-xs',
                  done && 'text-muted-foreground',
                  current && 'font-medium text-foreground',
                  !done && !current && 'text-muted-foreground/70',
                )}
              >
                {stage}
              </span>
            </div>
            {i < PIPELINE_STAGES.length - 1 ? (
              <span
                aria-hidden="true"
                className={cn('mx-3 hidden h-px w-6 sm:block', done ? 'bg-success/40' : 'bg-border')}
              />
            ) : null}
          </li>
        )
      })}
    </ol>
  )
}
