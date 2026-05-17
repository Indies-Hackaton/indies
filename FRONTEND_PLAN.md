# Indies — Frontend Plan

## Visual direction: Bold Journalistic

**Fonts:** `Barlow Condensed` (headings, labels, badges) · `Libre Baskerville` (body, questions) · `IBM Plex Mono` (data, code, params)
**Colors:** Pure white · Black borders (`2px solid #000`) · Red accent `#dc2626` · Pure black text
**Approach:** CSS Modules — no Tailwind, bespoke aesthetic

---

## Core principle: "Show the receipts"

Indies is a transparency tool, not just a chatbot. Every assistant response exposes the full chain so users can verify it themselves:

- What the agent planned to do
- What API calls were made (with exact parameters)
- What raw data came back
- How the data was synthesized into the answer

---

## Current state — what is built

### Interaction model
Traditional chat: message thread oldest→newest, input pinned at bottom, conversation list in a collapsible sidebar.

### File structure

```
frontend/
  app/
    page.tsx                  ← root layout: sidebar + chat
    page.module.css
    layout.tsx                ← metadata + fonts
    globals.css               ← design tokens, base reset
  components/
    ChatArea.tsx              ← message thread + title bar + input
    ChatArea.module.css
    ChatInput.tsx             ← bottom chat input
    ChatInput.module.css
    MessageBubble.tsx         ← user + assistant bubbles, [N] marker parser
    MessageBubble.module.css
    SourcesSection.tsx        ← collapsible FUENTES + per-source accordions
    SourcesSection.module.css
    DataRenderer.tsx          ← smart table renderer with JSON fallback
    DataRenderer.module.css
    Sidebar.tsx               ← conversation list, time groups, ⋯ menu, inline rename
    Sidebar.module.css
    ExampleChips.tsx          ← suggestion chips shown on empty state
    ExampleChips.module.css
    ConfirmDeleteModal.tsx    ← shared delete confirmation dialog
    ConfirmDeleteModal.module.css
    SearchBar.tsx             ← kept from original starter (unused in main UI)
    SearchBar.module.css
  hooks/
    useConversation.ts        ← active conversation state, send/load/rename/reset
    useConversations.ts       ← sidebar conversation list with refresh
  lib/
    api.ts                    ← typed fetch wrapper for all backend calls
    types.ts                  ← all shared TypeScript types
```

### Key components

**`MessageBubble`**
- User bubble (right-aligned, black background)
- Assistant bubble (left-aligned, black border) with `react-markdown` when `content_format === "markdown"`
- `[N]` citation markers rendered as clickable superscript buttons
- `SourcesSection` below each assistant bubble

**`SourcesSection`**
- Collapsible header showing source count + total records (expanded by default)
- Each tool run is a collapsible row: `[N] tool_name · X registros`
- Expanded row shows exact API call parameters + `DataRenderer` table
- `activeIndex` prop: forces the section open and auto-expands + highlights the target row when a `[N]` marker is clicked

**`Sidebar`**
- Conversations grouped by: Hoy / Ayer / Últimos 7 días / Últimos 30 días / Anterior
- Desktop: collapses to a 44px icon strip via toggle (panel icon)
- Mobile: full-width overlay triggered by hamburger in the main header
- Per-item `⋯` hover menu → Renombrar (inline edit) / Eliminar (confirmation modal)

**`ChatArea`**
- Title bar with inline rename (pencil icon) and delete (trash icon)
- Auto-scrolls to bottom on new message

---

## Pending — waiting on backend

### Rename + delete endpoints

Frontend fully built. Backend has not shipped these yet.

| What | Backend needed |
|---|---|
| Rename | `PATCH /api/v1/chat/conversations/{id}` — body: `{ "title": "..." }` |
| Soft delete | `DELETE /api/v1/chat/conversations/{id}` — sets `deleted_at = utc_now()` |
| DB migration | `deleted_at TEXT DEFAULT NULL` column on `conversations` table |
| Query filter | All `chat_service.py` queries must add `.where(ConversationRecord.deleted_at.is_(None))` |

### Citation markers `[N]`

Frontend fully wired. Backend needs to update `_CHAT_RESPONSE_PROMPT` to instruct the model to embed `[N]` markers in synthesis text, where `N` is the 1-based index of the `tool_run` in the results array.

---

## Pending — frontend work

### Export

CSV/JSON export button on each source row in `SourcesSection`. Self-contained — no backend needed. The full `records` array is already in state.

### Streaming responses

Needs analysis and a new backend SSE endpoint. When the backend streams tokens, the assistant bubble should show text appearing word-by-word instead of appearing all at once. Deferred until backend is ready.

### Markdown in synthesis prompt

Confirm with backend that `_CHAT_RESPONSE_PROMPT` explicitly requests markdown output so `content_format: "markdown"` is consistently returned and the UI always renders properly formatted responses.

---

## Phase roadmap

### Phase 1 — Core UI ✅ Done
Chat interface, evidence trail, sidebar, markdown rendering, citation marker wiring.

### Phase 2 — Persistence + Export
- History: **done by backend** — conversation DB replaces the original localStorage plan.
- Rename/delete: frontend done, **waiting on backend endpoints**.
- Export: **pending** — frontend only, no backend needed.

### Phase 3 — Auth + Cloud History
- NextAuth or similar — Next.js middleware protects routes.
- `useConversation` API calls get `Authorization` header (one-line change in `lib/api.ts`).
- Backend needs user model + auth middleware + user-scoped conversation queries.
- No frontend component changes required if the hook interface stays the same.
