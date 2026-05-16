# Agent Instructions — Indies

**Read this before doing anything else.**

This is a collaborative hackathon project. Multiple agents and developers are working on different parts simultaneously. Keeping documentation in sync is critical — the frontend team depends on it to make correct integration decisions.

## You MUST do this when you make changes

After completing any meaningful work (new endpoint, changed request/response shape, new service, new env variable, renamed field, anything that affects how the frontend talks to the backend), you are required to update **`OVERVIEW.md`** to reflect the current state of the system.

Do not skip this. Do not leave it for later. Update it as the last step of your work, before you consider the task done.

### What to update in OVERVIEW.md

- **New or changed endpoints** — method, path, request body, response shape, error codes
- **New environment variables** — name, required/optional, default value, what it controls
- **New services or external APIs** — what they do, how they're authenticated
- **Changed data shapes** — if a field is added, removed, renamed, or retyped
- **New intent tools** — if the MiniMax intent router gains a new `tool` value, document it

### How to update it

Find the relevant section in `OVERVIEW.md` and edit it in place. Keep it accurate and current, not a historical log — if something changed, rewrite the old description, don't append a note below it.

If you added something entirely new that has no existing section, add one.

## Project docs

| File | Purpose |
|---|---|
| `OVERVIEW.md` | Living reference for the whole system — **keep this current** |
| `FRONTEND_PLAN.md` | Frontend implementation plan and phase roadmap |
| `backend/.env.example` | Canonical list of backend environment variables |

## Quick architecture reminder

```
Next.js frontend  →  POST /api/v1/audit/query  →  FastAPI backend
                                                      ├── MiniMax LLM (intent classification)
                                                      └── Mercado Público API (procurement data)
```

The frontend renders a "receipt" for every query showing the full chain: question → intent → API call → results. Any change to what the backend returns is immediately visible to the user — so breaking changes to the response shape will break the UI.
