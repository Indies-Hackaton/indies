# Indies — Frontend Implementation Plan

## Visual Direction: Bold Journalistic

**Fonts:** `Barlow Condensed` (headings, labels, badges) · `Libre Baskerville` (body, questions) · `IBM Plex Mono` (data, code, params)
**Colors:** Pure white panels · Black borders · Red accent `#dc2626` · Pure black text
**Approach:** CSS Modules (no Tailwind) — bespoke aesthetic, no utility-class fighting

---

## Core principle: "Show the receipts"

Every query produces a numbered receipt card that exposes the full chain so users can verify it themselves:

1. **Pregunta original** — verbatim user input
2. **Interpretación del modelo** — intent badge, extracted params, LLM reasoning
3. **Consulta enviada** — the literal API call made (endpoint + params)
4. **Resultados** — smart renderer: table if shape is recognizable, formatted JSON fallback

---

## Phase 1 — Core UI *(build now)*

### What gets built
- Header with logo + branding
- Sticky search bar (black border, red submit `→`)
- Example query chips shown when feed is empty
- Results feed — numbered receipt cards with the 4-section chain above
- Loading skeleton on each card while request is in-flight
- Error and `unknown` intent states with actionable guidance
- `lib/api.ts` — typed fetch wrapper matching backend Pydantic models
- `lib/types.ts` — shared TypeScript types

### Architectural decisions made in Phase 1 that unlock Phases 2 & 3

| Decision | Phase 1 | Swapped in Phase 2/3 |
|---|---|---|
| `QueryEntry` type includes `id`, `timestamp`, `question`, `intent`, `rawData`, `status` | defined once, used everywhere | no change needed |
| `useQueryHistory` hook exposes `{ entries, add, clear }` | backed by React `useState` (in-memory) | swap internals to localStorage, then to API |
| `lib/api.ts` wraps all fetch calls | no auth headers | add `Authorization` header in one place |
| Page structure uses Next.js App Router layout | anonymous, single route `/` | middleware slot + `/login`, `/history` routes already fit |

### File structure

```
frontend/
  app/
    page.tsx              ← main page (replaces starter)
    layout.tsx            ← updated metadata + fonts
    globals.css           ← updated design tokens
  components/
    SearchBar.tsx
    SearchBar.module.css
    ReceiptCard.tsx
    ReceiptCard.module.css
    DataRenderer.tsx      ← smart table / JSON fallback
    ExampleChips.tsx
    ExampleChips.module.css
  hooks/
    useQueryHistory.ts    ← abstracted storage hook
  lib/
    api.ts                ← typed fetch wrapper
    types.ts              ← QueryEntry, Intent, etc.
```

### Implementation steps

- [ ] Step 1 — `lib/types.ts`: define `QueryEntry`, `Intent`, `IntentParameters`, `QueryResponse`
- [ ] Step 2 — `lib/api.ts`: typed fetch wrapper for `POST /api/v1/audit/query`
- [ ] Step 3 — `hooks/useQueryHistory.ts`: in-memory history hook (`entries`, `add`, `clear`)
- [ ] Step 4 — `app/globals.css` + `app/layout.tsx`: design tokens, fonts, base reset
- [ ] Step 5 — `components/SearchBar`: sticky search input + submit button
- [ ] Step 6 — `components/ExampleChips`: clickable suggestion chips (shown when feed is empty)
- [ ] Step 7 — `components/DataRenderer`: smart table renderer with JSON fallback
- [ ] Step 8 — `components/ReceiptCard`: full 4-section receipt card with loading + error states
- [ ] Step 9 — `app/page.tsx`: wire everything together into the hybrid layout

---

## Phase 2 — Persistence + Export *(next sprint)*

### What changes
- `useQueryHistory` internals swapped from `useState` → `localStorage`
- Zero changes to UI components (hook interface stays identical)
- "Exportar" button on each receipt card: CSV (table data) + raw JSON (full `data` object)
- "Limpiar historial" action in header
- History survives page refresh and browser close

### Why it's easy
Phase 1 already stores the full `rawData` object and timestamps every entry. Export is pure serialization, no new data fetching needed.

---

## Phase 3 — Auth + Cloud History *(later)*

### What changes
- NextAuth (or similar) added — Next.js middleware protects routes
- `useQueryHistory` internals swapped from `localStorage` → authenticated API calls
- Still zero changes to UI components
- Each `QueryEntry` gets a `userId` on the backend side

### What the backend team needs to build
- `POST /api/v1/history` — save a query entry (auth-gated)
- `GET /api/v1/history` — retrieve user's history (auth-gated)
- User model + session management

---

## Backend API reference (for frontend)

### `POST /api/v1/audit/query`

**Request**
```json
{ "message": "string" }
```

**Response**
```json
{
  "intent": {
    "tool": "orders_by_org_and_date | orders_by_date | unknown",
    "parameters": {
      "codigoorg": "string | null",
      "fecha": "string | null"
    },
    "reasoning": "string | null"
  },
  "data": { },
  "detail": "string | null"
}
```

**Error cases**
- `502` — MiniMax or Mercado Público unreachable
- `422` — required params missing (org or date not extractable)

### Other endpoints
- `GET /health` — liveness probe
- `GET /api/hello` — legacy connectivity check

### Environment
- `NEXT_PUBLIC_API_URL` — backend base URL (default: `http://localhost:8000`)
