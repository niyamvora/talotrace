# TaloTrace API contract

This is what the frontend codes against. The backend (FastAPI) owns all data, rules and permissions. The frontend only displays what it gets and redirects on `401`.

- **Base path:** `/api/...`. Next.js rewrites `/api/*` to FastAPI (`API_URL`, default `http://localhost:8000`), so the browser sees one origin: no CORS setup, and cookies work as-is.
- **Body format:** JSON, except the audio upload, which is multipart.
- **Errors:** FastAPI's shape, `{"detail": "..."}`. For a `422`, `detail` is either a string or FastAPI's list of validation errors.
- **Timestamps:** ISO 8601 with a UTC offset, e.g. `2026-10-27T11:27:42.750913+05:30`.
- **Live docs:** Swagger at `http://localhost:8000/docs` when the API is running.

| Area | Status |
|---|---|
| Candidate API | **live** (Step 4) |
| HR sign-in (mock Google / Facebook) | **live** (Step 5, part 1) |
| HR data, override, retry, audio | contract fixed, building next (Step 5) |

---

## Candidate

A candidate has no account. The secret `token` in their link (`/i/{token}`) is their only credential. These responses never include a score, a reason, a status or another candidate's data.

### `GET /api/interview/{token}`

```json
{
  "role": "Backend Engineer",
  "total": 6,
  "answered": 2,
  "done": false,
  "question": { "id": "Q3", "number": 3, "text": "Tell us about a disagreement with a colleague. How did you resolve it?" }
}
```

- `question` is the lowest-numbered question that has no current answer. It is `null` when `done` is `true`.
- A reload calls this again and lands on the same question. All progress lives on the server.
- `404` means the token is unknown.

### `POST /api/interview/{token}/answers`: typed answer

Headers: `Idempotency-Key: <1-100 chars>` (required). Body:

```json
{ "question_id": "Q3", "text": "..." }
```

Response `200`, the receipt to show ("Answer received at 14:03"):

```json
{ "answer_id": 41, "received_at": "2026-10-27T14:03:09.120000+05:30" }
```

- **Same key again:** returns the same receipt and creates no new row, even if the body differs. Make **one key per attempt to answer a question**, keep it until you get a 2xx, and resend that same key on retry. A double click or a network retry is then always safe.
- **New key, question already answered:** the new answer replaces the old one, which is kept but marked superseded. HR sees which one counts.
- **Errors:**
  - `404`: unknown token.
  - `422`: blank text, text over 20,000 characters, unknown `question_id`, or missing `Idempotency-Key`.

### `POST /api/interview/{token}/answers/audio`: audio upload

Headers: `Idempotency-Key` (required). Multipart form fields: `question_id`, `file`.

- The response is the same receipt as for a typed answer, with the same idempotency rules.
- The audio is stored and HR can see it arrived. It is not transcribed, so its status is `needs_person`.
- **Errors:**
  - `415`: the file's content type is not `audio/*`.
  - `413`: the file is over 25 MB.
  - `422`: the file is empty, the question is unknown, or the key is missing.

---

## HR sign-in: MOCK Google / Facebook

There is no real OAuth and no password. The flow should *feel* like a social sign-in, but it is a labelled mock.

1. `/hr/login` shows **Continue with Google** and **Continue with Facebook**, plus a visible **"Mock sign-in"** badge.
2. Clicking a button goes to a mock provider screen (e.g. `/hr/login/google`) that asks **only for an email**.
   - Never ask for a password.
   - Keep a clear "MOCK: no real Google/Facebook account is used" label on this screen too. The brief treats an unlabelled mock as a red flag.
3. That screen calls `POST /api/hr/login`, then redirects to `/hr`.
4. Every `/api/hr/*` call returns `401` without the cookie. On a `401`, redirect to `/hr/login`.

### `POST /api/hr/login`

```json
{ "provider": "google", "email": "hr@talotrace.ai" }
```

- **Response `200`:** `{ "email": "hr@talotrace.ai", "provider": "google" }`, plus a signed httpOnly cookie `talotrace_hr` (SameSite=Lax, 8 hours).
- Any well-formed email is accepted. This is a mock, so there is no allowlist.
- `422` means a malformed email, or a `provider` other than `google` or `facebook`.

### `GET /api/hr/me`

`200 { "email": "...", "provider": "google" | "facebook" }` while signed in, or `401`. Use it for the "Signed in as ... (mock)" header.

### `POST /api/hr/logout`

`204`. Clears the cookie.

---

## HR data (Step 5, next)

All routes need the cookie. Without it they return `401`.

### `GET /api/hr/roles`

```json
[
  { "id": 1, "name": "Backend Engineer", "candidates": 5,
    "counts": { "queued": 6, "running": 0, "scored": 0, "failed": 0, "needs_person": 1 } }
]
```

`counts` covers current answers only. Superseded answers have no job and are not counted.

### `GET /api/hr/roles/{role_id}/candidates`

```json
{
  "role": { "id": 1, "name": "Backend Engineer" },
  "candidates": [ { "id": "C2041", "name": "Nhi Van Tran", "email": "...", "answers": [Answer] } ]
}
```

`404` means the role is unknown.

**`Answer`:**

| field | type | notes |
|---|---|---|
| `id` | int | answer id; also used by override, retry and audio |
| `question_id`, `question_text` | str | |
| `kind` | `"text" \| "audio"` | an audio answer can be played from `/api/hr/answers/{id}/audio` |
| `text` | str \| null | null for audio |
| `duration_seconds` | int \| null | |
| `submitted_at` | ISO str | |
| `is_current` | bool | `false` = superseded, does **not** count |
| `status` | `"queued" \| "running" \| "scored" \| "failed" \| "needs_person" \| null` | `null` only for a superseded answer that never got a job |
| `attempts` | int | |
| `last_error` | str \| null | set when `failed` |
| `needs_person_reason` | str \| null | set when `needs_person`, e.g. "empty answer", "audio received, not transcribed" |
| `ai_score`, `ai_reason`, `evidence_quote` | int 1-4 / str / str, or null | **non-null only when `status == "scored"`**. A failed or needs-a-person answer never shows a number |
| `hr_score`, `hr_reason`, `hr_by`, `hr_at` | int 1-4 / str / str / ISO str, or null | HR's override. Can be set on any status. When set, it is the score that counts |

### `POST /api/hr/answers/{answer_id}/override`

```json
{ "score": 2, "reason": "Contribution stays vague; no checkable result." }
```

- **Response `200`:** the updated `Answer`. `hr_by` is the signed-in email.
- **Errors:**
  - `422`: score not 1-4, or a blank reason.
  - `409`: the answer is superseded.
  - `404`: unknown answer.

### `POST /api/hr/jobs/{answer_id}/retry`

- **Response `200`:** the updated `Answer`, now `queued`.
- `409` unless the status is `failed` or `needs_person`.
- `404`: unknown answer.

### `GET /api/hr/answers/{answer_id}/audio`

Returns the audio file, which can go straight into `<audio src>` since the cookie is sent with it. `404` if the answer has no audio.

### Polling

While any answer is `queued` or `running`, re-fetch the candidates endpoint every 5 seconds.
