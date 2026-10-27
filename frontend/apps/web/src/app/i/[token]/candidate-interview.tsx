"use client"

import { useCallback, useEffect, useState } from "react"
import { CircleAlertIcon, CircleCheckIcon, LinkIcon } from "lucide-react"

import {
  Alert,
  AlertAction,
  AlertDescription,
  AlertTitle,
} from "@workspace/ui/components/alert"
import { Button } from "@workspace/ui/components/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@workspace/ui/components/card"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@workspace/ui/components/empty"
import {
  Field,
  FieldDescription,
  FieldError,
  FieldLabel,
} from "@workspace/ui/components/field"
import { Input } from "@workspace/ui/components/input"
import { Progress, ProgressLabel } from "@workspace/ui/components/progress"
import { Skeleton } from "@workspace/ui/components/skeleton"
import { Spinner } from "@workspace/ui/components/spinner"
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@workspace/ui/components/tabs"
import { Textarea } from "@workspace/ui/components/textarea"

import {
  api,
  ApiError,
  errorMessage,
  formatTime,
  type Interview,
  type Receipt,
} from "@/lib/api"

const MAX_AUDIO_BYTES = 25 * 1024 * 1024 // same limit the API enforces

export function CandidateInterview({ token }: { token: string }) {
  const [interview, setInterview] = useState<Interview | null>(null)
  const [loadError, setLoadError] = useState<unknown>(null)
  const [receipt, setReceipt] = useState<Receipt | null>(null)

  // The API is the source of truth for where the candidate is, so a reload resumes at the same question.
  const load = useCallback(async () => {
    try {
      setInterview(await api<Interview>(`/api/interview/${token}`))
      setLoadError(null)
    } catch (error) {
      setLoadError(error)
    }
  }, [token])

  useEffect(() => {
    load()
  }, [load])

  if (loadError instanceof ApiError && loadError.status === 404) {
    return (
      <Empty>
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <LinkIcon />
          </EmptyMedia>
          <EmptyTitle>This interview link is not valid</EmptyTitle>
          <EmptyDescription>
            Check that you opened the full link from your invite email.
          </EmptyDescription>
        </EmptyHeader>
      </Empty>
    )
  }

  if (!interview) {
    return loadError ? (
      <Alert variant="destructive" className="mx-auto max-w-2xl">
        <CircleAlertIcon />
        <AlertTitle>Could not load your interview</AlertTitle>
        <AlertDescription>{errorMessage(loadError)}</AlertDescription>
        <AlertAction>
          <Button size="sm" variant="outline" onClick={load}>
            Retry
          </Button>
        </AlertAction>
      </Alert>
    ) : (
      <Skeleton className="mx-auto h-80 max-w-2xl" />
    )
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4">
      {receipt && (
        <Alert>
          <CircleCheckIcon />
          <AlertTitle>
            Answer received at {formatTime(receipt.received_at)}
          </AlertTitle>
        </Alert>
      )}
      {interview.done || !interview.question ? (
        <Empty className="border">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <CircleCheckIcon />
            </EmptyMedia>
            <EmptyTitle>All {interview.total} answers received</EmptyTitle>
            <EmptyDescription>
              Thank you. Your {interview.role} interview is complete and you can
              close this page.
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : (
        <QuestionCard
          key={interview.question.id}
          token={token}
          interview={interview}
          onReceived={async (r) => {
            setReceipt(r)
            await load()
          }}
        />
      )}
    </div>
  )
}

function QuestionCard({
  token,
  interview,
  onReceived,
}: {
  token: string
  interview: Interview
  onReceived: (receipt: Receipt) => Promise<void>
}) {
  const question = interview.question!
  const [mode, setMode] = useState<"text" | "audio">("text")
  const [text, setText] = useState("")
  const [file, setFile] = useState<File | null>(null)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fileError =
    file && !file.type.startsWith("audio/")
      ? "Choose an audio file."
      : file && file.size > MAX_AUDIO_BYTES
        ? "The file is larger than 25 MB."
        : null
  const ready = mode === "text" ? text.trim() !== "" : !!file && !fileError

  async function submit() {
    setPending(true)
    setError(null)
    // One key per question, kept until the API confirms: a retry or a second tab resends the same key,
    // so the API stores the answer once.
    const storageKey = `talotrace:${token}:${question.id}`
    let key = localStorage.getItem(storageKey)
    if (!key) {
      key = crypto.randomUUID()
      localStorage.setItem(storageKey, key)
    }
    try {
      let receipt: Receipt
      if (mode === "text") {
        receipt = await api<Receipt>(`/api/interview/${token}/answers`, {
          method: "POST",
          headers: { "Content-Type": "application/json", "Idempotency-Key": key },
          body: JSON.stringify({ question_id: question.id, text }),
        })
      } else {
        const form = new FormData()
        form.append("question_id", question.id)
        form.append("file", file!)
        receipt = await api<Receipt>(`/api/interview/${token}/answers/audio`, {
          method: "POST",
          headers: { "Idempotency-Key": key },
          body: form,
        })
      }
      localStorage.removeItem(storageKey)
      // Stay pending until the next question has loaded, so this one can't be sent twice.
      await onReceived(receipt)
    } catch (e) {
      setError(errorMessage(e))
      setPending(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <Progress value={(interview.answered / interview.total) * 100}>
          <ProgressLabel>
            Question {question.number} of {interview.total}
          </ProgressLabel>
        </Progress>
        <CardDescription>{interview.role} interview</CardDescription>
        <CardTitle className="text-lg">{question.text}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <Tabs value={mode} onValueChange={setMode}>
          <TabsList>
            <TabsTrigger value="text" disabled={pending}>
              Type
            </TabsTrigger>
            <TabsTrigger value="audio" disabled={pending}>
              Upload audio
            </TabsTrigger>
          </TabsList>
          <TabsContent value="text">
            <Field>
              <FieldLabel htmlFor="answer-text" className="sr-only">
                Your answer
              </FieldLabel>
              <Textarea
                id="answer-text"
                rows={8}
                placeholder="Type your answer…"
                value={text}
                disabled={pending}
                onChange={(e) => setText(e.target.value)}
              />
            </Field>
          </TabsContent>
          <TabsContent value="audio">
            <Field data-invalid={!!fileError}>
              <FieldLabel htmlFor="answer-audio">Audio recording</FieldLabel>
              <Input
                id="answer-audio"
                type="file"
                accept="audio/*"
                disabled={pending}
                aria-invalid={!!fileError}
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
              <FieldDescription>Any audio file, up to 25 MB.</FieldDescription>
              <FieldError>{fileError}</FieldError>
            </Field>
          </TabsContent>
        </Tabs>
        {error && (
          <Alert variant="destructive">
            <CircleAlertIcon />
            <AlertTitle>Your answer was not sent</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
            <AlertAction>
              <Button size="sm" variant="outline" onClick={submit}>
                Retry
              </Button>
            </AlertAction>
          </Alert>
        )}
      </CardContent>
      <CardFooter className="justify-end">
        <Button onClick={submit} disabled={!ready || pending}>
          {pending && <Spinner data-icon="inline-start" />}
          Submit answer
        </Button>
      </CardFooter>
    </Card>
  )
}
