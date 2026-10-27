"use client"

import { Fragment, useState } from "react"
import Link from "next/link"
import {
  ArrowLeftIcon,
  CheckIcon,
  ChevronRightIcon,
  LinkIcon,
  SearchXIcon,
} from "lucide-react"

import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
import {
  Empty,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@workspace/ui/components/empty"
import { Skeleton } from "@workspace/ui/components/skeleton"
import { Spinner } from "@workspace/ui/components/spinner"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@workspace/ui/components/table"
import { cn } from "@workspace/ui/lib/utils"

import { LoadError } from "@/components/load-error"
import { StatusCounts } from "@/components/status-badge"
import { useApi } from "@/hooks/use-api"
import {
  ApiError,
  type HrCandidate,
  type JobStatus,
  type RoleCandidates as RoleCandidatesData,
} from "@/lib/api"

import { AnswerCard } from "./answer-card"

// ponytail: the data pack has 6 questions for every role; have the API send the total if that ever varies.
const QUESTIONS = 6

const isPending = (d: RoleCandidatesData) =>
  d.candidates.some((c) =>
    c.answers.some((a) => a.status === "queued" || a.status === "running")
  )

export function RoleCandidates({ roleId }: { roleId: string }) {
  const { data, error, load, polling } = useApi<RoleCandidatesData>(
    `/api/hr/roles/${roleId}/candidates`,
    isPending
  )
  const [open, setOpen] = useState<Set<string>>(new Set())

  function toggle(id: string) {
    setOpen((prev) => {
      const next = new Set(prev)
      if (!next.delete(id)) next.add(id)
      return next
    })
  }

  if (!data) {
    if (error instanceof ApiError && error.status === 404) {
      return (
        <Empty className="border">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <SearchXIcon />
            </EmptyMedia>
            <EmptyTitle>Role not found</EmptyTitle>
          </EmptyHeader>
          <BackToRoles />
        </Empty>
      )
    }
    return error ? (
      <LoadError title="Could not load candidates" error={error} onRetry={load} />
    ) : (
      <Skeleton className="h-96" />
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <BackToRoles />
      <Card>
        <CardHeader>
          <CardTitle>{data.role.name}</CardTitle>
          <CardDescription>
            {data.candidates.length} candidates. Open a row to see the answers,
            suggested scores and reasons.
          </CardDescription>
          {polling && (
            <CardAction>
              <Badge variant="outline">
                <Spinner data-icon="inline-start" />
                Scoring in progress, refreshing every 5 s
              </Badge>
            </CardAction>
          )}
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {error !== null && (
            <LoadError title="Could not refresh" error={error} onRetry={load} />
          )}
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10" />
                <TableHead>Candidate</TableHead>
                <TableHead>Answered</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Average score</TableHead>
                <TableHead className="text-right">Interview link</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.candidates.map((c) => (
                <CandidateRows
                  key={c.id}
                  candidate={c}
                  open={open.has(c.id)}
                  onToggle={() => toggle(c.id)}
                  onChanged={load}
                />
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}

function CandidateRows({
  candidate,
  open,
  onToggle,
  onChanged,
}: {
  candidate: HrCandidate
  open: boolean
  onToggle: () => void
  onChanged: () => Promise<void>
}) {
  const current = candidate.answers.filter((a) => a.is_current)
  const counts: Partial<Record<JobStatus, number>> = {}
  for (const a of current) if (a.status) counts[a.status] = (counts[a.status] ?? 0) + 1
  // HR's score counts when set; the AI score is only non-null once the answer is scored.
  const scores = current
    .map((a) => a.hr_score ?? a.ai_score)
    .filter((s) => s !== null)
  const average = scores.length
    ? scores.reduce((sum, s) => sum + s, 0) / scores.length
    : null
  const answers = [...candidate.answers].sort(
    (a, b) =>
      a.question_id.localeCompare(b.question_id) ||
      a.submitted_at.localeCompare(b.submitted_at)
  )

  return (
    <Fragment>
      <TableRow className="cursor-pointer" onClick={onToggle}>
        <TableCell>
          <Button
            variant="ghost"
            size="icon-sm"
            aria-expanded={open}
            aria-label={`Answers from ${candidate.name}`}
          >
            <ChevronRightIcon className={cn("transition-transform", open && "rotate-90")} />
          </Button>
        </TableCell>
        <TableCell>
          <div className="font-medium">{candidate.name}</div>
          <div className="text-muted-foreground">{candidate.email}</div>
        </TableCell>
        <TableCell>
          {current.length} of {QUESTIONS}
        </TableCell>
        <TableCell>
          <StatusCounts counts={counts} />
        </TableCell>
        <TableCell className="text-right tabular-nums">
          {average === null ? (
            <span className="text-muted-foreground">—</span>
          ) : (
            <>
              {average.toFixed(1)}
              <span className="text-muted-foreground">
                {" "}
                ({scores.length} scored)
              </span>
            </>
          )}
        </TableCell>
        <TableCell className="text-right">
          <CopyLink token={candidate.access_token} />
        </TableCell>
      </TableRow>
      {open && (
        <TableRow className="hover:bg-transparent">
          <TableCell colSpan={6} className="bg-muted/30 p-4 whitespace-normal">
            <div className="grid gap-3 lg:grid-cols-2">
              {answers.map((a) => (
                <AnswerCard key={a.id} answer={a} onChanged={onChanged} />
              ))}
            </div>
          </TableCell>
        </TableRow>
      )}
    </Fragment>
  )
}

// Built from the page's own origin, so the link points at whichever host and port HR is using.
function CopyLink({ token }: { token: string }) {
  const [copied, setCopied] = useState(false)

  async function copy(e: React.MouseEvent) {
    e.stopPropagation() // the row click toggles the answers
    const link = `${window.location.origin}/i/${token}`
    try {
      await navigator.clipboard.writeText(link)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // ponytail: clipboard is blocked outside https/localhost; let HR copy it by hand
      window.prompt("Copy this interview link", link)
    }
  }

  return (
    <Button variant="outline" size="sm" onClick={copy}>
      {copied ? (
        <CheckIcon data-icon="inline-start" />
      ) : (
        <LinkIcon data-icon="inline-start" />
      )}
      {copied ? "Copied" : "Copy link"}
    </Button>
  )
}

function BackToRoles() {
  return (
    <Button
      variant="ghost"
      className="self-start"
      render={<Link href="/hr" />}
      nativeButton={false}
    >
      <ArrowLeftIcon data-icon="inline-start" />
      All roles
    </Button>
  )
}
