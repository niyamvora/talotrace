# TaloTrace

An internal hiring tool where AI suggests a score and HR decides. Candidates answer six interview questions from a personal link. A background worker asks a real language model to score each answer from 1 to 4 against the question's grading guide. HR sees every answer with its suggested score, the reason and an evidence quote, and can override any score with a written reason.

> **Status:** Backend steps 1–6 of 11 are done (setup, data model, seed loader, candidate API, HR API, scoring worker). The roadmap below tracks the rest. API contract: [docs/API.md](docs/API.md).

## Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 (typed `Mapped[]`), psycopg 3, pydantic-settings, managed with **uv** |
| Database | PostgreSQL 17 (`talotrace_dev` for the app, `talotrace_test` for pytest) |
| Scoring | Anthropic SDK, `claude-opus-5-5` (env `SCORER_MODEL`): structured output (Pydantic schema), then our own checks (score 1–4, non-empty reason, evidence quote really in the answer). Refusals fall back server-side to Anthropic's recommended model |
| Job queue | A `scoring_jobs` table plus a `python -m app.worker` loop using `FOR UPDATE SKIP LOCKED`. No Redis or Celery, and jobs survive restarts |
| Frontend | Next.js 16 (App Router, TypeScript, `src/`) with shadcn/ui in a **Turborepo** (pnpm workspaces) |
| Auth | Candidates use an unguessable token in their link. HR uses a **MOCK** "Continue with Google / Facebook" sign-in (email only, no password, no real OAuth) that sets a signed httpOnly cookie. All checks run in the API |

Next.js rewrites `/api/*` to FastAPI, so the browser sees a single origin. That means no CORS setup, and the HR cookie works without extra config.

## Repository layout

```
talotrace/
├── backend/                  FastAPI app, plain uv project
│   ├── app/
│   │   ├── main.py           app, startup create_all, /api/health
│   │   ├── config.py         settings from backend/.env
│   │   ├── db.py             engine, session, Base
│   │   ├── models.py         tables + every UNIQUE/CHECK constraint
│   │   ├── auth.py           MOCK HR sign-in, require_hr
│   │   ├── routes/
│   │   │   ├── candidate.py  /api/interview/{token}/* (no grade fields, ever)
│   │   │   └── hr.py         /api/hr/* (HR only)
│   │   ├── scorer.py         prompt, LLM call, output validation
│   │   ├── worker.py         python -m app.worker
│   │   └── seed.py           python -m app.seed
│   └── tests/
├── frontend/                 Turborepo
│   ├── apps/web/src/         Next.js app (candidate + HR areas)
│   └── packages/ui/src/      shared shadcn/ui components (@workspace/ui)
├── data/                     the challenge data pack (synthetic, committed as-is)
└── docs/                     plan and brief
```

## Getting started

**Prerequisites:** Python 3.12+ with [uv](https://docs.astral.sh/uv/), Node 20.9+ with pnpm, and PostgreSQL 17 running locally.

```bash
# 1. Databases
createdb talotrace_dev
createdb talotrace_test

# 2. Backend (http://localhost:8000)
cd backend
cp .env.example .env          # set ANTHROPIC_API_KEY and SECRET_KEY; edit the two DB URLs if your Postgres user/password differ
uv sync
uv run python -m app.seed     # loads the data pack and prints every candidate link; safe to re-run
uv run uvicorn app.main:app --reload --port 8000
uv run python -m app.worker   # in another terminal: scores queued answers with the real model; Ctrl+C stops after the current one

# 3. Frontend (http://localhost:3000), in a second terminal
cd frontend
pnpm install
pnpm dev
```

Check that it works: `curl localhost:3000/api/health` should return `{"ok":true}`. That request goes through the Next rewrite to FastAPI and then to Postgres.

**Tests:** `cd backend && uv run pytest`. Tests run against `talotrace_test` and never touch the dev database.

### Local database

Both connection strings live in `backend/.env`. The defaults assume a local Postgres with a `postgres` user and no password.

| Database | `.env` key | Used by |
|---|---|---|
| `talotrace_dev` | `DATABASE_URL` | the API, the seed, the worker |
| `talotrace_test` | `TEST_DATABASE_URL` | pytest only. Every table is dropped and recreated on each run, so pytest refuses to start if the two URLs are the same |

- **Tables** are created when the API starts and when the seed runs. There are no migrations yet.
- **Inspect the data:** `psql postgresql://postgres@localhost:5432/talotrace_dev`
- **Start over:** `dropdb talotrace_dev && createdb talotrace_dev && uv run python -m app.seed`. This prints new candidate links.

## Roadmap

- [x] **1. Setup:** repo, data pack, databases, uv backend, Turborepo + Next.js + shadcn frontend
- [x] **2. Data model:** roles, questions, candidates, answers, scoring_jobs, scores, with UNIQUE/CHECK constraints guarding against duplicates and invalid scores
- [x] **3. Seed loader:** loads the pack in one command and is safe to re-run (35 answers: 28 queued, 6 needs a person, A022 superseded), plus one demo candidate per role
- [x] **4. Candidate API:** current question, text answers with an `Idempotency-Key` header, audio upload (audio/* only, max 25 MB), receipts; submissions are serialized per candidate, so a double click is one answer
- [x] **5. HR API:** MOCK sign-in (Google / Facebook, email only), role list with status counts, candidates per role with every answer, override with a required reason, retry for failed / needs-a-person, HR-only audio. A failed answer never shows a number
- [x] **6. Scorer worker:** real LLM call. The answer is passed as untrusted data, the output is validated, retries use backoff, and a job ends as `failed` or `needs_person`, never as a low score
- [ ] **7. Candidate UI:** one question at a time, type or upload audio, "Answer received at 14:03", a reload returns to the same question, retry on error
- [ ] **8. HR UI:** role picker, candidate table, status badges, reason and evidence quote, audio player, override dialog, retry button, polling
- [ ] **9. Tests:** one test for each rule below, using a fake LLM client
- [ ] **10. Docs:** final README plus `docs/ARCHITECTURE.md` (data model, endpoints, submission-to-score flow, what was left out)
- [ ] **11. Verify:** fresh clone, follow this README, seed, worker scores everything, live walkthrough

**Optional, only once the steps above work:** an agreement report against `hr_reference_scores.csv`, a "needs a person" list, a candidate list ordered for review, mocked transcripts for the audio-only answers (labelled MOCK).

## Rules the system enforces

- Submitting the same answer twice creates one answer and one score, and HR sees which answer counts.
- A candidate can never see grades, other candidates or HR pages, even by calling the API directly.
- A failed scoring job is visible to HR with a retry, and is never shown as a low score.
- An answer that tries to instruct the scorer cannot change its score.
- The typed answers in the data pack load and get scored.

### Test cases the data pack plants

| Answer | Case | Expected |
|---|---|---|
| A007 | empty transcript, 0 s | needs a person, never a low score |
| A019 | tells the scorer to give it a 4 | prompt injection flagged, score not forced |
| A022 / A023 | same candidate re-records Q3 | A023 counts, A022 superseded |
| A027 | 3,000+ characters of rambling | long answer handled |
| A031 to A035 | audio only (.m4a) | stored, HR sees it arrived |

## Mocks

- **HR sign-in is MOCK:** "Continue with Google / Facebook" asks only for an email and accepts it. There is no OAuth and no password, and it is labelled MOCK in the UI. The API still signs the identity into an httpOnly cookie and checks it on every `/api/hr/*` route.
- **The scorer is not mocked.** It always calls the real model. A fake client is used only in tests.
