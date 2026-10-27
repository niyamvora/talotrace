"use client"

import { useState } from "react"
import {
  CircleCheckIcon,
  CircleMinusIcon,
  CircleXIcon,
  GavelIcon,
  RotateCwIcon,
  SparklesIcon,
  UserRoundIcon,
  type LucideIcon,
} from "lucide-react"

import {
  Alert,
  AlertAction,
  AlertDescription,
  AlertTitle,
} from "@workspace/ui/components/alert"
import { Badge } from "@workspace/ui/components/badge"
import { Button } from "@workspace/ui/components/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
import { Progress } from "@workspace/ui/components/progress"
import { Spinner } from "@workspace/ui/components/spinner"
import { cn } from "@workspace/ui/lib/utils"

import { StatusBadge } from "@/components/status-badge"
import {
  api,
  errorMessage,
  formatDateTime,
  type HrAnswer,
} from "@/lib/api"

import { OverrideDialog } from "./override-dialog"

export function AnswerCard({
  answer,
  onChanged,
}: {
  answer: HrAnswer
  onChanged: () => Promise<void>
}) {
  return (
    // Fixed-height header, badge row and answer box, and the footer pinned to the bottom, so two cards
    // side by side line up section for section whatever the question or answer length.
    <Card size="sm" className={cn(!answer.is_current && "opacity-70")}>
      <CardHeader>
        <CardTitle className="line-clamp-2 min-h-[2lh]" title={answer.question_text}>
          {answer.question_id}. {answer.question_text}
        </CardTitle>
        <CardDescription className="truncate">
          {answer.kind === "audio" ? "Audio" : "Typed"} answer,{" "}
          {formatDateTime(answer.submitted_at)}
          {answer.duration_seconds !== null &&
            `, ${answer.duration_seconds} s`}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-3">
        <div className="flex h-5 gap-1.5">
          {answer.status && <StatusBadge status={answer.status} />}
          {answer.is_current ? (
            <Badge variant="secondary">Counts</Badge>
          ) : (
            <Badge variant="outline">Superseded by a newer answer</Badge>
          )}
        </div>

        {answer.kind === "audio" ? (
          <div className="flex h-48 items-center rounded-lg border bg-background p-3">
            <audio
              controls
              preload="none"
              src={`/api/hr/answers/${answer.id}/audio`}
              className="w-full"
            />
          </div>
        ) : (
          <p
            className={cn(
              "h-48 overflow-y-auto rounded-lg border bg-background p-3 whitespace-pre-wrap",
              !answer.text?.trim() && "text-muted-foreground italic"
            )}
          >
            {answer.text?.trim() ? answer.text : "Empty answer"}
          </p>
        )}

        <Verdict answer={answer} onChanged={onChanged} />

        {answer.hr_score !== null && (
          <ScorePanel icon={GavelIcon} label="HR decision · counts" score={answer.hr_score}>
            <Section label="Reason">{answer.hr_reason}</Section>
            <p className="text-xs text-muted-foreground">
              {answer.hr_by}
              {answer.hr_at && ` · ${formatDateTime(answer.hr_at)}`}
            </p>
          </ScorePanel>
        )}
      </CardContent>
      {answer.is_current && (
        <CardFooter className="justify-end">
          <OverrideDialog answer={answer} onSaved={onChanged} />
        </CardFooter>
      )}
    </Card>
  )
}

// What the scorer said. A number only ever appears for a scored answer, never for failed or needs a person.
function Verdict({
  answer,
  onChanged,
}: {
  answer: HrAnswer
  onChanged: () => Promise<void>
}) {
  switch (answer.status) {
    case "scored":
      return (
        <ScorePanel
          icon={SparklesIcon}
          label="AI suggestion"
          score={answer.ai_score!}
          replaced={answer.hr_score !== null}
        >
          <Section label="Why">{answer.ai_reason}</Section>
          {answer.evidence_quote && (
            <Section label="Evidence from the answer">
              <blockquote className="border-l-2 border-primary/40 pl-3 text-muted-foreground italic">
                “{answer.evidence_quote}”
              </blockquote>
            </Section>
          )}
        </ScorePanel>
      )
    case "failed":
      return (
        <Alert variant="destructive">
          <CircleXIcon />
          <AlertTitle>
            Scoring failed after {answer.attempts}{" "}
            {answer.attempts === 1 ? "attempt" : "attempts"}
          </AlertTitle>
          <AlertDescription>{answer.last_error}</AlertDescription>
          <AlertAction>
            <RetryButton answerId={answer.id} onChanged={onChanged} />
          </AlertAction>
        </Alert>
      )
    case "needs_person":
      return (
        <Alert>
          <UserRoundIcon />
          <AlertTitle>Needs a person</AlertTitle>
          <AlertDescription className="first-letter:uppercase">
            {answer.needs_person_reason}. Score it yourself with Override.
          </AlertDescription>
        </Alert>
      )
    case "queued":
    case "running":
      return (
        <p className="text-muted-foreground">
          {answer.status === "queued"
            ? "Waiting for the scorer."
            : "The scorer is working on this answer."}
        </p>
      )
    default:
      return (
        <p className="text-muted-foreground">
          Not scored: a newer answer to this question counts instead.
        </p>
      )
  }
}

function RetryButton({
  answerId,
  onChanged,
}: {
  answerId: number
  onChanged: () => Promise<void>
}) {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function retry() {
    setPending(true)
    setError(null)
    try {
      await api(`/api/hr/jobs/${answerId}/retry`, { method: "POST" })
      await onChanged()
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setPending(false)
    }
  }

  return (
    <Button
      size="sm"
      variant="outline"
      onClick={retry}
      disabled={pending}
      title={error ?? undefined}
      aria-invalid={!!error}
    >
      {pending ? (
        <Spinner data-icon="inline-start" />
      ) : (
        <RotateCwIcon data-icon="inline-start" />
      )}
      {error ? "Retry failed, try again" : "Retry"}
    </Button>
  )
}

// One look at a score: whose it is, the number on a 4-step meter, and whether it meets the bar (3+).
function ScorePanel({
  icon: Icon,
  label,
  score,
  replaced = false,
  children,
}: {
  icon: LucideIcon
  label: string
  score: number
  replaced?: boolean
  children: React.ReactNode
}) {
  const meets = score >= 3
  return (
    <div className="flex flex-col gap-3 rounded-lg border bg-background p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
          <Icon className="size-3.5" />
          {label}
        </span>
        {replaced ? (
          <Badge variant="outline">Replaced by HR</Badge>
        ) : (
          <Badge variant={meets ? "secondary" : "outline"}>
            {meets ? (
              <CircleCheckIcon data-icon="inline-start" />
            ) : (
              <CircleMinusIcon data-icon="inline-start" />
            )}
            {meets ? "Meets the bar" : "Below the bar"}
          </Badge>
        )}
      </div>
      <div className={cn("flex items-center gap-3", replaced && "opacity-50")}>
        <p className="shrink-0 tabular-nums">
          <span className="text-2xl font-semibold">{score}</span>
          <span className="text-muted-foreground"> / 4</span>
        </p>
        <Progress
          value={score * 25}
          aria-label={`${label}: ${score} out of 4`}
          className="flex-1"
        />
      </div>
      {children}
    </div>
  )
}

function Section({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <div className="leading-relaxed">{children}</div>
    </div>
  )
}
