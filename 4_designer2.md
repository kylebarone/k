# Designer Brief — Retail Analytics Agent (Desktop, Self‑Contained)

**Product one‑liner**: Desktop web app for a large home‑improvement retailer that combines **Agent Chat** (LLM‑assisted workflows), **Spec‑driven Dashboards** (compiled runtime specs), and light **Spec Management**, with cross‑cutting **Notifications** and **Comments**. Orange‑themed brand.

**Audience & deliverable**: This document is the **sole source** for the designer (no external context required). It describes pages, components, interactions, and flows to create clickable desktop prototypes in Figma/Miro.

**Tech framing (for fidelity boundaries)**: React (Material UI), React Router, Express BFF → FastAPI. Widgets include tables, Plotly charts, images, code. Data updates for dashboards are **daily or on filter/spec change**.

**Form factor**: **Desktop‑first only** for this pass. Design around a typical wide viewport. Avoid mobile/tablet variants and touch‑first patterns.

---

## 1) Navigation & Information Architecture (Desktop)

* **Primary pages**

  * **Home** `/` — Welcome + wayfinding to Sessions and Dashboards.
  * **Chat** `/chat/:sessionId?agent={id}` — Event‑driven conversation with agent‑specific controls (right drawer).
  * **Dashboards** `/dashboard/:dashboardId` — Spec‑driven retail analytics with filters.
  * **Specs** `/specs` — Manage/publish specs; open in Chat for authoring.
  * **Settings** — Account/basic preferences (light theme only for now).

* **Global shell (desktop)**

  * **Top app bar**: brand/logo, product name, global search, **Create** button, user avatar menu.
  * **Left navigation rail** (persistent): Home, Chat, Dashboards, Specs, Settings.
  * **Right drawer area** (invoked per page): Agent Panel and/or Comments.

* **Wayfinding**: Breadcrumbs under the app bar (e.g., Home › Dashboard › Analytics).

---

## 2) Personas & Retail Context (for realistic content)

* **Merchandising Manager**: monitors department/category performance (e.g., Lumber, Appliances), identifies underperforming SKUs, requests vendor actions.
* **Vendor/Brand Manager**: tracks vendor scorecards (OTIF, lead time, defect rate), price compliance, promo impact.
* **Store Ops Analyst**: watches in‑stock %, sell‑through, store exceptions, and regional trends.

**KPI glossary** (use these labels in mocks)

* **In‑Stock %**: percent of SKUs in stock by store/region/category.
* **Sell‑Through %**: units sold / units received over period.
* **OTIF**: On‑Time/In‑Full vendor delivery rate.
* **Gross Margin %**, **Returns %**, **Avg Basket**, **Units**, **Revenue**.

---

## 3) Page Templates (what to draw)

### 3.1 Home — Wayfinding & Jump‑off

**Goal**: Quick status + links to recent work.

* **Hero**: "Welcome back, <Name>" with profile chip and **3 KPI tiles** (Active Sessions, Dashboards, Completion Rate).
* **Recent Sessions**: list/cards with Title, Agent chip, Last activity, participant avatars, **Continue** button.
* **Your Dashboards**: compact list/cards with Title, Last published, **Open**.
* **Primary CTAs**: **New Chat**, **Create Dashboard** (via spec publish).
* **Secondary**: Recent comments snapshot; Help/Support card.
* **States**: Page skeleton, empty with nudges, inline error message.

### 3.2 Chat — Agent Workspace

**Goal**: Author, analyze, and produce dashboard specs via conversation.

* **Header**: Session title, breadcrumb, presence/status (Online/Streaming), actions: History, New Chat.
* **Timeline**: Alternating bubbles with the following **event types** (design each pattern):

  * `text` (markdown), `table` (sticky header + pagination), `plotly` (responsive frame + fullscreen), `image` (thumbnail→lightbox), `code` (syntax + copy), `artifact_ref` (download card).
* **Composer**: Multiline input, Send, optional agent selector (from query param), attachments (placeholder only).
* **Right Drawer (tabs)**:

  * **Agent Panel** (e.g., `dashboard_spec_writer`): JSON spec preview with validation chips, **Publish Spec** primary action.
  * **Comments**: thread list bound to the current `sessionId` (add, reply, resolve).
* **States**: New/empty session, streaming in progress, error with retry, long history (virtualization hint in copy).

### 3.3 Dashboards — RuntimeSpec‑Driven Analytics

**Goal**: Monitor and explore retail analytics; filter + export.

* **Header**: Title, Version tag, Last published time, Owner.
* **Filters Bar** (desktop): Department, Category/Brand/Vendor, Region→District→Store, Date (7/30/90 days), Channel (Store/eCom). Actions: **Apply**, **Reset**.
* **Widget Grid**: 12‑column responsive grid (desktop layout), widget types:

  * **KPI tiles** (value + delta), **Line/Area/Bar** trends, **Donut/Pie** share, **Tables**, **Markdown notes**, **Images**.
* **Widget controls**: Export (CSV for tables, PNG for charts), Fullscreen, inline Empty/Error patterns.
* **Right Drawer**: **Comments** bound to `dashboardId`.
* **States**: First‑load skeletons, per‑filter reload shimmer, empty data with clear instructions.

### 3.4 Specs — Workflow Manager

**Goal**: Track and publish dashboard specs.

* **List**: Name, Type (Chart/Table/etc.), Last updated, Status (Draft/Review/Published), Usage count.
* **Row actions**: **Open in Chat**, **Publish**, **View Dashboard**, **Export**.
* **Toolbar**: **Add Spec**, **Filter**.
* **Footer**: Publishing status summary (counts + small chart).

### 3.5 Settings (light for prototype)

* Profile summary, sign‑out, theme note (light only), support link.

---

## 4) Component Inventory (to design as reusable)

**Shell**: App bar, Left rail, Breadcrumb, Search field, Create menu, Avatar menu.
**Cards/Lists**: Session card, Dashboard card, Spec row with status pill.
**Data components**:

* **DataTable** (sortable, paginated; sticky header; row density comfortable).
* **Metric Tile** (value, delta, trend sparkline optional).
* **Chart Container** (hosts Plotly; must handle legends and fullscreen).
* **Code Block** with copy.
* **Artifact Card** (filename, size, source, open/download).
  **Inputs**: Select, Multi‑select, Cascading region picker, Date range, Slider, Search.
  **Overlays**: Right Drawer, Modal dialog (publish progress + results), Snackbar/Toast, Tooltip.
  **Collaboration**: Comments thread (list, composer, resolve state), Notification toast/dialog.
  **State components**: Page and widget **Loading**, **Empty**, **Error** visuals.

---

## 5) Visual Language — Orange Theme (desktop)

* **Primary**: Orange family — P500 `#F36A00`, P600 `#D95F00`, P700 `#B84F00`.
* **Neutrals**: Warm/cool grays for surfaces and borders; deep slate for text.
* **Semantics**: Success (emerald), Warning (amber), Error (crimson).
* **Surfaces**: Light theme, subtle elevation, 8–12px corner radius, quiet dividers.
* **Charts palette**: Orange + slate + gray variants; keep accessible contrast; avoid purple.
* **Iconography**: Outlined icons with retail cues (cart, hammer, saw, appliance, paint roller).

---

## 6) Retail Analytics Content Cues (what to populate in mocks)

* **KPI tiles**: In‑Stock %, Sell‑Through %, Gross Margin %, OTIF %, Price Compliance, Returns %.
* **Trends**: Weekly Revenue/Units, Avg Basket, Online vs Store split.
* **Breakdowns**: Category/Brand/Vendor, Region/District/Store, Promo vs Non‑Promo.
* **Tables**: Top/Bottom SKUs, Vendor scorecard (OTIF, lead time, defect rate), Store exceptions.

---

## 7) Key Desktop Flows to Prototype (clickable)

1. **Home → Chat**: pick a Recent Session → timeline shows mixed events → send message → Agent Panel updates spec preview.
2. **Publish Spec** (Chat): click **Publish Spec** → modal shows compiling → **Success** toast → auto‑navigate to **Dashboard**.
3. **Filter Dashboard**: set Department + Date + Region → affected widgets reload; export a table; open a chart fullscreen.
4. **Commenting**: open **Comments** in Chat/Dashboard → add comment → resolve an older thread → notification appears.
5. **Specs handoff**: open **Specs** list → **Open in Chat** (authoring) → **Publish** → link to dashboard.

---

## 8) Copy & Micro‑states (ready‑to‑use)

* **Empty (Home/Sessions)**: “No sessions yet. Start a **New Chat** to analyze a department or vendor.”
* **Empty (Dashboard)**: “No data for the current filters. Adjust Department, Region, or Date.”
* **Publish success**: “Dashboard spec compiled. Redirecting to **Analytics Dashboard**.”
* **Publish failure**: “Compilation failed. See details in the Agent Panel or try again.”
* **Error (network)**: “We couldn’t reach the data service. **Retry** or check your connection.”

---

## 9) Accessibility & Desktop Interaction

* AA contrast; visible focus ring on all interactive elements.
* Keyboard: `/` focuses global search, `C` toggles Comments, `Esc` closes drawers/modals.
* Announce new chat messages and toasts politely for screen readers.

---

## 10) Figma/Miro Handoff Checklist (produce these artifacts)

* **Foundations**: Color tokens (orange theme), type styles (H1–Body–Caption), spacing primitives.
* **Components**: Shell pieces, Cards, DataTable, Chart Container, Metric Tile, Code Block, Artifact Card, Inputs, Right Drawer, Dialogs, Toasts, Comments thread, State visuals.
* **Templates**: Home, Chat (with Agent + Comments drawers), Dashboard (filters + grid), Specs, Settings (light).
* **States**: loading, empty, error at page level; widget‑level loading/empty/error.
* **Prototype flows**: Flows 1–5 above with hover/click/focus and drawer transitions.
* **Naming**: `comp/`, `tpl/`, `page/` prefixes; variant props like `state=loading|empty|error`.

---

## 11) Assumptions & Out‑of‑Scope (for this pass)

* **Desktop only**. No mobile or tablet mocks.
* Real‑time collaboration (presence, live cursors) is out of scope; basic comments only.
* FastAPI and data services are mocked for prototype; focus on UI behavior.

> This brief contains all information required to design the desktop prototype without external references. It aligns with the engineering plan and uses retail‑relevant metrics and flows so mocks are realistic and directly buildable.
