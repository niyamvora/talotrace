// Every call goes to /api/*, which next.config rewrites to FastAPI (same origin, so the HR cookie just works).
// The API owns all rules and permissions; the browser only renders and redirects.

export type JobStatus = "queued" | "running" | "scored" | "failed" | "needs_person"

export type Interview = {
  role: string
  total: number
  answered: number
  done: boolean
  question: { id: string; number: number; text: string } | null
}

export type Receipt = { answer_id: number; received_at: string }

export type Provider = "google" | "facebook"

export type HrUser = { email: string; provider: Provider }

export type RoleSummary = {
  id: number
  name: string
  candidates: number
  counts: Record<JobStatus, number>
}

export type HrAnswer = {
  id: number
  question_id: string
  question_text: string
  kind: "text" | "audio"
  text: string | null
  duration_seconds: number | null
  submitted_at: string
  is_current: boolean
  status: JobStatus | null // null: superseded, never scored
  attempts: number
  last_error: string | null
  needs_person_reason: string | null
  ai_score: number | null
  ai_reason: string | null
  evidence_quote: string | null
  hr_score: number | null
  hr_reason: string | null
  hr_by: string | null
  hr_at: string | null
}

export type HrCandidate = {
  id: string
  name: string
  email: string
  answers: HrAnswer[]
}

export type RoleCandidates = {
  role: { id: number; name: string }
  candidates: HrCandidate[]
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message)
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init)
  if (
    res.status === 401 &&
    path.startsWith("/api/hr/") &&
    !window.location.pathname.startsWith("/hr/login")
  ) {
    window.location.assign("/hr/login")
  }
  const body = await res.text()
  const data = body ? JSON.parse(body) : undefined
  if (!res.ok) {
    // FastAPI sends {detail: "..."} or, for validation errors, {detail: [{msg}, ...]}.
    const detail = data?.detail
    const message = Array.isArray(detail)
      ? detail.map((d: { msg: string }) => d.msg).join(", ")
      : (detail ?? `Request failed (${res.status})`)
    throw new ApiError(res.status, message)
  }
  return data as T
}

export function errorMessage(error: unknown) {
  return error instanceof ApiError
    ? error.message
    : "Could not reach the server. Check your connection."
}

export function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString([], {
    dateStyle: "medium",
    timeStyle: "short",
  })
}

export function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  })
}
