"use client"

import { useState } from "react"
import { CircleAlertIcon, GavelIcon } from "lucide-react"

import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@workspace/ui/components/alert"
import { Button } from "@workspace/ui/components/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@workspace/ui/components/dialog"
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@workspace/ui/components/field"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@workspace/ui/components/select"
import { Spinner } from "@workspace/ui/components/spinner"
import { Textarea } from "@workspace/ui/components/textarea"

import { api, errorMessage, type HrAnswer } from "@/lib/api"

// The pass mark in questions.md is 3.
const SCORES = [
  { label: "Pick a score", value: null },
  { label: "1 · below the bar", value: 1 },
  { label: "2 · below the bar", value: 2 },
  { label: "3 · meets the bar", value: 3 },
  { label: "4 · meets the bar", value: 4 },
]

export function OverrideDialog({
  answer,
  onSaved,
}: {
  answer: HrAnswer
  onSaved: () => Promise<void>
}) {
  const [open, setOpen] = useState(false)
  const [score, setScore] = useState<number | null>(answer.hr_score)
  const [reason, setReason] = useState(answer.hr_reason ?? "")
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const title = answer.hr_score === null ? "Override score" : "Change HR score"

  async function save(e: React.FormEvent) {
    e.preventDefault()
    setPending(true)
    setError(null)
    try {
      // The API rejects a blank reason too (422), so this check is for the user, not for safety.
      await api(`/api/hr/answers/${answer.id}/override`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ score, reason }),
      })
      await onSaved()
      setOpen(false)
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setPending(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button variant="outline" size="sm" />}>
        <GavelIcon data-icon="inline-start" />
        {title}
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={save} className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
            <DialogDescription>
              {answer.question_id}. {answer.question_text} Your score replaces
              the AI suggestion and is the one that counts.
            </DialogDescription>
          </DialogHeader>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor={`score-${answer.id}`}>Score</FieldLabel>
              <Select items={SCORES} value={score} onValueChange={setScore}>
                <SelectTrigger id={`score-${answer.id}`} className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {SCORES.filter((s) => s.value !== null).map((s) => (
                      <SelectItem key={s.value} value={s.value}>
                        {s.label}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </Field>
            <Field>
              <FieldLabel htmlFor={`reason-${answer.id}`}>Reason</FieldLabel>
              <Textarea
                id={`reason-${answer.id}`}
                rows={4}
                required
                placeholder="Why this score?"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
              <FieldDescription>
                Required. Saved with your email and the time.
              </FieldDescription>
            </Field>
          </FieldGroup>
          {error && (
            <Alert variant="destructive">
              <CircleAlertIcon />
              <AlertTitle>Score not saved</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          <DialogFooter>
            <DialogClose render={<Button variant="outline" />}>Cancel</DialogClose>
            <Button
              type="submit"
              disabled={score === null || !reason.trim() || pending}
            >
              {pending && <Spinner data-icon="inline-start" />}
              Save score
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
