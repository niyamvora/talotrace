import {
  CircleCheckIcon,
  CircleXIcon,
  ClockIcon,
  UserRoundIcon,
} from "lucide-react"

import { Badge } from "@workspace/ui/components/badge"
import { Spinner } from "@workspace/ui/components/spinner"

import type { JobStatus } from "@/lib/api"

// Icon + label, not colour alone: the states that need HR (needs a person, failed) are the loudest.
const STATUS = {
  needs_person: { label: "Needs a person", variant: "default", Icon: UserRoundIcon },
  failed: { label: "Failed", variant: "destructive", Icon: CircleXIcon },
  running: { label: "Scoring", variant: "outline", Icon: Spinner },
  queued: { label: "Queued", variant: "outline", Icon: ClockIcon },
  scored: { label: "Scored", variant: "secondary", Icon: CircleCheckIcon },
} as const

export function StatusBadge({
  status,
  count,
}: {
  status: JobStatus
  count?: number
}) {
  const { label, variant, Icon } = STATUS[status]
  return (
    <Badge variant={variant}>
      <Icon data-icon="inline-start" />
      {label}
      {count !== undefined && ` · ${count}`}
    </Badge>
  )
}

export function StatusCounts({
  counts,
}: {
  counts: Partial<Record<JobStatus, number>>
}) {
  const shown = (Object.keys(STATUS) as JobStatus[]).filter((s) => counts[s])
  if (!shown.length) return <span className="text-muted-foreground">—</span>
  return (
    <div className="flex flex-wrap gap-1.5">
      {shown.map((s) => (
        <StatusBadge key={s} status={s} count={counts[s]} />
      ))}
    </div>
  )
}
