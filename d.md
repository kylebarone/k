Let’s wire this into something you can evolve fast: upload/query → dataframe/table → chart pane with a pluggable renderer registry. I’ll keep it tight and pragmatic.


# Suggested folder structure

```
src/
  components/
    DataSourcePanel.tsx
    DataTable.tsx
    ChartPane.tsx
    charts/
      ChartJSRenderer.tsx
      PlotlyFigureWrapper.tsx
  lib/
    dataframe.ts
    payloads.ts
    adapters/
      chartjsAdapter.ts
  routes/  (keep using your TanStack Router setup)
    charts.route.tsx
```

---

## Core types (dataframe + payloads)

**`src/lib/dataframe.ts`**

```ts
export type DType = 'number' | 'string' | 'boolean' | 'date';

export type Column = {
  name: string;
  dtype: DType;
};

export type DataFrame = {
  columns: Column[];
  // rows[i][j] corresponds to columns[j]
  rows: (string | number | boolean | Date | null)[][];
};

// minimal utilities
export const inferDType = (v: unknown): DType => {
  if (typeof v === 'number') return 'number';
  if (typeof v === 'boolean') return 'boolean';
  if (v instanceof Date) return 'date';
  // naive date parse fallback
  if (typeof v === 'string' && !Number.isNaN(Date.parse(v))) return 'date';
  return 'string';
};
```

**`src/lib/payloads.ts`**

```ts
export type ChartKind = 'bar' | 'line' | 'scatter' | 'pie' | 'area';
export type ChartLibrary = 'chartjs' | 'plotly' | 'echarts';

export type ChartSpec = {
  kind: ChartKind;
  // mapping from dataframe columns -> encodings
  x?: string;
  y?: string | string[];
  color?: string;     // group-by column
  agg?: 'sum' | 'avg' | 'count' | 'min' | 'max';
  options?: Record<string, unknown>; // passthrough styling/axes/etc
};

export type ChartPayload = {
  id: string;
  title?: string;
  library: ChartLibrary;
  spec: ChartSpec;
  dataFrameId: string;
};

export type NLQueryRequest = { query: string };
export type NLQueryResponse = {
  dataFrames: Record<string, import('./dataframe').DataFrame>;
  charts: ChartPayload[];
};
```

---

## Chart registry (plug-in style)

**`src/app/chartRegistry.ts`**

```ts
import type { ChartPayload } from '@/lib/payloads';
import ChartJSRenderer from '@/components/charts/ChartJSRenderer';

type Renderer = (props: { payload: ChartPayload }) => JSX.Element;

const registry: Record<string, Renderer> = {
  chartjs: ({ payload }) => <ChartJSRenderer payload={payload} />,
  // plotly: ({ payload }) => <PlotlyRenderer payload={payload} />,
  // echarts: ({ payload }) => <EChartsRenderer payload={payload} />,
};

export const renderChart = (payload: ChartPayload) => {
  const R = registry[payload.library];
  if (!R) return <div className="text-sm text-red-600">No renderer for {payload.library}</div>;
  return <R payload={payload} />;
};
```

---

## Chart.js adapter + renderer

**`src/lib/adapters/chartjsAdapter.ts`**

```ts
import type { DataFrame } from '@/lib/dataframe';
import type { ChartPayload } from '@/lib/payloads';

type ChartJSData = {
  labels: (string | number)[];
  datasets: { label?: string; data: number[] }[];
};

export function toChartJS(payload: ChartPayload, df: DataFrame): { type: string; data: ChartJSData; options?: any } {
  const { spec } = payload;
  const x = spec.x!;
  const ys = Array.isArray(spec.y) ? spec.y : [spec.y!];
  const colorBy = spec.color;

  // Build an index on columns
  const colIndex = Object.fromEntries(df.columns.map((c, i) => [c.name, i]));
  const xi = colIndex[x];

  // simple group-by flow if color present; otherwise just one dataset per y
  const labels = df.rows.map(r => r[xi] as string | number);

  const makeSeries = (y: string) => {
    const yi = colIndex[y];
    if (colorBy) {
      const ci = colIndex[colorBy];
      const groups = new Map<string, number[]>();
      df.rows.forEach(r => {
        const key = String(r[ci]);
        const arr = groups.get(key) ?? [];
        arr.push(Number(r[yi]));
        groups.set(key, arr);
      });
      // Align by label order (naive; assumes rows already grouped per x)
      const groupNames = Array.from(groups.keys());
      // Reconstruct per group in row order
      const byGroup: Record<string, number[]> = {};
      df.rows.forEach(r => {
        const g = String(r[ci]);
        byGroup[g] ??= [];
        byGroup[g].push(Number(r[yi]));
      });
      return groupNames.map(gn => ({ label: `${y} • ${gn}`, data: byGroup[gn] }));
    } else {
      return [{ label: y, data: df.rows.map(r => Number(r[yi])) }];
    }
  };

  const datasets = ys.flatMap(makeSeries);

  const typeMap: Record<string, string> = {
    line: 'line',
    bar: 'bar',
    area: 'line', // Chart.js 'area' is a line with fill
    scatter: 'scatter',
    pie: 'pie',
  };

  const type = typeMap[spec.kind] ?? 'line';
  const options = spec.options ?? {};
  if (spec.kind === 'area') {
    options.elements ??= {};
    options.elements.line ??= {};
    options.elements.line.fill = true;
  }

  return { type, data: { labels, datasets }, options };
}
```

**`src/components/charts/ChartJSRenderer.tsx`**

```tsx
import { useMemo } from 'react';
import { Chart as ChartJS, LineElement, PointElement, BarElement, LinearScale, CategoryScale, ArcElement, Tooltip, Legend } from 'chart.js';
import { Line, Bar, Pie, Scatter } from 'react-chartjs-2';
import { toChartJS } from '@/lib/adapters/chartjsAdapter';
import type { ChartPayload } from '@/lib/payloads';
import { useQuery } from '@tanstack/react-query';
import type { DataFrame } from '@/lib/dataframe';

ChartJS.register(LineElement, PointElement, BarElement, LinearScale, CategoryScale, ArcElement, Tooltip, Legend);

export default function ChartJSRenderer({ payload }: { payload: ChartPayload }) {
  const { data: bundle } = useQuery({
    queryKey: ['df-for-chart', payload.dataFrameId],
    queryFn: async (): Promise<{ df: DataFrame }> => {
      // In your app, replace with real source; here assume it’s already cached by NL/Upload step
      const store = (window as any).__DF_STORE__ as Record<string, DataFrame>;
      return { df: store[payload.dataFrameId] };
    },
  });

  const chart = useMemo(() => {
    if (!bundle?.df) return null;
    return toChartJS(payload, bundle.df);
  }, [bundle?.df, payload]);

  if (!chart) return <div className="text-sm text-neutral-500">Loading chart…</div>;

  const Comp = chart.type === 'bar' ? Bar
    : chart.type === 'pie' ? Pie
    : chart.type === 'scatter' ? Scatter
    : Line;

  return (
    <div className="p-4 rounded-2xl shadow-sm bg-white">
      {payload.title && <div className="mb-2 font-medium">{payload.title}</div>}
      <Comp data={chart.data as any} options={chart.options} />
    </div>
  );
}
```

---

## Data source panel (upload CSV or NL query)

**`src/components/DataSourcePanel.tsx`**

```tsx
import { useState } from 'react';
import { z } from 'zod';
import Papa from 'papaparse';
import { Button, TextField, Stack, Typography } from '@mui/material';
import { useQueryClient } from '@tanstack/react-query';
import type { DataFrame } from '@/lib/dataframe';
import { inferDType } from '@/lib/dataframe';
import type { NLQueryResponse } from '@/lib/payloads';

const QuerySchema = z.object({ query: z.string().min(2) });

function csvToDataFrame(csvText: string): DataFrame {
  const parsed = Papa.parse<string[]>(csvText, { header: true, dynamicTyping: true });
  const rows = (parsed.data as any[]).filter(r => r && Object.keys(r).length);
  const colNames = parsed.meta.fields ?? Object.keys(rows[0] ?? {});
  const firstRow = rows[0] ?? {};
  const columns = colNames.map(name => ({
    name,
    dtype: inferDType(firstRow[name]),
  }));
  const matrix = rows.map(r => colNames.map(c => r[c] ?? null));
  return { columns, rows: matrix };
}

export default function DataSourcePanel({
  onLoad,
  onCharts,
}: {
  onLoad: (dfs: Record<string, DataFrame>) => void;
  onCharts: (charts: NLQueryResponse['charts']) => void;
}) {
  const qc = useQueryClient();
  const [query, setQuery] = useState('');

  const handleUpload = async (file: File) => {
    const text = await file.text();
    const df = csvToDataFrame(text);
    const id = crypto.randomUUID();
    (window as any).__DF_STORE__ ??= {};
    (window as any).__DF_STORE__[id] = df;
    onLoad({ [id]: df });
    // prime cache
    qc.setQueryData(['df-for-chart', id], { df });
  };

  const fakeNL = async (q: string): Promise<NLQueryResponse> => {
    // MOCK: sales by store grouped by region => create a toy df + charts
    const dfId = crypto.randomUUID();
    const df: DataFrame = {
      columns: [
        { name: 'region', dtype: 'string' },
        { name: 'store', dtype: 'string' },
        { name: 'sales', dtype: 'number' },
      ],
      rows: [
        ['East', 'A', 120], ['East', 'B', 150], ['West', 'C', 80],
        ['West', 'D', 130], ['North', 'E', 90], ['South', 'F', 110],
      ],
    };
    (window as any).__DF_STORE__ ??= {};
    (window as any).__DF_STORE__[dfId] = df;

    return {
      dataFrames: { [dfId]: df },
      charts: [
        {
          id: crypto.randomUUID(),
          title: 'Sales by Store (Bar)',
          library: 'chartjs',
          dataFrameId: dfId,
          spec: { kind: 'bar', x: 'store', y: 'sales', color: 'region' },
        },
        {
          id: crypto.randomUUID(),
          title: 'Sales by Store (Line)',
          library: 'chartjs',
          dataFrameId: dfId,
          spec: { kind: 'line', x: 'store', y: 'sales', color: 'region' },
        },
      ],
    };
  };

  const runQuery = async () => {
    const { query: q } = QuerySchema.parse({ query });
    const resp = await fakeNL(q);
    // load frames & charts
    onLoad(resp.dataFrames);
    onCharts(resp.charts);
    // prime cache for all dataframes
    for (const [id, df] of Object.entries(resp.dataFrames)) {
      qc.setQueryData(['df-for-chart', id], { df });
    }
  };

  return (
    <div className="p-4 rounded-2xl bg-white shadow-sm">
      <Typography variant="h6" className="mb-3">Data Source</Typography>
      <Stack direction="row" spacing={2} alignItems="center" className="mb-3">
        <Button variant="outlined" component="label">
          Upload CSV
          <input hidden type="file" accept=".csv,text/csv" onChange={e => {
            const f = e.target.files?.[0];
            if (f) handleUpload(f);
          }} />
        </Button>
        <span className="text-sm text-neutral-500">or</span>
        <TextField
          size="small"
          placeholder="Ask for data (e.g., 'sales by store grouped by region')"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="flex-1"
        />
        <Button variant="contained" onClick={runQuery}>Fetch</Button>
      </Stack>
      <div className="text-xs text-neutral-500">CSV → DataFrame; Query → mocked NL API for now.</div>
    </div>
  );
}
```

---

## Table view (TanStack Table)

**`src/components/DataTable.tsx`**

```tsx
import * as React from 'react';
import { useMemo } from 'react';
import { useReactTable, getCoreRowModel, flexRender, createColumnHelper } from '@tanstack/react-table';
import type { DataFrame } from '@/lib/dataframe';

export default function DataTable({ df }: { df: DataFrame }) {
  const columnHelper = createColumnHelper<any>();
  const columns = useMemo(
    () =>
      df.columns.map((c, idx) =>
        columnHelper.accessor((row) => row[idx], {
          id: c.name,
          header: c.name,
          cell: (info) => String(info.getValue() ?? ''),
        }),
      ),
    [df.columns],
  );

  const table = useReactTable({
    data: df.rows,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div className="overflow-auto rounded-2xl border border-neutral-200">
      <table className="min-w-full text-sm">
        <thead className="bg-neutral-50">
          {table.getHeaderGroups().map(hg => (
            <tr key={hg.id}>
              {hg.headers.map(h => (
                <th key={h.id} className="px-3 py-2 text-left font-medium">
                  {flexRender(h.column.columnDef.header, h.getContext())}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map(r => (
            <tr key={r.id} className="odd:bg-white even:bg-neutral-50">
              {r.getVisibleCells().map(c => (
                <td key={c.id} className="px-3 py-2 whitespace-nowrap">
                  {flexRender(c.column.columnDef.cell, c.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

---

## Chart pane

**`src/components/ChartPane.tsx`**

```tsx
import type { DataFrame } from '@/lib/dataframe';
import type { ChartPayload } from '@/lib/payloads';
import { renderChart } from '@/app/chartRegistry';

export default function ChartPane({
  frames,
  charts,
}: {
  frames: Record<string, DataFrame>;
  charts: ChartPayload[];
}) {
  if (!Object.keys(frames).length && !charts.length) {
    return <div className="text-sm text-neutral-500">Load data or run a query to see charts.</div>;
  }
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {charts.map((p) => (
        <div key={p.id}>{renderChart(p)}</div>
      ))}
    </div>
  );
}
```

---

## Route page that ties it together

**`src/routes/charts.route.tsx`**

```tsx
import * as React from 'react';
import { useState } from 'react';
import DataSourcePanel from '@/components/DataSourcePanel';
import DataTable from '@/components/DataTable';
import ChartPane from '@/components/ChartPane';
import type { DataFrame } from '@/lib/dataframe';
import type { ChartPayload } from '@/lib/payloads';
import { Typography, Tabs, Tab, Box } from '@mui/material';

export default function ChartsRoute() {
  const [frames, setFrames] = useState<Record<string, DataFrame>>({});
  const [charts, setCharts] = useState<ChartPayload[]>([]);
  const [activeDf, setActiveDf] = useState<string | null>(null);
  const [tab, setTab] = useState(0);

  const handleLoad = (dfs: Record<string, DataFrame>) => {
    setFrames(prev => ({ ...prev, ...dfs }));
    const firstId = Object.keys(dfs)[0];
    if (firstId) setActiveDf(firstId);
  };

  return (
    <div className="p-6 space-y-4">
      <Typography variant="h5">Charting Demo</Typography>
      <DataSourcePanel onLoad={handleLoad} onCharts={setCharts} />

      <Box className="rounded-2xl bg-white shadow-sm">
        <Tabs value={tab} onChange={(_, v) => setTab(v)} className="px-4" variant="scrollable">
          <Tab label="Table" />
          <Tab label={`Charts (${charts.length})`} />
        </Tabs>
        <div className="p-4">
          {tab === 0 && (
            <>
              {!activeDf ? (
                <div className="text-sm text-neutral-500">No dataframe loaded yet.</div>
              ) : (
                <>
                  <div className="mb-2 text-xs text-neutral-500">
                    Active DataFrame: <code>{activeDf}</code>
                  </div>
                  <DataTable df={frames[activeDf]} />
                </>
              )}
            </>
          )}
          {tab === 1 && <ChartPane frames={frames} charts={charts} />}
        </div>
      </Box>
    </div>
  );
}
```

---

## App providers (Query + MUI + your Tailwind)

**`src/app/queryClient.ts`**

```ts
import { QueryClient } from '@tanstack/react-query';
export const queryClient = new QueryClient();
```

**`src/app/theme.ts`**

```ts
import { createTheme } from '@mui/material/styles';

export const theme = createTheme({
  palette: { mode: 'light' },
  shape: { borderRadius: 16 },
  typography: { fontFamily: ['Inter', 'system-ui', 'Arial', 'sans-serif'].join(',') },
});
```

**`src/main.tsx`** (adapt to your existing TanStack Router root)

```tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from '@/app/queryClient';
import { ThemeProvider, CssBaseline } from '@mui/material';
import { theme } from '@/app/theme';
import { RouterProvider, createRootRoute, createRouter } from '@tanstack/react-router';
import ChartsRoute from '@/routes/charts.route';
import '@/index.css';

const rootRoute = createRootRoute({
  component: () => <div className="min-h-screen bg-neutral-100"><CssBaseline /><Outlet /></div>,
});
const chartsRoute = new (class extends (rootRoute.addChildren as any) {})();

const routeTree = rootRoute.addChildren([
  chartsRoute.createRoute({
    path: '/',
    component: ChartsRoute,
  }),
]);

const router = createRouter({ routeTree });

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider theme={theme}>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </ThemeProvider>
  </React.StrictMode>,
);
```

> If your scaffold already has a router tree, just register `charts.route.tsx` at `/charts` and link from Home.

---

## How this ties to your flow

* **Upload CSV** or **type a query** → `DataSourcePanel` creates DataFrames and mocked `ChartPayload[]`.
* DataFrames are stored in a simple `window.__DF_STORE__` (replace with your state/store later).
* **Table** uses TanStack Table to render the active DataFrame.
* **Charts** uses a **library-agnostic payload** and a **renderer registry**. Today: Chart.js. Tomorrow: drop in Plotly/ECharts renderers by adding new adapters + entries in `chartRegistry.ts`.
* **Spec-driven**: The adapter translates your `ChartSpec` to the target lib’s API. When your NL API returns `charts: ChartPayload[]`, the pane renders them all.

---

