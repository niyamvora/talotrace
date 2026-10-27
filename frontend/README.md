# TaloTrace web

Next.js (App Router) + shadcn/ui in a pnpm/Turborepo workspace. It only displays what the API returns
and redirects to sign-in on a `401`; every rule and permission lives in the FastAPI backend.
`/api/*` is rewritten to FastAPI (`API_URL`, default `http://localhost:8000`), so the browser sees one origin.
The API contract is [`docs/API.md`](../docs/API.md).

```bash
pnpm install
pnpm dev        # http://localhost:3000 (the API must be running on :8000)
pnpm typecheck && pnpm lint && pnpm build
```

## Pages

| Route | Who | What |
|---|---|---|
| `/i/[token]` | candidate | the personal link printed by `uv run python -m app.seed`. One question at a time, typed or uploaded audio, a receipt per answer, and a reload resumes on the same question |
| `/hr/login` | HR | **MOCK** "Continue with Google / Facebook": asks only for an email, no password, no real OAuth |
| `/hr` | HR | roles with status counts per answer |
| `/hr/roles/[role]` | HR | candidates; open a row for every answer with its status, suggested score, reason, evidence quote, audio, override and retry. Refreshes every 5 s while answers are being scored |

Light, dark and system themes come from the toggle in the header (or press `d`).

## Layout

- `apps/web/src/app`: the pages above. `lib/api.ts` holds the typed API client and every response type.
- `packages/ui/src/components`: shadcn/ui components, shared as `@workspace/ui/components/*`.

## Adding a shadcn component

Always through the CLI, never by hand. From `apps/web`:

```bash
npx shadcn@latest add <component>
```

Files land in `packages/ui/src/components`. To check that an installed component still matches the
registry: `npx shadcn@latest add <component> --dry-run --diff` (prints "No changes.").
