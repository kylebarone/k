// ===============================
// src/providers/QueryProvider.tsx
// ===============================
import { PropsWithChildren } from 'react'
import {
  QueryClient,
  QueryClientProvider,
} from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'

// Singleton QueryClient for SPA usage
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Reasonable production defaults — tune per widget
      staleTime: 60_000,        // 1 min: widgets won't refetch on re-mount within this window
      gcTime: 10 * 60_000,      // 10 min: keep data around when leaving route
      retry: 2,                 // quick resilience for brief network hiccups
      refetchOnWindowFocus: true,
      refetchOnReconnect: true,
    },
    mutations: {
      retry: 1,
    }
  }
})

export function QueryProvider({ children }: PropsWithChildren) {
  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <ReactQueryDevtools initialIsOpen={false} position="bottom-right" />
    </QueryClientProvider>
  )
}

// ===============================
// src/services/api/client.ts
// ===============================
import { QueryFunctionContext } from '@tanstack/react-query'

export const API_BASE = import.meta.env.VITE_API_BASE ?? '/api'

export type HttpMethod = 'GET'|'POST'|'PUT'|'PATCH'|'DELETE'

export interface ApiRequest<TBody = unknown> {
  path: string
  method?: HttpMethod
  body?: TBody
  headers?: Record<string, string>
  // Optional AbortSignal from query function context
  signal?: AbortSignal
}

export async function apiFetch<TResp = unknown, TBody = unknown>({
  path,
  method = 'GET',
  body,
  headers,
  signal
}: ApiRequest<TBody>): Promise<TResp> {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
    body: body != null ? JSON.stringify(body) : undefined,
    signal,
    credentials: 'include',
  })

  if (!res.ok) {
    // Surface useful error context
    const text = await res.text().catch(() => '')
    throw new Error(`API ${method} ${path} failed: ${res.status} ${res.statusText} ${text}`)
  }
  // If there's no content, return undefined as any
  if (res.status === 204) return undefined as any
  return (await res.json()) as TResp
}

// Helpers to bind QueryFunctionContext.signal into api calls
export function withSignal<T extends unknown[], R>(fn: (signal?: AbortSignal, ...rest: T) => Promise<R>) {
  return ({ signal }: QueryFunctionContext, ...rest: T) => fn(signal, ...rest)
}

// ===============================
// src/types/dashboard.ts
// ===============================
// Minimal DTOs — adjust to your backend contracts
export type PlotlyFigure = {
  data: unknown[]
  layout?: Record<string, unknown>
  frames?: unknown[]
}

export type KPI = {
  id: string
  label: string
  valueFmt?: string
  ref: { endpoint: string; params?: Record<string, unknown> }
}

export type DataTableRef = { id: string; columns?: string[]; ref: { endpoint: string; params?: Record<string, unknown> } }
export type PlotRef = { id: string; title?: string; ref: { endpoint: string; params?: Record<string, unknown> } }

export type RuntimeSpec = {
  id: string
  title: string
  description?: string
  metadata?: Record<string, unknown>
  kpi_cards: KPI[]
  dataTables: DataTableRef[]
  plots: PlotRef[]
}

export type TablePage<T = Record<string, unknown>> = {
  rows: T[]
  total?: number
  nextCursor?: string | null
}

// ===============================
// src/services/dashboards.ts
// ===============================
import { apiFetch } from './api/client'
import type { RuntimeSpec } from '@/types/dashboard'

export function getRuntimeSpec(specId: string, signal?: AbortSignal) {
  return apiFetch<RuntimeSpec>({ path: `/dashboards/${specId}/runtime-spec`, signal })
}

// ===============================
// src/services/widget.ts
// ===============================
import { apiFetch } from './api/client'
import type { PlotlyFigure, TablePage } from '@/types/dashboard'

export function getWidgetKpi(
  specId: string,
  widgetId: string,
  params?: Record<string, unknown>,
  signal?: AbortSignal
) {
  return apiFetch<{ value: number; updatedAt?: string }>({
    path: `/dashboards/${specId}/widgets/${widgetId}/kpi`,
    method: 'POST',
    body: params,
    signal,
  })
}

export function getWidgetTable(
  specId: string,
  widgetId: string,
  params?: Record<string, unknown>,
  signal?: AbortSignal
) {
  return apiFetch<TablePage>({
    path: `/dashboards/${specId}/widgets/${widgetId}/table`,
    method: 'POST',
    body: params,
    signal,
  })
}

export function getWidgetFigure(
  specId: string,
  widgetId: string,
  params?: Record<string, unknown>,
  signal?: AbortSignal
) {
  return apiFetch<PlotlyFigure>({
    path: `/dashboards/${specId}/widgets/${widgetId}/figure`,
    method: 'POST',
    body: params,
    signal,
  })
}

// ===============================
// src/hooks/dashboard/queryKeys.ts
// ===============================
// Query key factory — array keys w/ all variables included
export const qk = {
  specs: () => ['specs'] as const,
  spec: (specId: string) => ['spec', specId] as const,
  widgetKpi: (specId: string, widgetId: string, params?: Record<string, unknown>) =>
    ['widget', specId, 'kpi', widgetId, params ?? {}] as const,
  widgetTable: (specId: string, widgetId: string, params?: Record<string, unknown>) =>
    ['widget', specId, 'table', widgetId, params ?? {}] as const,
  widgetFigure: (specId: string, widgetId: string, params?: Record<string, unknown>) =>
    ['widget', specId, 'figure', widgetId, params ?? {}] as const,
}

// ===============================
// src/hooks/dashboard/queries.ts
// ===============================
import { queryOptions, keepPreviousData } from '@tanstack/react-query'
import { qk } from './queryKeys'
import { getRuntimeSpec } from '@/services/dashboards'
import { getWidgetFigure, getWidgetKpi, getWidgetTable } from '@/services/widget'

export const specQuery = (specId: string) =>
  queryOptions({
    queryKey: qk.spec(specId),
    queryFn: ({ signal }) => getRuntimeSpec(specId, signal),
    staleTime: 5 * 60_000, // Typically specs change rarely; cache longer
  })

export const widgetKpiQuery = (
  specId: string,
  widgetId: string,
  params?: Record<string, unknown>
) =>
  queryOptions({
    queryKey: qk.widgetKpi(specId, widgetId, params),
    queryFn: ({ signal }) => getWidgetKpi(specId, widgetId, params, signal),
    staleTime: 30_000,
  })

export const widgetTableQuery = (
  specId: string,
  widgetId: string,
  params?: Record<string, unknown>
) =>
  queryOptions({
    queryKey: qk.widgetTable(specId, widgetId, params),
    queryFn: ({ signal }) => getWidgetTable(specId, widgetId, params, signal),
    staleTime: 30_000,
    // For filter/pagination transitions, keep previous to avoid flashing
    placeholderData: keepPreviousData, // v5 replacement for keepPreviousData
  })

export const widgetFigureQuery = (
  specId: string,
  widgetId: string,
  params?: Record<string, unknown>
) =>
  queryOptions({
    queryKey: qk.widgetFigure(specId, widgetId, params),
    queryFn: ({ signal }) => getWidgetFigure(specId, widgetId, params, signal),
    staleTime: 30_000,
  })

// ===============================
// src/hooks/dashboard/useWidgetCache.ts
// ===============================
import { queryClient } from '@/providers/QueryProvider'
import { qk } from './queryKeys'

export function invalidateWidgetsForSpec(specId: string) {
  // With the key shape ['widget', specId, ...], this invalidates KPI+table+figure queries for the spec
  return queryClient.invalidateQueries({ queryKey: ['widget', specId] })
}


export function invalidateSpec(specId: string) {
  return queryClient.invalidateQueries({ queryKey: qk.spec(specId) })
}

// ===============================
// src/hooks/dashboard/useRuntimeWidgets.ts
// ===============================
import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { RuntimeSpec } from '@/types/dashboard'
import { specQuery, widgetFigureQuery, widgetKpiQuery, widgetTableQuery } from './queries'

export function useRuntimeSpec(specId: string) {
  return useQuery(specQuery(specId))
}

export type WidgetDescriptor =
  | { kind: 'kpi'; specId: string; widgetId: string; params?: Record<string, unknown> }
  | { kind: 'table'; specId: string; widgetId: string; params?: Record<string, unknown> }
  | { kind: 'figure'; specId: string; widgetId: string; params?: Record<string, unknown> }

export function useWidgetData(desc: WidgetDescriptor) {
  switch (desc.kind) {
    case 'kpi':
      return useQuery(widgetKpiQuery(desc.specId, desc.widgetId, desc.params))
    case 'table':
      return useQuery(widgetTableQuery(desc.specId, desc.widgetId, desc.params))
    case 'figure':
      return useQuery(widgetFigureQuery(desc.specId, desc.widgetId, desc.params))
  }
}

export function useSpecWidgets(spec: RuntimeSpec) {
  return useMemo(() => {
    return [
      ...spec.kpi_cards.map((k) => ({ kind: 'kpi', specId: spec.id, widgetId: k.id, params: k.ref.params } as const)),
      ...spec.dataTables.map((t) => ({ kind: 'table', specId: spec.id, widgetId: t.id, params: t.ref.params } as const)),
      ...spec.plots.map((p) => ({ kind: 'figure', specId: spec.id, widgetId: p.id, params: p.ref.params } as const)),
    ] as const
  }, [spec])
}

// ===============================
// src/routes/dashboards/loader.ts
// ===============================
import { queryClient } from '@/providers/QueryProvider'
import { specQuery, widgetFigureQuery, widgetKpiQuery, widgetTableQuery } from '@/hooks/dashboard/queries'
import { getRuntimeSpec } from '@/services/dashboards'

export async function dashboardLoader({ params }: { params: { specId: string } }) {
  const specId = params.specId

  // 1) Ensure the spec is in cache (ignores staleTime and always returns cache if exists)
  const spec = await queryClient.ensureQueryData(specQuery(specId))

  // 2) Prefetch widget data to avoid waterfalls on first paint
  await Promise.all([
    ...spec.kpi_cards.map((k) => queryClient.prefetchQuery(widgetKpiQuery(spec.id, k.id, k.ref.params))),
    ...spec.dataTables.map((t) => queryClient.prefetchQuery(widgetTableQuery(spec.id, t.id, t.ref.params))),
    ...spec.plots.map((p) => queryClient.prefetchQuery(widgetFigureQuery(spec.id, p.id, p.ref.params))),
  ])

  return { specId }
}

// ===============================
// src/routes/dashboards/DashboardRoute.tsx
// ===============================
import { useLoaderData } from 'react-router-dom'
import { useRuntimeSpec, useSpecWidgets } from '@/hooks/dashboard/useRuntimeWidgets'
import { WidgetRenderer } from '@/components/dashboard/WidgetRenderer'
import { DashboardLayout } from '@/components/dashboard/DashboardLayout'

export default function DashboardRoute() {
  const { specId } = useLoaderData() as { specId: string }
  const spec = useRuntimeSpec(specId)

  if (spec.isPending) return <div>Loading dashboard…</div>
  if (spec.isError) return <div>Failed to load spec: {(spec.error as Error).message}</div>

  const widgets = useSpecWidgets(spec.data)
  return (
    <DashboardLayout spec={spec.data}>
      <WidgetRenderer widgets={widgets as any} />
    </DashboardLayout>
  )
}

// ===============================
// src/components/dashboard/WidgetRenderer.tsx
// ===============================
import { WidgetBoundary } from './WidgetBoundary'
import { KpiCard } from './widgets/KpiCard'
import { DataTable } from './widgets/DataTable'
import { PlotFigure } from './widgets/PlotFigure'
import type { WidgetDescriptor } from '@/hooks/dashboard/useRuntimeWidgets'

export function WidgetRenderer({ widgets }: { widgets: readonly WidgetDescriptor[] }) {
  return (
    <div className="grid grid-cols-12 gap-4">
      {widgets.map((w) => (
        <WidgetBoundary key={`${w.kind}-${w.widgetId}`}>
          {w.kind === 'kpi' && <KpiCard desc={w} />}
          {w.kind === 'table' && <DataTable desc={w} />}
          {w.kind === 'figure' && <PlotFigure desc={w} />}
        </WidgetBoundary>
      ))}
    </div>
  )
}

// ===============================
// src/components/dashboard/widgets/KpiCard.tsx
// ===============================
import { useWidgetData } from '@/hooks/dashboard/useRuntimeWidgets'
import type { WidgetDescriptor } from '@/hooks/dashboard/useRuntimeWidgets'

export function KpiCard({ desc }: { desc: Extract<WidgetDescriptor, { kind: 'kpi' }> }) {
  const { data, isPending, isError, error, refetch } = useWidgetData(desc)

  if (isPending) return <div className="p-4">Loading…</div>
  if (isError) return <div className="p-4 text-red-600">{(error as Error).message}</div>

  return (
    <div className="rounded-2xl shadow p-4 bg-white">
      <div className="text-sm text-gray-500">{desc.widgetId}</div>
      <div className="text-3xl font-semibold">{data?.value ?? '—'}</div>
      <button className="text-xs underline" onClick={() => refetch()}>refresh</button>
    </div>
  )
}

// ===============================
// src/components/dashboard/widgets/DataTable.tsx
// ===============================
import { useWidgetData } from '@/hooks/dashboard/useRuntimeWidgets'
import type { WidgetDescriptor } from '@/hooks/dashboard/useRuntimeWidgets'

export function DataTable({ desc }: { desc: Extract<WidgetDescriptor, { kind: 'table' }> }) {
  const { data, isPending, isError, error, isPlaceholderData } = useWidgetData(desc)

  if (isPending && !isPlaceholderData) return <div className="p-4">Loading table…</div>
  if (isError) return <div className="p-4 text-red-600">{(error as Error).message}</div>

  return (
    <div className="rounded-2xl shadow p-4 bg-white overflow-auto">
      <table className="min-w-full text-sm">
        <thead>
          <tr>
            {data?.rows?.[0] && Object.keys(data.rows[0]).map((col) => (
              <th key={col} className="text-left px-2 py-1 border-b">{col}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data?.rows?.map((row: any, i: number) => (
            <tr key={i} className="odd:bg-gray-50">
              {Object.entries(row).map(([k, v]) => (
                <td key={k} className="px-2 py-1 border-b">{String(v)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ===============================
// src/components/dashboard/widgets/PlotFigure.tsx
// ===============================
import { useWidgetData } from '@/hooks/dashboard/useRuntimeWidgets'
import type { WidgetDescriptor } from '@/hooks/dashboard/useRuntimeWidgets'

// Note: You will likely replace this with react-plotly.js or a custom renderer
export function PlotFigure({ desc }: { desc: Extract<WidgetDescriptor, { kind: 'figure' }> }) {
  const { data, isPending, isError, error } = useWidgetData(desc)

  if (isPending) return <div className="p-4">Loading plot…</div>
  if (isError) return <div className="p-4 text-red-600">{(error as Error).message}</div>

  return (
    <pre className="rounded-2xl shadow p-4 bg-white text-xs overflow-auto">{JSON.stringify(data, null, 2)}</pre>
  )
}

// ===============================
// src/routes/root.tsx
// ===============================
import { Outlet } from 'react-router-dom'
import { QueryProvider } from '@/providers/QueryProvider'

export default function RootLayout() {
  return (
    <QueryProvider>
      <Outlet />
    </QueryProvider>
  )
}

// ===============================
// src/App.tsx
// ===============================
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import RootLayout from '@/routes/root'
import DashboardRoute from '@/routes/dashboards/DashboardRoute'
import { dashboardLoader } from '@/routes/dashboards/loader'

const router = createBrowserRouter([
  {
    path: '/',
    element: <RootLayout />,
    children: [
      { path: 'dashboards/:specId', element: <DashboardRoute />, loader: dashboardLoader },
      // ...other routes
    ],
  },
])

export default function App() {
  return <RouterProvider router={router} />
}

// ===============================
// src/components/dashboard/WidgetBoundary.tsx
// ===============================
import { ReactNode } from 'react'

export function WidgetBoundary({ children }: { children: ReactNode }) {
  // Placeholder for an error boundary per widget
  return <div>{children}</div>
}
