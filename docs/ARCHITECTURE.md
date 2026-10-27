# TaloTrace architecture

The system suggests a score and HR decides. A Python API owns all data, rules and permissions. Next.js only displays what the API returns and redirects to sign-in on a `401`. A separate worker calls the model.

```
Browser ──> Next.js :3000 ── rewrites /api/* ──> FastAPI :8000 ──> Postgres <── worker ──> Anthropic API
            /i/[token]         (one origin: no CORS,               (data, rules,   (python -m app.worker,
            /hr/...             cookie just works)                  permissions)    claude-opus-5-5)
```

## Data model (Postgres, `backend/app/models.py`)

| Table | Key columns | Rules enforced by the database |
|---|---|---|
| `roles` | name | name unique |
| `questions` | id `Q1`–`Q6`, text, rubric (the 1–4 guide) | |
| `candidates` | id, role, name, email, `access_token` | token unique (it is the candidate's only credential) |
| `answers` | candidate, question, kind `text`/`audio`, text, audio_path, `idempotency_key`, `is_current`, submitted_at | `UNIQUE(candidate_id, idempotency_key)`: a double submit is one row. Partial unique index on `(candidate_id, question_id) WHERE is_current`: only one answer per question counts. The kind must match its content |
| `scoring_jobs` | **answer_id (PK)**, status, attempts, last_error, needs_person_reason, locked_at | One job per answer. Status is one of `queued, running, scored, failed, needs_person`. A failed job must carry `last_error`, and a needs_person job must carry its reason |
| `scores` | **answer_id (PK)**, ai_score, ai_reason, evidence_quote, model, hr_score, hr_reason, hr_by, hr_at | One score row per answer. Scores are 1–4. An AI score needs a reason. An HR override needs a non-blank reason, `hr_by` and `hr_at`, written NULL-safe because `length(reason) > 0` alone lets a NULL through |

The rules live in Postgres so that a bug in the API still cannot create a duplicate, a second current answer, or an unexplained override. Constraint names are predictable (e.g. `uq_answers_candidate_id_idempotency_key`).

## API endpoints (full contract: [API.md](API.md))

| Area | Endpoint | Notes |
|---|---|---|
| Candidate (token in the URL) | `GET /api/interview/{token}` | role, progress, and the first unanswered question. No grade fields in any candidate response |
| | `POST /api/interview/{token}/answers` | `Idempotency-Key` header. The same key returns the same receipt `{answer_id, received_at}` |
| | `POST /api/interview/{token}/answers/audio` | `audio/*` only, max 25 MB, stored under a server-generated name |
| HR sign-in (MOCK) | `POST /api/hr/login` `/logout`, `GET /api/hr/me` | "Continue with Google / Facebook" sends only an email. The API signs it into an httpOnly cookie |
| HR (cookie required) | `GET /api/hr/roles`, `GET /api/hr/roles/{id}/candidates` | status counts per role, and every answer with its status, which answer counts, the suggestion and any override, plus each candidate's interview link |
| | `POST /api/hr/answers/{id}/override` | score 1–4 and a required reason. `409` on a superseded answer |
| | `POST /api/hr/jobs/{id}/retry`, `GET /api/hr/answers/{id}/audio` | retry works only on `failed` or `needs_person` answers. Audio is HR-only |

Sign-in is enforced once, on the whole `/api/hr` router. A test reads every `/api/hr` route from the app's OpenAPI schema and fails if any of them answers without sign-in.

## How an answer becomes a score

1. **Submit:** the candidate posts an answer with an `Idempotency-Key`.
   - The API locks the candidate's row (`SELECT … FOR UPDATE`), so a double click or two tabs are handled one at a time.
   - The same key returns the stored receipt.
   - Otherwise, in **one transaction**: the previous answer to that question is marked superseded, its job is deleted if still `queued`, and the new answer is inserted with its job.
2. **Triage:** an empty answer or an audio-only answer becomes `needs_person` at once and never reaches the model. Everything else becomes `queued`.
3. **Claim:** `python -m app.worker` takes the oldest queued job with `FOR UPDATE SKIP LOCKED`, so several workers never take the same job. It marks the job `running` and commits. No lock is held during the model call.
4. **Score:** one `client.beta.messages.parse` call to `claude-opus-5-5`.
   - The system prompt holds the role, the question and the rubric. The answer goes inside `<answer>` tags, marked as untrusted data the model must never obey.
   - The output must match a Pydantic schema: score, reason, evidence_quote, injection_attempt, needs_person.
   - If the model declines, Anthropic's server-side fallback re-runs the request on another model.
5. **Check:** the server checks the output again before storing it: the score is a whole number 1–4, the reason isn't empty, and the evidence quote really appears in the answer.
6. **Store:** in one transaction, under the same answer-row lock that HR's override and retry take:

   | Result | Stored as |
   |---|---|
   | Valid output | `scored` |
   | Injection flagged, model says a person must judge, refusal, or cut-off output | `needs_person` with the reason. The suggestion is stored, but the API never shows it as a number |
   | Rejected output, or an API error after 2 retries with backoff | `failed` with `last_error`. HR can retry |

7. **Recovery:** a job left `running` by a crashed worker goes back to `queued` after 10 minutes. A job that crashes its worker 3 times becomes `failed`.

On the data pack: 28 queued → 26 scored, plus A019 (prompt injection) and A012 (off-topic) → needs a person, 0 failed. Against `hr_reference_scores.csv`, 7 of the 8 comparable answers match HR exactly and all 8 are within one point.

## What we chose not to build, and why

| Not built | Why / what we would do next |
|---|---|
| Real OAuth and HR accounts | The brief allows a labelled mock. Any email can sign in. A real version would verify the provider's ID token and check an HR allowlist |
| Audio transcription | Optional in the brief. Audio is stored and shown to HR as "needs a person". Next: transcribe into `answers.text`, then queue it like typed text |
| Migrations | `create_all()` at startup is enough for a fixed schema. Add Alembic at the first schema change |
| Override history | `scores` keeps the latest HR decision (who and when). An `overrides` audit table would come first if two scorers disagree |
| Object storage for audio | A local `uploads/` folder. S3 (or similar) for any multi-host deploy |
| Docker or deploy, rate limits, candidate link expiry | Out of scope for a 2–3 hour slice. All three are additive and don't change the data model |
| Redis or Celery queue | Postgres `SKIP LOCKED` gives a durable queue with one less service to run |
