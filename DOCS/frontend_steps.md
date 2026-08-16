# FRONTEND_STEPS.md

## Overview

This document is the step-by-step implementation roadmap for the AI Database Administrator **frontend** (`apps/frontend/`), derived directly from `PRD.md`, `TECHSTACK.md`, and `ARCHITECTURE.md`. It covers only frontend work — no backend (`apps/backend/`) implementation is included. Each step lists its goal, exact files/folders, implementation detail, backend/API dependency, verification, and expected result.

Frontend framework/technology is confirmed by `ARCHITECTURE.md`/`TECHSTACK.md` as **Next.js (React)** with **React Flow** for graphs, **TanStack Query** for server state, **Zustand** for the auth store, and typed API access via a generated OpenAPI client. Exact styling library is marked `TBD` per `PRD.md` §11 ("frontend framework/technology is not specified... TBD" — resolved here as Next.js per `ARCHITECTURE.md`/`TECHSTACK.md`, but CSS approach itself is `TBD`).

---

### Step 1 — Frontend Project Scaffolding

**Goal**
Create the base Next.js App Router project structure exactly as defined in `ARCHITECTURE.md` §5.

**Files/Folders**
```
apps/frontend/
├── app/
├── components/
│   ├── ui/
│   └── charts/
├── features/
│   ├── diagnosis/
│   ├── simulation/
│   ├── forecasting/
│   └── roi/
├── hooks/
├── lib/
├── services/
├── stores/
├── types/
├── public/
├── tests/
└── package.json
```

**Implementation**
Initialize a Next.js (App Router) project inside `apps/frontend/`. Create all folders listed above as empty directories with placeholder `.gitkeep` or index files where needed. Do not add page content yet — that begins in Step 6.

**Backend/API Dependency**
None.

**Verification**
`apps/frontend` directory tree matches `ARCHITECTURE.md` §5 exactly; `npm run dev` starts a blank Next.js app without error.

**Expected Result**
An empty, correctly structured Next.js project ready for dependency installation.

---

### Step 2 — Dependencies

**Goal**
Install all frontend dependencies referenced in `ARCHITECTURE.md` §5 and `TECHSTACK.md`.

**Files/Folders**
- `apps/frontend/package.json`

**Implementation**
Add: `next`, `react`, `react-dom`, `@tanstack/react-query`, `zustand`, `reactflow` (React Flow, for the evidence-graph timeline view per `ARCHITECTURE.md` §5), a charting library for the calibration/MAE charts (`TBD` — e.g. `recharts`; not fixed by source docs), `zod` or equivalent for runtime schema validation of API responses (`TBD`), `openapi-typescript` (dev dependency, to generate `types/` from the backend OpenAPI schema per `ARCHITECTURE.md` §5), `eventsource`/native `EventSource` polyfill if needed for SSE (`lib/sse-client.ts`), and a CSS approach (`TBD` — Tailwind CSS is a common default but not confirmed in source docs; mark styling library choice `TBD` until decided in Step 5).

**Backend/API Dependency**
None (backend OpenAPI schema needed later in Step 8, not here).

**Verification**
`npm install` completes cleanly; `npm run build` compiles the empty scaffold.

**Expected Result**
All frontend dependencies installed and importable.

---

### Step 3 — Environment Configuration

**Goal**
Configure frontend environment variables per `ARCHITECTURE.md` §11.

**Files/Folders**
- `apps/frontend/.env.local` (gitignored)
- `.env.example` (root, confirm frontend vars documented)

**Implementation**
Define `NEXT_PUBLIC_API_BASE_URL` (base URL the frontend calls for REST/SSE) and `NODE_ENV`/`ENVIRONMENT` (dev/prod switch for logging/config), per `ARCHITECTURE.md` §11 table. Do not commit real values — `.env.example` documents names/purposes only.

**Backend/API Dependency**
Backend must be running and reachable at the configured base URL for later verification steps (not required yet).

**Verification**
`process.env.NEXT_PUBLIC_API_BASE_URL` accessible in a test page/component during `npm run dev`.

**Expected Result**
Frontend has a working, environment-driven configuration point for all backend calls.

---

### Step 4 — API Client Foundation

**Goal**
Build the single typed fetch wrapper all backend calls will go through, per `ARCHITECTURE.md` §5 (`lib/api-client.ts`).

**Files/Folders**
- `apps/frontend/lib/api-client.ts`
- `apps/frontend/lib/sse-client.ts`

**Implementation**
`api-client.ts`: a typed `fetch` wrapper handling base URL (`NEXT_PUBLIC_API_BASE_URL`), credentials (httpOnly JWT cookie — `credentials: "include"`), JSON parsing, and normalized error objects (mapping backend error responses to a consistent frontend error shape). Every `services/` module (Step 9) will call through this.
`sse-client.ts`: a thin wrapper around `EventSource` for the two backend SSE endpoints (`GET /api/v1/experiments/{id}/canary/stream`, `GET /api/v1/forecasts/{id}/stream`), exposing a `subscribe(url, onMessage, onError)` helper.

**Backend/API Dependency**
None yet functionally required (backend routes tested in later steps), but this is the layer every backend call passes through going forward.

**Verification**
Unit test: mock `fetch`, confirm `api-client.ts` correctly attaches base URL/credentials and normalizes a mock error response; mock `EventSource`, confirm `sse-client.ts` invokes callbacks correctly.

**Expected Result**
A reusable, tested transport layer ready for typed service modules.

---

### Step 5 — Generated API Types

**Goal**
Generate TypeScript types from the backend's OpenAPI schema, per `ARCHITECTURE.md` §5 (`types/`).

**Files/Folders**
- `apps/frontend/types/api.ts` (generated output)
- `apps/frontend/package.json` (add a `generate:types` script)

**Implementation**
Add an `openapi-typescript` script pointing at the backend's `/openapi.json` (available once `BACKEND_STEPS.md` Step 10 is complete), outputting typed request/response interfaces to `types/api.ts`. This keeps frontend/backend contracts in sync without a shared package (per `ARCHITECTURE.md` §2).

**Backend/API Dependency**
Requires the backend FastAPI app running with all routes registered (`BACKEND_STEPS.md` Step 10 — Core API Skeleton) so `/openapi.json` reflects the full route surface, even if route bodies are still stubs.

**Verification**
Run `npm run generate:types`; confirm `types/api.ts` contains interfaces for every route/schema defined in the backend (connections, diagnoses, experiments, forecasts, roi, auth).

**Expected Result**
Frontend has compile-time-safe types matching the backend contract, regenerable any time the backend schema changes.

---

### Step 6 — Global Layout & Design System Foundation

**Goal**
Establish the app shell and base styling system, per `ARCHITECTURE.md` §5.

**Files/Folders**
- `apps/frontend/app/layout.tsx`
- `apps/frontend/app/globals.css` (or equivalent, depending on chosen styling approach — `TBD`)
- `apps/frontend/components/ui/` (base primitives: `Button.tsx`, `Card.tsx`, `Table.tsx`, `Badge.tsx`, `Modal.tsx`, `Tabs.tsx`)

**Implementation**
`layout.tsx`: root HTML shell, global providers wiring point (TanStack Query provider added in Step 8, auth store provider in Step 9), global navigation shell (top nav / sidebar linking to Dashboard, Connections, Diagnostics, Experiments, Forecasts, ROI — per `PRD.md` §11 page list).
`components/ui/`: feature-agnostic presentational primitives reused across all pages — **reusable across the entire app**.
Styling approach: `TBD` (Tailwind CSS or CSS Modules — not specified in source docs); pick one and apply consistently from this step forward.

**Backend/API Dependency**
None.

**Verification**
`npm run dev` renders the root layout with working navigation links (routes not yet implemented, so links may 404 until Step 7).

**Expected Result**
A consistent visual shell and a base component library ready for page-level composition.

---

### Step 7 — Routing Skeleton (App Router Pages)

**Goal**
Create all route segments per `ARCHITECTURE.md` §5, matching the page list in `PRD.md` §11.

**Files/Folders**
```
apps/frontend/app/
├── (auth)/
│   ├── login/page.tsx
│   └── signup/page.tsx
├── dashboard/page.tsx
├── connections/page.tsx
├── diagnostics/[connectionId]/page.tsx
├── experiments/[experimentId]/page.tsx
├── forecasts/[connectionId]/page.tsx
└── roi/page.tsx
```

**Implementation**
Each `page.tsx` is a stub component rendering a placeholder heading only — real content is added feature-by-feature in later steps (Steps 12–18). This step exists purely to establish routable URLs matching every planned page.

**Backend/API Dependency**
None yet.

**Verification**
Navigate to each route in the browser; confirm each renders its placeholder without error.

**Expected Result**
Every planned page in `PRD.md` §11 is routable, even though content is not yet implemented.

---

### Step 8 — TanStack Query Setup (Server State)

**Goal**
Wire up server-state management, per `ARCHITECTURE.md` §5.

**Files/Folders**
- `apps/frontend/app/layout.tsx` (add QueryClientProvider)
- `apps/frontend/lib/query-client.ts`

**Implementation**
Create a singleton `QueryClient` (default stale-time/retry config) in `query-client.ts`; wrap the app in `QueryClientProvider` inside `layout.tsx`. This is the mechanism that will own caching, refetching, and loading/error states for every API call across the app (per `ARCHITECTURE.md` §5 — "Server state... is managed by TanStack Query, not a global store").

**Backend/API Dependency**
None directly; this is the plumbing that later `hooks/` (Step 10) will use to call backend endpoints.

**Verification**
Render a test component using `useQuery` against a mock resolver; confirm caching/loading states behave as expected in React DevTools.

**Expected Result**
App-wide server-state management is in place and ready for real API-backed hooks.

---

### Step 9 — Authentication UI & Auth Store

**Goal**
Implement login/signup and the Zustand auth store, per `ARCHITECTURE.md` §5.

**Files/Folders**
- `apps/frontend/app/(auth)/login/page.tsx`
- `apps/frontend/app/(auth)/signup/page.tsx`
- `apps/frontend/stores/auth-store.ts`
- `apps/frontend/services/authService.ts`
- `apps/frontend/hooks/useAuth.ts`
- `apps/frontend/middleware.ts` (Next.js middleware for route protection)

**Implementation**
`authService.ts`: typed functions calling `POST /api/v1/auth/login`, `POST /api/v1/auth/signup`, `GET /api/v1/auth/me` via `lib/api-client.ts`.
`auth-store.ts`: Zustand store holding only the non-sensitive user profile (id, email, role) fetched from `/auth/me` on app load — **not** the JWT itself (stored as httpOnly cookie by the backend).
`useAuth.ts`: cross-feature hook (per `ARCHITECTURE.md` §5 `hooks/`) wrapping `authService` + `auth-store` with TanStack Query (`useQuery` for `/auth/me`, `useMutation` for login/signup) — **reusable across the app**.
`login/page.tsx` / `signup/page.tsx`: forms calling `useAuth`'s login/signup mutations, redirecting to `/dashboard` on success.
`middleware.ts`: Next.js middleware checking session validity (lightweight server-side call), redirecting unauthenticated users to `/login` for all protected routes (per `ARCHITECTURE.md` §5).

**Backend/API Dependency**
`POST /api/v1/auth/login`, `POST /api/v1/auth/signup`, `GET /api/v1/auth/me` (`BACKEND_STEPS.md` Steps 8, 10).

**Verification**
Signup a test user → login → confirm httpOnly cookie set → confirm `/auth/me` returns the profile → confirm accessing `/dashboard` without login redirects to `/login`.

**Expected Result**
Full authentication flow working end-to-end against the real backend.

---

### Step 10 — Feature Service Modules & Data Hooks

**Goal**
Build one typed API-wrapper module per feature area, per `ARCHITECTURE.md` §5, and the TanStack Query hooks that consume them.

**Files/Folders**
- `apps/frontend/services/diagnosisService.ts`
- `apps/frontend/services/simulationService.ts`
- `apps/frontend/services/forecastService.ts`
- `apps/frontend/services/roiService.ts`
- `apps/frontend/services/connectionService.ts` (new — supports Step 13)
- `apps/frontend/hooks/usePolling.ts`
- `apps/frontend/hooks/useSSE.ts`
- `apps/frontend/features/diagnosis/hooks/useDiagnoses.ts`
- `apps/frontend/features/simulation/hooks/useExperiments.ts`
- `apps/frontend/features/forecasting/hooks/useForecasts.ts`
- `apps/frontend/features/roi/hooks/useRoi.ts`

**Implementation**
Each `services/*Service.ts` exposes typed functions (using `types/api.ts` from Step 5) calling the corresponding backend routes via `lib/api-client.ts`:
- `connectionService.ts`: `POST /connections`, `POST /connections/{id}/test`, `GET /connections/{id}/telemetry`.
- `diagnosisService.ts`: `GET /connections/{id}/diagnoses`, `GET /diagnoses/{id}`, `GET /diagnoses/{id}/recommendations`.
- `simulationService.ts`: `POST /recommendations/{id}/simulate`, `GET /recommendations/{id}/verification`, `POST /recommendations/{id}/approve`, `POST /recommendations/{id}/reject`, `GET /deployments/{id}`, `GET /experiments`.
- `forecastService.ts`: `GET /forecast/{connectionId}`, `GET /models/performance`.
- `roiService.ts`: reads ROI data (exact endpoint per `PRD.md` §12 — attached to experiment records; `TBD` precise route if not explicitly listed).
Each `features/<feature>/hooks/use*.ts` wraps the corresponding service call in `useQuery`/`useMutation`, exposing loading/error/data state to page components.
`usePolling.ts`: generic hook for TanStack Query polling/refetch-on-focus (used by dashboard-style, non-SSE views).
`useSSE.ts`: generic hook wrapping `lib/sse-client.ts` for components needing live updates.

**Backend/API Dependency**
All routes listed above — requires `BACKEND_STEPS.md` Steps 12 (connections), 19 (diagnosis), 23–24 (simulation/approval), 27 (forecast), 28 (roi) to be functionally implemented (stubs acceptable for initial wiring/testing, full function needed for Step 25 integration testing).

**Verification**
Unit test each service function against a mocked `api-client`; confirm each hook exposes correct `data`/`isLoading`/`error` states with a mocked `QueryClient`.

**Expected Result**
A complete, typed data-access layer connecting every page to its corresponding backend feature — **the core state/data-flow spine of the app**.

---

### Step 11 — Shared Reusable Components

**Goal**
Build the cross-feature UI components used across multiple pages, per `ARCHITECTURE.md` §5.

**Files/Folders**
- `apps/frontend/components/ui/DataTable.tsx`
- `apps/frontend/components/ui/StatusBadge.tsx` (e.g., VERIFIED/CONDITIONAL/REJECTED, COMMIT/ROLLBACK states)
- `apps/frontend/components/ui/ConfidenceMeter.tsx` (confidence % display, reused in diagnosis + forecast + recommendations)
- `apps/frontend/components/ui/EmptyState.tsx`
- `apps/frontend/components/ui/LoadingSkeleton.tsx`
- `apps/frontend/components/ui/ErrorBanner.tsx`
- `apps/frontend/components/ui/Toast.tsx` (notifications, Step 21)

**Implementation**
Each component is presentational-only, accepting typed props, with no direct API calls — **all reusable** across Dashboard, Diagnostics, Experiments, Forecasts, and ROI pages. `StatusBadge` and `ConfidenceMeter` encode the domain vocabulary from `PRD.md` (VERIFIED/CONDITIONAL/REJECTED; COMMIT/ROLLBACK; PRIMARY/CONTRIBUTING/CORRELATED/UNRELATED; confidence percentages).

**Backend/API Dependency**
None (pure presentational components).

**Verification**
Render each component in isolation (Storybook or a throwaway test page) with representative prop values; confirm visual correctness for each state variant.

**Expected Result**
A shared component library ready for composition into feature pages.

---

### Step 12 — Dashboard Page

**Goal**
Implement the overview dashboard, per `PRD.md` §11 ("Dashboard (overview of connected databases, active problems)").

**Files/Folders**
- `apps/frontend/app/dashboard/page.tsx`
- `apps/frontend/features/diagnosis/components/ActiveProblemsList.tsx`
- `apps/frontend/features/diagnosis/components/ConnectionsSummaryCard.tsx`

**Implementation**
`dashboard/page.tsx`: composes `ConnectionsSummaryCard` (list of connected databases + status, via `connectionService`) and `ActiveProblemsList` (recent/active diagnoses across all connections, via `diagnosisService`/`useDiagnoses`). Uses TanStack Query polling (`usePolling`, per `ARCHITECTURE.md` §5 — "everything else uses plain REST + TanStack Query polling").

**Backend/API Dependency**
`GET /connections/{id}/telemetry`, `GET /connections/{id}/diagnoses` (aggregated across connections — confirm backend supports a list-all-connections variant; if not present, mark aggregation endpoint `TBD` and fetch per-connection client-side as an interim approach).

**Verification**
With at least one test connection and one diagnosis seeded in the backend, confirm the dashboard displays the connection and the diagnosis summary; confirm polling refreshes data without a manual reload.

**Expected Result**
A working overview dashboard reflecting real backend state.

---

### Step 13 — Database Connection UI

**Goal**
Implement the "Connect Database" flow, per `TECHSTACK.md` User Connection Workflow and `PRD.md` §4/§11.

**Files/Folders**
- `apps/frontend/app/connections/page.tsx`
- `apps/frontend/app/connections/components/ConnectionForm.tsx`
- `apps/frontend/app/connections/components/ConnectionTestResult.tsx`
- `apps/frontend/app/connections/components/ConnectionList.tsx`

**Implementation**
`ConnectionForm.tsx`: form for host/port/db/user/password/SSL (or a full connection string), submits via `connectionService.create_connection` (`POST /connections`).
`ConnectionTestResult.tsx`: displays the result of `POST /connections/{id}/test` — reachability, credential validity, required extension (`pg_stat_statements`) and permission checks, per `PRD.md` §4 Core User Journey.
`ConnectionList.tsx`: lists all connections with status badges (`StatusBadge` from Step 11).
`connections/page.tsx`: composes the above; triggers test automatically after creation.

Note: Connections isn't one of the four `features/*` folders defined in `ARCHITECTURE.md` §5, so its components are placed directly under `app/connections/components/` rather than a `features/connections/` folder (`TBD` — revisit if a `features/connections/` folder is preferred for consistency).

**Backend/API Dependency**
`POST /connections`, `POST /connections/{id}/test`, `GET /connections/{id}/telemetry` (`BACKEND_STEPS.md` Step 12).

**Verification**
Add a real test Postgres connection string through the form; confirm the test-connection result correctly reports success/failure and missing-extension errors as returned by the backend.

**Expected Result**
Users can connect and validate a monitored database end-to-end through the UI.

---

### Step 14 — Monitoring UI (Live Telemetry)

**Goal**
Implement the live telemetry view, per `PRD.md` §11 ("Monitoring UI (live telemetry, anomaly indicators)").

**Files/Folders**
- `apps/frontend/app/connections/[connectionId]/monitoring/page.tsx` (new nested route — add to routing skeleton from Step 7)
- `apps/frontend/features/diagnosis/components/TelemetryOverview.tsx`
- `apps/frontend/features/diagnosis/components/AnomalyIndicator.tsx`

**Implementation**
`TelemetryOverview.tsx`: displays recent query/table/plan metrics summaries for a connection, fetched via `connectionService.list_telemetry_summary` (`GET /connections/{id}/telemetry`), refreshed via `usePolling`.
`AnomalyIndicator.tsx`: visual flag when anomaly detection (backend Feature 1 ML layer) has flagged the connection — sourced from the diagnosis list's anomaly-triggered entries.

**Backend/API Dependency**
`GET /connections/{id}/telemetry` (`BACKEND_STEPS.md` Step 12), telemetry populated by the backend's `telemetry_collector` worker (`BACKEND_STEPS.md` Step 14).

**Verification**
With the backend telemetry collector running against a seeded test DB, confirm the monitoring page reflects live-updating metrics on each poll interval.

**Expected Result**
A working live-monitoring view per connection.

---

### Step 15 — Diagnostics UI (Feature 1)

**Goal**
Implement the root-cause diagnosis report view, per `PRD.md` §5 Feature 1 and §11 ("Investigation/Diagnosis UI").

**Files/Folders**
- `apps/frontend/app/diagnostics/[connectionId]/page.tsx`
- `apps/frontend/features/diagnosis/components/RootCauseReport.tsx`
- `apps/frontend/features/diagnosis/components/EvidenceTimeline.tsx`
- `apps/frontend/components/charts/EvidenceGraph.tsx` (React Flow, per `ARCHITECTURE.md` §5)

**Implementation**
`diagnostics/[connectionId]/page.tsx`: fetches diagnoses for the connection via `useDiagnoses` (`GET /connections/{id}/diagnoses`), lists them, and on selection loads the full report via `GET /diagnoses/{id}`.
`RootCauseReport.tsx`: renders primary cause, contributing causes, confidence (`ConfidenceMeter`), evidence list, per the JSON shape in `PRD.md` §5 Feature 1.
`EvidenceTimeline.tsx`: renders the "what happened first/next" timeline from the report.
`EvidenceGraph.tsx`: React Flow graph rendering the causal evidence chain (e.g., bulk load → stale stats → cardinality error → plan flip → latency increase), per `ARCHITECTURE.md` §1/§5 — **reusable** wherever an evidence graph needs displaying.

**Backend/API Dependency**
`GET /connections/{id}/diagnoses`, `GET /diagnoses/{id}` (`BACKEND_STEPS.md` Step 19 — Feature 1 complete).

**Verification**
Trigger a real diagnosis run against a seeded fault-injected test DB via the backend; confirm the UI renders a complete, evidence-traceable root-cause report matching backend output exactly (no fabricated UI-side data).

**Expected Result**
Feature 1 (Root Cause Diagnosis) fully viewable end-to-end in the UI.

---

### Step 16 — Recommendations UI (Diagnosis → Candidate Optimizations)

**Goal**
Implement the recommendations list surfaced from a diagnosis, per `PRD.md` §5 Feature 1/§11 ("Recommendations UI").

**Files/Folders**
- `apps/frontend/features/diagnosis/components/RecommendationsList.tsx`
- Update `apps/frontend/app/diagnostics/[connectionId]/page.tsx`

**Implementation**
`RecommendationsList.tsx`: fetches `GET /diagnoses/{id}/recommendations` via `diagnosisService`, displays each candidate optimization with predicted impact/uncertainty, and a "Simulate" action linking to the Experiments UI (Step 17). Composed into the diagnosis detail page.

**Backend/API Dependency**
`GET /diagnoses/{id}/recommendations` (`BACKEND_STEPS.md` Step 19/23).

**Verification**
From a real diagnosis report with generated candidates, confirm the recommendations list renders correctly and each "Simulate" action navigates to/triggers the correct experiment.

**Expected Result**
Users can move from a diagnosis directly into candidate optimization review.

---

### Step 17 — Simulation Results UI (Feature 2)

**Goal**
Implement the simulation/verification report view, per `PRD.md` §5 Feature 2 and §11 ("Simulation Results UI").

**Files/Folders**
- `apps/frontend/app/experiments/[experimentId]/page.tsx`
- `apps/frontend/features/simulation/components/VerificationReport.tsx`
- `apps/frontend/features/simulation/components/SkepticFindings.tsx`
- `apps/frontend/features/simulation/components/PolicyVerdict.tsx`

**Implementation**
`experiments/[experimentId]/page.tsx`: on load, calls `simulationService` to trigger (`POST /recommendations/{id}/simulate`, if not already run) and fetch verification results (`GET /recommendations/{id}/verification`).
`VerificationReport.tsx`: renders baseline vs. candidate latency/p95/p99, bootstrap CI, statistical significance, regression rate — per `PRD.md` §5 Feature 2 example report.
`SkepticFindings.tsx`: lists adversarial findings from the Skeptic Agent.
`PolicyVerdict.tsx`: displays the `VERIFIED`/`CONDITIONAL`/`REJECTED` verdict (`StatusBadge` from Step 11) with the deterministic policy reasoning (e.g., which threshold passed/failed).

**Backend/API Dependency**
`POST /recommendations/{id}/simulate`, `GET /recommendations/{id}/verification` (`BACKEND_STEPS.md` Steps 22–23 — Feature 2 agent graph + service).

**Verification**
Run a real simulation against a seeded candidate; confirm the UI renders statistical results, skeptic findings, and policy verdict exactly matching backend output — no client-side computation of verdicts.

**Expected Result**
Feature 2's simulation/verification pipeline fully viewable in the UI before any approval decision.

---

### Step 18 — Approval UI (Human-in-the-Loop Safety Gate)

**Goal**
Implement the explicit approve/reject flow, per `PRD.md` §5 Feature 2/§6/§9/§11 ("Approval UI").

**Files/Folders**
- `apps/frontend/features/simulation/components/ApprovalPanel.tsx`
- Update `apps/frontend/app/experiments/[experimentId]/page.tsx`

**Implementation**
`ApprovalPanel.tsx`: shown only when a recommendation has reached a `VERIFIED`/`CONDITIONAL` state; presents explicit Approve/Reject buttons calling `simulationService.approve`/`reject` (`POST /recommendations/{id}/approve`, `POST /recommendations/{id}/reject`). On approve, displays confirmation and transitions the page toward the live canary view (Step 19). Enforces role visibility per the authenticated user's role from `auth-store` (only authorized roles see enabled approve/reject controls — RBAC scheme `TBD` per backend `PRD.md` §24, so the UI check is advisory pending backend enforcement).

**Backend/API Dependency**
`POST /recommendations/{id}/approve`, `POST /recommendations/{id}/reject` (`BACKEND_STEPS.md` Step 24 — Human Approval Gate).

**Verification**
Attempt approval as an unauthorized test user (if role check implemented) → UI disables the action; approve as an authorized user → confirm backend records the approval and the UI transitions state; reject → confirm the recommendation is marked rejected and no deployment occurs.

**Expected Result**
No production-modifying action can be triggered from the UI without an explicit, visible human approval step.

---

### Step 19 — Real-Time Updates (SSE: Canary Monitoring & Forecast Streams)

**Goal**
Implement live updates for the two SSE-backed views, per `ARCHITECTURE.md` §1/§5.

**Files/Folders**
- `apps/frontend/features/simulation/components/CanaryLivePanel.tsx`
- `apps/frontend/features/forecasting/components/ForecastLivePanel.tsx`
- Update `apps/frontend/app/experiments/[experimentId]/page.tsx`
- Update `apps/frontend/app/forecasts/[connectionId]/page.tsx`

**Implementation**
`CanaryLivePanel.tsx`: subscribes via `useSSE` (Step 10) to `GET /api/v1/experiments/{id}/canary/stream`, rendering live p50/p95/p99, error rate, lock waits, CPU, IO, throughput, write latency as they stream in; shows COMMIT/ROLLBACK outcome when the window closes.
`ForecastLivePanel.tsx`: subscribes to `GET /api/v1/forecasts/{id}/stream` for active/long-running forecast updates.
Both panels fall back gracefully (connection-closed / error state) using `ErrorBanner` (Step 11).
Per `ARCHITECTURE.md` §1/§5: this is the **only** real-time mechanism in the app — every other view uses TanStack Query polling/refetch (already covered in Steps 12–17).

**Backend/API Dependency**
Both SSE endpoints (`BACKEND_STEPS.md` Step 23 canary stream, Step 27 forecast stream).

**Verification**
Trigger a real canary deployment; confirm the live panel updates in real time during the monitoring window and correctly reflects the final commit/rollback outcome; same for an active forecast.

**Expected Result**
Live, streaming updates work correctly for the two features that require them.

---

### Step 20 — Forecasting UI (Feature 3)

**Goal**
Implement the degradation forecast and closed-loop learning views, per `PRD.md` §5 Feature 3 and §11.

**Files/Folders**
- `apps/frontend/app/forecasts/[connectionId]/page.tsx`
- `apps/frontend/features/forecasting/components/ForecastTimeline.tsx`
- `apps/frontend/features/forecasting/components/BanditPerformanceView.tsx`
- `apps/frontend/components/charts/CalibrationChart.tsx`
- `apps/frontend/components/charts/MaeOverIterationsChart.tsx`

**Implementation**
`ForecastTimeline.tsx`: renders the `degradation_probability(t)` curve with prediction intervals, fetched via `useForecasts` (`GET /forecast/{connectionId}`).
`BanditPerformanceView.tsx`: displays the L3 bandit's strategy-selection performance (per `PRD.md` §5 Feature 3), sourced from the same forecast/model-performance endpoints.
`CalibrationChart.tsx`: predicted-confidence vs. actual-coverage across confidence buckets (`GET /models/performance`) — **reusable** chart component per `ARCHITECTURE.md` §5.
`MaeOverIterationsChart.tsx`: prediction-error-over-iterations chart (the "system is improving" visual) — **reusable**.

**Backend/API Dependency**
`GET /forecast/{connectionId}`, `GET /models/performance` (`BACKEND_STEPS.md` Step 27).

**Verification**
With backend forecast data seeded, confirm the timeline, calibration chart, and MAE chart render values matching the backend's raw response exactly.

**Expected Result**
Feature 3 (Predictive ML + Closed-Loop Optimization) fully viewable in the UI.

---

### Step 21 — Optimization History / Audit Trail UI

**Goal**
Implement the experiment history/audit view, per `PRD.md` §11 ("Optimization History / Audit Trail").

**Files/Folders**
- `apps/frontend/app/experiments/page.tsx` (list view — add to routing skeleton if not already present; note `[experimentId]/page.tsx` from Step 17 is the detail view)
- `apps/frontend/features/simulation/components/ExperimentHistoryTable.tsx`

**Implementation**
`ExperimentHistoryTable.tsx`: uses `DataTable` (Step 11) to list all experiments via `GET /experiments`, with columns for strategy, status (VERIFIED/CONDITIONAL/REJECTED), deployment outcome (COMMIT/ROLLBACK), and links into the detail page (Step 17).

**Backend/API Dependency**
`GET /experiments` (`BACKEND_STEPS.md` Step 23).

**Verification**
Confirm the history table lists all backend-recorded experiments accurately, including rolled-back ones.

**Expected Result**
A complete, filterable audit trail of every optimization experiment.

---

### Step 22 — ROI UI (Feature 4)

**Goal**
Implement the cost/performance analytics view, per `PRD.md` §5 Feature 4 and §11 ("Cost/Performance Analytics").

**Files/Folders**
- `apps/frontend/app/roi/page.tsx`
- `apps/frontend/features/roi/components/RoiCard.tsx`

**Implementation**
`RoiCard.tsx`: "$ saved / month" card per verified optimization, fetched via `useRoi` (`roiService`). Must correctly render the backend's "cost model not configured" fallback state (per `PRD.md` §5 Feature 4 Failure cases) rather than fabricating a number client-side.

**Backend/API Dependency**
ROI data endpoint (`BACKEND_STEPS.md` Step 28 — exact route `TBD` per `PRD.md` §12, likely attached to experiment records).

**Verification**
With a committed optimization and configured pricing model on the backend, confirm the ROI card shows a correct dollar figure; with pricing unconfigured, confirm the "not configured" state renders instead of a blank or fabricated value.

**Expected Result**
Feature 4 (Cost-to-Dollar ROI) viewable in the UI, honestly reflecting backend TBD/unconfigured states.

---

### Step 23 — Loading, Error, and Empty States (Global Pass)

**Goal**
Ensure every data-driven view handles loading/error/empty states consistently, per `ARCHITECTURE.md` §5 (TanStack Query owns these states).

**Files/Folders**
- Update all page/feature components from Steps 12–22 to use `LoadingSkeleton.tsx`, `ErrorBanner.tsx`, `EmptyState.tsx` (Step 11)

**Implementation**
Audit every `useQuery`/`useMutation` consumer built in Steps 12–22: render `LoadingSkeleton` while `isLoading`, `ErrorBanner` on `isError` (surfacing the normalized error from `lib/api-client.ts`), and `EmptyState` when a list/report returns empty (e.g., "No diagnoses yet," "No connections added," cold-start diagnosis with lowered confidence per `PRD.md` §5 Feature 1 Failure cases).

**Backend/API Dependency**
All endpoints wired in prior steps (this step verifies their failure/empty paths, not new endpoints).

**Verification**
Simulate each state manually: disconnect the backend (error state), query a fresh connection with no data yet (empty state), throttle network (loading state). Confirm every page degrades gracefully.

**Expected Result**
No page ever shows a blank screen, unhandled exception, or silent failure.

---

### Step 24 — Notifications

**Goal**
Implement toast/notification feedback for key actions, per general UX best practice implied by the approval/deployment workflow (`PRD.md` §5/§9) — exact notification requirements not explicitly specified in source docs (`TBD` scope, implemented at minimum for critical actions).

**Files/Folders**
- `apps/frontend/components/ui/Toast.tsx` (from Step 11, wired here)
- `apps/frontend/hooks/useNotifications.ts`

**Implementation**
`useNotifications.ts`: a small hook/context triggering toast notifications on: connection test success/failure (Step 13), simulation complete (Step 17), approval submitted (Step 18), canary commit/rollback (Step 19), forecast risk threshold crossed (Step 20, if surfaced). Notification triggers hook into existing `useMutation`/`useSSE` success/error callbacks — no new backend calls.

**Backend/API Dependency**
None new — reuses signals from previously wired endpoints/streams.

**Verification**
Trigger each listed action; confirm a toast appears with an accurate message and dismisses correctly.

**Expected Result**
Users receive clear, immediate feedback for all key state-changing actions.

---

### Step 25 — Charts & Data Visualization Consolidation

**Goal**
Finalize all chart components as a cohesive, reusable set, per `ARCHITECTURE.md` §5 (`components/charts/`).

**Files/Folders**
- `apps/frontend/components/charts/EvidenceGraph.tsx` (Step 15, finalize)
- `apps/frontend/components/charts/CalibrationChart.tsx` (Step 20, finalize)
- `apps/frontend/components/charts/MaeOverIterationsChart.tsx` (Step 20, finalize)

**Implementation**
Review all three chart components for consistent theming, responsive sizing, and shared prop conventions (per `ARCHITECTURE.md` §5 — "reused across feature pages"). Confirm `EvidenceGraph.tsx` (React Flow) correctly renders arbitrary evidence-graph shapes returned by the backend, not just the fixture used in Step 15.

**Backend/API Dependency**
Same as Steps 15 and 20 (no new endpoints).

**Verification**
Render each chart with varied real backend data (multiple diagnosis shapes, multiple calibration bucket counts, multi-version MAE history); confirm no layout breakage.

**Expected Result**
A polished, reusable charting layer used consistently across Diagnostics, Forecasts, and Models Performance views.

---

### Step 26 — Responsive Design Pass

**Goal**
Ensure all pages work across desktop and smaller viewports.

**Files/Folders**
- Global CSS/styling updates across `components/ui/`, `components/charts/`, and all `app/**/page.tsx` files

**Implementation**
Apply responsive breakpoints to the navigation shell (Step 6), data tables (collapse to card view on small screens), the evidence graph and charts (horizontal scroll or resize on narrow viewports), and the approval panel (Step 18) to ensure critical actions remain usable on tablet-width screens. Exact target breakpoints/devices: `TBD` (not specified in source docs — assume standard desktop/tablet/mobile breakpoints).

**Backend/API Dependency**
None.

**Verification**
Manually test each page at common viewport widths (e.g., 375px, 768px, 1280px) or via browser dev-tools device emulation; confirm no horizontal overflow or unusable controls.

**Expected Result**
The full application is usable across common device widths.

---

### Step 27 — Frontend Unit & Component Tests

**Goal**
Cover components, hooks, and services with tests, per `ARCHITECTURE.md` §5 (`tests/`).

**Files/Folders**
- `apps/frontend/tests/unit/components/*.test.tsx` (one per key `components/ui/` and `components/charts/` component)
- `apps/frontend/tests/unit/services/*.test.ts` (one per `services/*Service.ts`)
- `apps/frontend/tests/unit/hooks/*.test.ts` (one per custom hook)

**Implementation**
Using a component-testing framework (`TBD` — e.g., Vitest/Jest + React Testing Library; not specified in source docs), write tests for: `StatusBadge`/`ConfidenceMeter` rendering variants (Step 11), each service module's request construction against a mocked `api-client` (Step 10), and each feature hook's loading/success/error state transitions.

**Backend/API Dependency**
None (all backend calls mocked).

**Verification**
`npm run test` passes with meaningful coverage of presentational components, service request-building logic, and hook state transitions.

**Expected Result**
Core frontend logic is regression-tested independent of a live backend.

---

### Step 28 — Backend Integration Testing (Frontend ↔ Real API)

**Goal**
Verify the full frontend works against a real running backend, per the complete user journey in `PRD.md` §4.

**Files/Folders**
- `apps/frontend/tests/integration/user-journey.spec.ts` (end-to-end test — framework `TBD`, e.g. Playwright/Cypress; not specified in source docs)

**Implementation**
Run an end-to-end test against the Dockerized backend stack (per `BACKEND_STEPS.md` Step 36) and a locally served frontend build: signup/login → connect a test database → wait for telemetry → view dashboard → open a diagnosis → view a recommendation → run simulation → view verification report → approve → watch live canary panel → confirm commit/rollback → view ROI card → view forecast page.

**Backend/API Dependency**
Full backend stack running (`BACKEND_STEPS.md` Steps 1–37 complete, or at minimum through Step 34).

**Verification**
The end-to-end test suite passes against the live backend without any mocked network calls.

**Expected Result**
The entire documented user journey (`PRD.md` §4) works correctly through the real UI against the real backend.

---

### Step 29 — Production Build

**Goal**
Produce a deployable production build, per `ARCHITECTURE.md` §6 (`frontend.Dockerfile`).

**Files/Folders**
- `apps/frontend/next.config.js` (production settings review)
- `infra/docker/frontend.Dockerfile`

**Implementation**
Configure `next.config.js` for production (output mode, image optimization settings if used, environment variable exposure limited to `NEXT_PUBLIC_*`). `frontend.Dockerfile`: multi-stage build producing the optimized Next.js production image, per `ARCHITECTURE.md` §6.

**Backend/API Dependency**
`NEXT_PUBLIC_API_BASE_URL` must point at the production/staging backend URL for the built image to function correctly.

**Verification**
`npm run build` completes with no errors/warnings that block production; `docker build` on `frontend.Dockerfile` succeeds; the resulting container serves the app on its published port (per `ARCHITECTURE.md` §6 — only `frontend`/`backend` publish ports).

**Expected Result**
A production-ready, containerized frontend build.

---

### Step 30 — Final Frontend Verification

**Goal**
Confirm the complete frontend satisfies every UI requirement in `PRD.md` §11 and every page/workflow defined across this document.

**Files/Folders**
- No new files; full-system verification pass.

**Implementation**
Walk through every page listed in `PRD.md` §11 against the production build + real backend (`docker-compose up` per `BACKEND_STEPS.md` Step 36): Dashboard, Connection flow, Monitoring UI, Investigation/Diagnosis UI, Recommendations UI, Simulation Results UI, Approval UI, Optimization History/Audit Trail, Cost/Performance Analytics. Confirm authentication gating, real-time updates (SSE), loading/error/empty states, and responsive behavior all function correctly together as one cohesive application.

**Backend/API Dependency**
Full backend stack (`BACKEND_STEPS.md` Step 37 complete).

**Verification**
Manual full-app walkthrough + automated integration suite (Step 28) passing against the production build.

**Expected Result**
A complete, verified frontend implementation of the AI Database Administrator, fully integrated with the backend and ready for deployment.

---

## Frontend Build Order

1. Project scaffolding
2. Dependencies
3. Environment configuration
4. API client foundation (`lib/api-client.ts`, `lib/sse-client.ts`)
5. Generated API types
6. Global layout & design system foundation
7. Routing skeleton
8. TanStack Query setup
9. Authentication UI & auth store
10. Feature service modules & data hooks
11. Shared reusable components
12. Dashboard page
13. Database connection UI
14. Monitoring UI
15. Diagnostics UI (Feature 1)
16. Recommendations UI
17. Simulation results UI (Feature 2)
18. Approval UI
19. Real-time updates (SSE: canary + forecast)
20. Forecasting UI (Feature 3)
21. Optimization history / audit trail UI
22. ROI UI (Feature 4)
23. Loading/error/empty states (global pass)
24. Notifications
25. Charts & data visualization consolidation
26. Responsive design pass
27. Frontend unit & component tests
28. Backend integration testing
29. Production build
30. Final frontend verification

---

## Frontend Definition of Done

**Pages**
- [ ] Login / Signup (`(auth)/login`, `(auth)/signup`)
- [ ] Dashboard (`/dashboard`)
- [ ] Connections (`/connections`)
- [ ] Monitoring (`/connections/[connectionId]/monitoring`)
- [ ] Diagnostics (`/diagnostics/[connectionId]`)
- [ ] Experiments list + detail (`/experiments`, `/experiments/[experimentId]`)
- [ ] Forecasts (`/forecasts/[connectionId]`)
- [ ] ROI (`/roi`)

**Components**
- [ ] Shared `components/ui/` primitives complete and reused across all pages
- [ ] `components/charts/` (EvidenceGraph, CalibrationChart, MaeOverIterationsChart) complete and reused
- [ ] Feature-scoped components under `features/diagnosis/`, `features/simulation/`, `features/forecasting/`, `features/roi/`

**Authentication**
- [ ] Login/signup working against real backend JWT cookie flow
- [ ] `auth-store.ts` correctly holds only non-sensitive profile data
- [ ] Middleware route protection redirects unauthenticated users

**API Integration**
- [ ] `lib/api-client.ts` used by every backend call (no direct `fetch` elsewhere)
- [ ] `types/api.ts` generated and kept in sync with backend OpenAPI schema
- [ ] Every `services/*Service.ts` module maps 1:1 to its backend route group

**State Management**
- [ ] TanStack Query owns all server state (data, loading, error, caching)
- [ ] Zustand (`auth-store.ts`) owns only client-side auth profile state
- [ ] No server data duplicated into Zustand or component state unnecessarily

**Feature Workflows**
- [ ] Connect DB → test connection → telemetry visible
- [ ] Diagnosis → evidence graph + root-cause report → recommendations
- [ ] Recommendation → simulate → verification report → skeptic findings → policy verdict
- [ ] Approval → canary live panel (SSE) → commit/rollback outcome
- [ ] Forecast → degradation curve → calibration/MAE charts
- [ ] Committed optimization → ROI card (or "not configured" state)

**Error/Loading States**
- [ ] Every data view has loading, error, and empty states implemented
- [ ] Errors from `api-client.ts` surfaced via `ErrorBanner`, never silently swallowed
- [ ] Notifications fire for all key state-changing actions

**Responsive UI**
- [ ] Navigation, tables, charts, and approval panel usable at common breakpoints
- [ ] No horizontal overflow or blocked critical actions on smaller viewports

**Testing**
- [ ] Unit tests for shared components, services, and hooks passing
- [ ] End-to-end integration test covering the full `PRD.md` §4 user journey passing against a live backend

**Production Build**
- [ ] `npm run build` succeeds cleanly
- [ ] `frontend.Dockerfile` builds and serves correctly
- [ ] `NEXT_PUBLIC_API_BASE_URL` correctly configured for target environment
- [ ] Full app verified end-to-end against the Dockerized backend stack
