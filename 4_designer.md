# Prototype Brief — Pages, Flows, and Feature Demos

**Product**: Web app (React + React Router + Material UI) with Express BFF (proxy to FastAPI)

**Audience**: Product/design, front‑end, and BFF engineers

**Purpose**: Provide a single source of truth for what we will prototype: pages, user flows, demo scripts, and functional requirements. This is intentionally concrete so design can begin wireframes and interaction models while engineering scaffolds the repo.

---

## 1) Scope & Objectives

**Primary pages (v1)**

* **Home** `/` — profile at-a-glance; lists of recent **Sessions** and **Dashboards** with search/sort.
* **Chat** `/chat/:sessionId?agent=dashboard_spec_writer` — LLM agent chat with **event-driven** rendering (text, tables, images, code, plotly figures) and agent-specific side panels.
* **Dashboard** `/dashboard/:dashboardId` — dynamic dashboard rendered from **RunTimeSpec** (compiled by FastAPI after publish). Supports filters.
* **Workflow Manager (Specs)** `/specs` — browse/create/edit user dashboard specs and publishing entry points (high-level for now).

**Cross-cutting features**

* **Notifications** — global snackbar/modal feed; can surface success/errors; optional realtime via SSE.
* **Comments Sidebar** — context-aware threads tied to `sessionId` or `dashboardId`.
* **Auth** — token-based; assume Firebase Auth (aligns with Firestore), but any IdP works.

**Out of scope for prototype**

* Building the FastAPI service itself (we’ll mock/proxy via Express where needed).
* Heavy real-time collab (presence, live cursors). Basic commenting only.

**Prototype goals**

* Demonstrate **end-to-end**: Home → Chat with agent → publish spec → compiled dashboard → filter, comment, notify.
* Validate information architecture and interaction patterns for growth.

---

## 2) Information Architecture & Navigation

**Global shell**

* **Top App Bar**: logo, product name, user avatar/menu; page title/breadcrumb; global actions (Notifications bell, Comments toggle if applicable).
* **Left Nav (desktop)**: primary sections — Home, Chat (entry/search), Dashboards, Specs.
* **Bottom Nav (mobile)**: Home, Chat, Dashboards, More.

**Hierarchy**

* Level 1: Home, Chat, Dashboards, Specs.
* Level 2: Specific session or dashboard pages.
* Utilities: Notifications (global), Comments (per-context), Search (global quick find).

**Routing patterns**

* `chat/:sessionId?agent={id}`
* `dashboard/:dashboardId`
* `specs` (list), `specs/:specId` (optional detail later)

---

## 3) Page Blueprints (what to design)

### 3.1 Home

**Purpose**: Entry to recent work and wayfinding.

**Primary content**

* **Profile summary** (avatar, name, org, role; edit link)
* **Sessions**: list/table with columns: Title, Agent, Last Activity, Status, Open → `/chat/:sessionId`.
* **Dashboards**: list/cards with: Title, Last Published, Owner, Open → `/dashboard/:dashboardId`.
* **Create actions**: New Chat, New Spec (CTA buttons)

**States**

* Loading (skeleton lists), Empty (zero sessions/dashboards with nudges), Error (retry).

**Key interactions**

* Search/filter within lists; pinned/favorites; quick actions (ellipsis menu).

---

### 3.2 Chat

**Purpose**: Conversational interface with LLM agents; renders events with rich widgets and manages per-session state.

**Layout**

* **Main column**: message composer at bottom; scrollable event timeline above.
* **Right panel (collapsible)**:

  * **Agent panel** (if `agent` present): agent-specific controls and preview (e.g., spec preview for `dashboard_spec_writer`).
  * **Comments** tab: thread tied to `sessionId`.

**Event types (must design visual patterns)**

* `text` — assistant/user bubbles; support markdown.
* `table` — DataTable with sticky header, pagination/virtualization.
* `plotly` — embedded Plotly figure (responsive container, fullscreen toggle).
* `image` — thumbnail to lightbox; caption/alt.
* `code` — syntax-highlighted block; copy button; optional download.
* `artifact_ref` — card with filename/size/source + open/download.

**Composer**

* Multi-line input; submit; attachments (optional); agent selector (when multiple);
* Loading/streaming indicators on send.

**Agent: `dashboard_spec_writer`**

* Side panel shows **JSON spec preview** with validation status.
* **Publish Spec** button (primary). On success → global success notification → **redirect to Dashboard**.

**States**

* New/Empty session; In-progress (streaming); Error (retry/send diagnostics); Large content (progress for uploads);

---

### 3.3 Dashboard

**Purpose**: Read-only (for now) runtime dashboards compiled from user spec.

**Layout**

* **Header**: Title, Last Published/Version, Owner, Share (future).
* **Filters bar**: select/range/search; ‘Reset’ and ‘Apply’.
* **Content grid**: widgets per RunTimeSpec (tables, plotly, images, markdown, statistic tiles).
* **Right panel**: Comments tab for `dashboardId`.

**Behavior**

* Loads **RunTimeSpec** via Express (cached).
* Filters update data queries (no need for intra-day updates unless filters change).
* Empty states per widget; error banner per widget; loading skeletons on first load and per filter change.

**Controls**

* Export (CSV for tables, PNG for charts); widget fullscreen; grid responsive breakpoints.

---

### 3.4 Workflow Manager (Specs)

**Purpose**: Manage specs that drive dashboards; connect to Chat authoring flow.

**Content**

* Spec list (title, updated, status, linked dashboard?).
* Actions: New Spec, Edit in Chat (open session with agent), Publish (calls FastAPI via Express), View Dashboard.

**States**

* Draft vs Published; validation errors; publish progress and result.

---

## 4) Cross‑Cutting Features

### 4.1 Notifications (global)

* Snackbar/toast for minor events; modal for significant actions (e.g., publish result, compilation failures).
* History drawer (optional v2).
* Accessible (role=alert), queueing, auto-dismiss with focus interrupt.

### 4.2 Comments Sidebar

* Open via global button or keyboard shortcut; slides from right.
* Context automatically set by page (session vs dashboard).
* Thread list and composer; mentions (v2); timestamps; resolve/unresolve.
* Empty state encouraging first comment.

### 4.3 Auth (assumed)

* Sign-in modal/page; protected routes redirect; show avatar menu with basic account actions.

---

## 5) End‑to‑End Flows (for clickable prototype)

### Flow A — Wayfinding → Chat

1. From **Home**, user clicks a recent **Session** → lands on **Chat**.
2. Event timeline displays; user sends new message; streaming indicator appears.
3. If agent is `dashboard_spec_writer`, right panel shows evolving spec preview.

**Success criteria**: user can identify session context, read mixed event types, and understand agent affordances.

---

### Flow B — Authoring → Publish → Dashboard

1. In **Chat** with `dashboard_spec_writer`, user reviews JSON preview.
2. User clicks **Publish Spec**.
3. Show modal with brief progress (mock ok); on success, show **Notification** and auto-navigate to `/dashboard/:dashboardId`.
4. **Dashboard** loads: header + filters + widgets from **RunTimeSpec**.
5. User applies a filter; affected widgets show loading then update.

**Success criteria**: publish CTA clear, state transition visible, dashboard renders as spec-driven; filters feel responsive.

---

### Flow C — Comments

1. On **Chat** or **Dashboard**, user opens **Comments** sidebar.
2. Adds a new comment; it appears at top with timestamp.
3. Resolves a comment; thread collapses and shows resolved badge.

**Success criteria**: comments obviously tied to current context; discoverable; non-blocking.

---

### Flow D — Notifications

1. Trigger: publish success/failure, API error, or info banner.
2. Snackbar appears; user can click to view details (modal) or dismiss.

**Success criteria**: users never miss critical outcomes; consistent placement/behavior.

---

## 6) Data & Interaction Contracts (for mock data in prototype)

**Sessions**

* `SessionMeta`: `{ id, title, agent, createdAt, metadata }`
* `SessionEvent`: `{ id, sessionId, ts, role, payload(kind= text|table|plotly|image|code|artifact_ref), stateDelta?, artifactDelta? }`
* **Event rendering rules**: Each `payload.kind` maps to a dedicated component with consistent spacing, headers, and overflow behavior.

**Dashboards**

* `RunTimeSpec`: `{ id, title, version, layout[{zone, widgetId}], dataSources, widgets{ id → {type, source, options} }, filters[] }`
* **Rendering rules**: Grid layout assigns widgets to responsive zones; widget renderer selected by `type`.

**Comments**

* `Comment`: `{ id, resourceType: 'session'|'dashboard', resourceId, authorId, body, createdAt, resolved }`

**Notifications**

* `Notification`: `{ id, kind: info|success|warning|error, title, message?, link? }`

---

## 7) Visual & Interaction Guidelines (for designer)

**Design system base** (Material UI + custom theme)

* **Type scale**: Display, H1–H6, Body, Caption; code font for monospaced blocks.
* **Spacing**: 8px grid; dense tables use 4px within cells.
* **Elevation**: 0/1/2 for content; modals at 24.
* **Radius**: 8–12px on surfaces and inputs.
* **Color**: Neutral background, strong contrast for code/text; semantic colors for notifications.

**Accessibility**

* Color contrast AA; focus states on all interactive elements.
* Keyboard: ESC closes sidebars/modals; `/` focuses global search; `C` toggles comments.
* Announce new chat messages and notifications to screen readers politely.

**Responsive**

* Breakpoints: `sm 600`, `md 900`, `lg 1200`, `xl 1536`.
* Chat timeline flexes vertically; right panel stacks under main on mobile (accordion).
* Dashboard widgets reflow from 12‑col grid → 1‑col.

**Empty/Loading/Error states** (design distinct visuals)

* **Empty**: friendly illustration + primary action.
* **Loading**: skeletons for lists, timeline bubbles, and widgets.
* **Error**: inline retry + diagnostics link.

---

## 8) Prototype Demo Scripts (step‑by‑step)

**Demo 1 — Home → Chat**

1. Load Home with 3 recent sessions, 3 dashboards.
2. Click a session; show chat with mixed events (text, table, plotly, code snippet).
3. Type and send a prompt; show streaming indicator and final text event.

**Demo 2 — Authoring & Publish**

1. In Chat (agent=`dashboard_spec_writer`), show right panel JSON preview with a few validation messages (green checks).
2. Click **Publish Spec**; show modal “Compiling…” → success.
3. Auto‑navigate to Dashboard.

**Demo 3 — Dashboard & Filters**

1. Display header (title + version + last published time).
2. Show filters (date range + category select).
3. Apply filter → widgets reload; one table supports CSV export; a chart supports fullscreen.

**Demo 4 — Comments & Notifications**

1. Open Comments; add a comment; resolve a previous one.
2. Trigger a notification (e.g., “Spec v1.3 published”).

---

## 9) Content Inventory (what copy/design assets we need)

* Empty state copy for Home (Sessions & Dashboards), Chat (new session), Dashboard (no data / no filters set), Specs (no specs).
* Error messages examples (network, auth, compile failure).
* Tooltip/help text for agent panel and filter controls.
* Success copy for publish action + notification variants.

---

## 10) Acceptance Criteria (prototype)

**Home**

* Lists render; search/filter works visually; empty/loading/error screens present.

**Chat**

* Renders at least 5 event kinds with consistent spacing; right panel for agent is discoverable.
* Composer UX validated (multi-line, send, disabled while sending optional).

**Publish**

* Clear primary CTA; success and failure paths both demonstrated.

**Dashboard**

* Spec‑driven layout renders; each widget has loading/empty/error visuals.
* Filters re-query/re-render; export and fullscreen available where relevant.

**Comments**

* Sidebar can be opened/closed from Home/Chat/Dashboard (context follows). CRUD demonstration.

**Notifications**

* Snackbar + modal patterns; timeouts and manual dismiss shown.

---

## 11) Technical Notes for Designer (so mocks map cleanly to build)

* **Tables**: paginate by default; sticky headers; actions in last column; row density ‘comfortable’ with option to compact.
* **Code blocks**: limit height with expand; copy affordance; dark surface.
* **Charts**: container must be responsive; provide min heights; include legend, axis labels; fullscreen toggles.
* **Panels/Drawers**: 360–420px width on desktop; full‑width overlay on mobile.
* **Dialogs**: max‑width `sm`/`md`; primary action right‑aligned; secondary left.
* **Toasts**: bottom‑right on desktop; top on mobile; avoid overlapping critical UI.
* **Keyboard shortcuts**: display in menus/tooltips.

---

## 12) Open Questions / Assumptions

* Auth provider final choice (assumed Firebase); SSO needs?
* Do we need role-based access in v1 (viewer vs editor)? (assume “yes” for copy tone; enforce later).
* Comments: do we support mentions/attachments in v1? (assume text‑only).
* Global search scope (sessions + dashboards only in v1?).
* Theming: light only for v1? (assume light).

---

## 13) Appendix — Example Data Snippets (for prototype mocks)

**Chat events**

* Text: “Here’s a summary of your last run…”
* Table: columns `["Metric","Value"]`, rows like `[["MAE", 0.12], ["R^2", 0.86]]`
* Plotly: line chart (time vs metric)
* Code: Python snippet (20–30 lines)
* Image: 16:9 thumbnail

**RunTimeSpec (conceptual)**

```
{
  "id": "dash_123",
  "title": "Sales Overview",
  "version": "1.3.0",
  "filters": [
    {"id":"date","type":"range"},
    {"id":"region","type":"select"}
  ],
  "layout": [
    {"zone":"hero","widgetId":"kpi_1"},
    {"zone":"left","widgetId":"tbl_sales"},
    {"zone":"right","widgetId":"plt_trend"}
  ],
  "dataSources": {
    "sales_api": {"type":"api","ref":"/api/sales?{filters}"}
  },
  "widgets": {
    "kpi_1": {"type":"stat","source":"sales_api","options":{"field":"total"}},
    "tbl_sales": {"type":"table","source":"sales_api"},
    "plt_trend": {"type":"plotly","source":"sales_api"}
  }
}
```

---

## 14) Next Steps

* Designer: create low‑fidelity wireframes for the four pages + major states; then one high‑fidelity flow end‑to‑end (A or B).
* Engineering: scaffold repo (routes/providers), stub data and mocks; wire navigation and panels; implement notification & comments shells.
* Review: align on component inventory and spacing, then move to interactive prototype.
