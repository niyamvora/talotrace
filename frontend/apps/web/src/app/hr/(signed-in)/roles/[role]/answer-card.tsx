"use client"

import { useState } from "react"
import {
  CircleXIcon,
  GavelIcon,
  RotateCwIcon,
  UserRoundIcon,
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
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
import { Spinner } from "@workspace/ui/components/spinner"
import { cn } from "@workspace/ui/lib/utils"

import { StatusBadge } from "@/components/status-badge"
import {
  api,
  errorMessage,
  formatDateTime,
  type HrAnswer,
} from "@/lib/api"

export function AnswerCard({
  answer,
  onChanged,
}: {
  answer: HrAnswer
  onChanged: () => Promise<void>
}) {
  return (
    <Card size="sm" className={cn(!answer.is_current && "opacity-70")}>
      <CardHeader>
        <CardTitle>
          {answer.question_id}. {answer.question_text}
        </CardTitle>
        <CardDescription>
          {answer.kind === "audio" ? "Audio" : "Typed"} answer,{" "}
          {formatDateTime(answer.submitted_at)}
          {answer.duration_seconds !== null &&
            `, ${answer.duration_seconds} s`}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="flex flex-wrap gap-1.5">
          {answer.status && <StatusBadge status={answer.status} />}
          {answer.is_current ? (
            <Badge variant="secondary">Counts</Badge>
          ) : (
            <Badge variant="outline">Superseded by a newer answer</Badge>
          )}
        </div>

        {answer.kind === "audio" ? (
          <audio
            controls
            preload="none"
            src={`/api/hr/answers/${answer.id}/audio`}
            className="w-full"
          />
        ) : answer.text?.trim() ? (
          <p className="max-h-48 overflow-y-auto rounded-lg border bg-background p-3 whitespace-pre-wrap">
            {answer.text}
          </p>
        ) : (
          <p className="text-muted-foreground italic">Empty answer</p>
        )}

        <Verdict answer={answer} onChanged={onChanged} />

        {answer.hr_score !== null && (
          <Alert>
            <GavelIcon />
            <AlertTitle>HR score {answer.hr_score} / 4, this counts</AlertTitle>
            <AlertDescription>
              <p>{answer.hr_reason}</p>
              <p className="text-xs">
                {answer.hr_by}, {answer.hr_at && formatDateTime(answer.hr_at)}
              </p>
            </AlertDescription>
          </Alert>
        )}
      </CardContent>
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
        <div className="flex flex-col gap-1.5">
          <p className="font-medium">
            AI suggests {answer.ai_score} / 4
            {answer.hr_score !== null && (
              <span className="font-normal text-muted-foreground">
                {" "}
                (replaced by HR)
              </span>
            )}
          </p>
          <p className="text-muted-foreground">{answer.ai_reason}</p>
          {answer.evidence_quote && (
            <blockquote className="border-l-2 pl-3 italic">
              “{answer.evidence_quote}”
            </blockquote>
          )}
        </div>
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
