CLANK. I dropped a **production-grade TanStack Query skeleton** into the canvas with all the wiring you need (QueryClient, query key factory, `queryOptions` helpers, React Router loader prefetch, widget hydration, and invalidation). You can read/modify everything there.

Here’s the why + how, tied to the docs:

## Core ideas we’re using

* **Array query keys that include every variable** the fetch depends on, so caching and dedupe “just work.” Keys are array-based and must be JSON-serializable; TanStack hashes them deterministically. ([TanStack][1])
* **`queryOptions` helpers** co-locate `queryKey` + `queryFn` (and defaults) once, then feed the same options to `useQuery`, `prefetchQuery`, or `ensureQueryData` for full type-safety. ([TanStack][2])
* **Router loader prefetch** uses `queryClient.ensureQueryData` for the spec and `prefetchQuery` for widgets to avoid waterfalls on initial render. `ensureQueryData` will ignore `staleTime` and return cached data if present; prefetched queries are GC’d after `gcTime` if they’re never mounted. ([TanStack][3])
* **Cancellation**: your query functions receive an **`AbortSignal`**; we pass it through to `fetch` in the API client so stale/abandoned requests are canceled automatically. ([TanStack][4])
* **Smooth table transitions**: we use `placeholderData: keepPreviousData` (v5 replacement) so paging/filter changes don’t flash. ([TanStack][5])
* **Targeted invalidation**: we shape keys as `['widget', specId, kind, widgetId, params]` so `invalidateQueries({ queryKey: ['widget', specId] })` refreshes **all** widgets for a spec after a filter change. The docs cover invalidation by key filters. ([TanStack][6])

## What’s in the canvas (ready to run)

* **`providers/QueryProvider.tsx`** — singleton `QueryClient` with production-leaning defaults (`staleTime`, `gcTime`, retries, focus/reconnect refetch) and Devtools.
* **`services/api/client.ts`** — thin `fetch` wrapper that injects the **`AbortSignal`** from the query function context, throws on non-OK, and includes `credentials: 'include'`. ([TanStack][4])
* **`types/dashboard.ts`** — minimal `RuntimeSpec`, `KPI`, `PlotlyFigure`, `TablePage` DTOs you described.
* **`hooks/dashboard/queryKeys.ts`** — **query key factory** with spec + widget buckets:

  * `spec(specId)` → `['spec', specId]`
  * `widgetKpi(specId, widgetId, params)` → `['widget', specId, 'kpi', widgetId, params]`
  * `widgetTable(...)`, `widgetFigure(...)` similar.
* **`hooks/dashboard/queries.ts`** — **`queryOptions`** creators (`specQuery`, `widgetKpiQuery`, `widgetTableQuery`, `widgetFigureQuery`) that both components *and* loaders use. ([TanStack][2])
* **`routes/dashboards/loader.ts`** — **prefetch** pattern:

  * `ensureQueryData(specQuery(specId))`
  * `Promise.all([...prefetchQuery(widgetXQuery(...))])` for all widgets in the spec. ([TanStack][3])
* **`hooks/dashboard/useRuntimeWidgets.ts`** — hydration hooks:

  * `useRuntimeSpec(specId)` → `useQuery(specQuery(...))` (doc baseline). ([TanStack][7])
  * `useSpecWidgets(spec)` builds typed descriptors from the spec.
  * `useWidgetData(descriptor)` picks the correct `useQuery(...)`.
* **`hooks/dashboard/useWidgetCache.ts`** — convenience invalidators:

  * `invalidateWidgetsForSpec(specId)` → refresh all widgets under that spec. ([TanStack][8])
* **`routes/dashboards/DashboardRoute.tsx`** — consumes the loader’s `specId`, reads the spec via Query, builds widget descriptors, and renders.
* **`components/dashboard/WidgetRenderer.tsx` & widgets** — simple KPI/DataTable/Figure components reading Query state.

## How to operate this pattern

1. **Prefetch at navigation time**, render from the cache: loader fills the cache; components call `useQuery` with the same `queryOptions`. No duplicate fetches, no waterfalls. ([TanStack][3])
2. **Design keys for the invalidations you need** (that’s why `specId` is the 2nd element for widgets). ([TanStack][1])
3. **Model refresh cadence via `staleTime`** (e.g., KPIs: 30s; specs: 5m) and optional `refetchInterval` for live tiles. (See queries guide for basics). ([TanStack][7])
4. **Keep UX snappy** with `placeholderData: keepPreviousData` for list/table transitions. ([TanStack][5])
5. **Cancellation is automatic** as long as you thread the `signal` into your fetcher. ([TanStack][4])

## Where to tweak first

* Dial `staleTime`/`gcTime` per widget class (KPI vs heavy plot).
* Add `refetchInterval` for any time-series tiles that must auto-refresh.
* If you later co-host with SSR, you can keep the same `queryOptions` and rely on `ensureQueryData` server-side too. ([TanStack][3])

If you want, I can extend this with:

* a typed **filter state → queryKey** adapter for dashboards,
* an **infinite table** variant using `useInfiniteQuery`,
* or a **Plotly renderer** integration.

[1]: https://tanstack.com/query/v5/docs/react/guides/query-keys?utm_source=chatgpt.com "Query Keys | TanStack Query React Docs"
[2]: https://tanstack.com/query/v5/docs/react/guides/query-options?utm_source=chatgpt.com "Query Options | TanStack Query React Docs"
[3]: https://tanstack.com/query/v5/docs/react/guides/prefetching?utm_source=chatgpt.com "Prefetching & Router Integration | TanStack Query React ..."
[4]: https://tanstack.com/query/v5/docs/react/guides/query-cancellation?utm_source=chatgpt.com "Query Cancellation | TanStack Query React Docs"
[5]: https://tanstack.com/query/v5/docs/react/guides/placeholder-query-data?utm_source=chatgpt.com "Placeholder Query Data | TanStack Query React Docs"
[6]: https://tanstack.com/query/v5/docs/react/guides/query-invalidation?utm_source=chatgpt.com "Query Invalidation | TanStack Query React Docs"
[7]: https://tanstack.com/query/v5/docs/react/guides/queries?utm_source=chatgpt.com "TanStack Query React Docs"
[8]: https://tanstack.com/query/latest/docs/reference/QueryClient?utm_source=chatgpt.com "QueryClient | TanStack Query Docs"
