love this stack — you’ve got all the pieces for a fast, composable “server-state first” app. here’s a crisp design you can drop in.

# architecture sketch (data flow)

* **Vite + React Router + TanStack Query (v5)** for UI + server-state cache.
* **Express** as your single frontend origin:

  * terminates auth (httpOnly cookie session/JWT), CSRF.
  * proxies to **FastAPI** (analytics/business endpoints).
  * exposes **Firestore CRUD** for comments/notifications via Admin SDK.
  * optional **SSE/WebSocket** fan-out for real-time (bridges Firestore change streams).
* **Firestore** for collaboration primitives (comments, notifications).

# query key scheme (server-state map)

* Dashboard shell/spec: `['dashboard', dashboardId]`
* Widgets configuration list: `['widgets', dashboardId]`
* Widget data (paramized): `['widgetData', { dashboardId, widgetId, paramsHash }]`
* Comments per entity: `['comments', { entityType, entityId, page? }]`
* Notifications feed: `['notifications', userId]`

# rules of engagement (React Query)

* **staleness**: long for structural data (spec, widgets), short for volatile (metrics, comments).

  * `['dashboard', id]`: `staleTime: 5 * 60_000`
  * `['widgets', id]`: `staleTime: 5 * 60_000`
  * `['widgetData', …]`: `staleTime: 5_000` (dashboards feel live)
* **prefetch on route** to avoid waterfalls; widgets fetch in parallel after spec loads.
* **optimistic mutations** for comments/notifications.
* **realtime**: SSE → `queryClient.setQueryData`/`invalidateQueries` by key.
* **batching**: if multiple widgets read overlapping datasets, backends expose a **multiquery** endpoint to minimize N+1.

---

# backend slices

## express (auth + proxy + firestore + sse)

```ts
// server/app.ts
import express from 'express';
import cors from 'cors';
import cookieParser from 'cookie-parser';
import { initializeApp, cert } from 'firebase-admin/app';
import { getFirestore } from 'firebase-admin/firestore';

initializeApp({ credential: cert(JSON.parse(process.env.GCP_SA!)) });
const db = getFirestore();

const app = express();
app.use(cors({ origin: 'http://localhost:5173', credentials: true }));
app.use(cookieParser());
app.use(express.json());

// simple auth gate (replace with real verify)
app.use((req, res, next) => {
  const sid = req.cookies['sid'];
  if (!sid) return res.status(401).json({ error: 'unauthorized' });
  (req as any).userId = 'u_' + sid.slice(0, 6);
  next();
});

// proxy to FastAPI (analytics)
import { createProxyMiddleware } from 'http-proxy-middleware';
app.use('/api', createProxyMiddleware({
  target: 'http://localhost:8000',
  changeOrigin: true,
  pathRewrite: { '^/api': '' },
}));

// firestore: comments
app.get('/comments/:entityType/:entityId', async (req, res) => {
  const { entityType, entityId } = req.params;
  const snap = await db.collection('comments')
    .where('entityType', '==', entityType)
    .where('entityId', '==', entityId)
    .orderBy('createdAt', 'desc')
    .limit(Number(req.query.limit ?? 20)).get();
  res.json(snap.docs.map(d => ({ id: d.id, ...d.data() })));
});

app.post('/comments/:entityType/:entityId', async (req, res) => {
  const { entityType, entityId } = req.params;
  const doc = await db.collection('comments').add({
    entityType, entityId,
    text: String(req.body.text ?? ''),
    authorId: (req as any).userId,
    createdAt: Date.now(),
  });
  res.status(201).json({ id: doc.id });
});

// firestore: notifications (read + ack)
app.get('/notifications', async (req, res) => {
  const uid = (req as any).userId;
  const q = await db.collection('notifications')
    .where('userId', '==', uid)
    .orderBy('createdAt', 'desc')
    .limit(25).get();
  res.json(q.docs.map(d => ({ id: d.id, ...d.data() })));
});
app.post('/notifications/:id/ack', async (req, res) => {
  await db.collection('notifications').doc(req.params.id).update({ read: true });
  res.status(204).end();
});

// SSE for realtime (push new comments/notifications)
app.get('/events', async (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.flushHeaders();

  const uid = (req as any).userId;

  const notifUnsub = db.collection('notifications')
    .where('userId', '==', uid)
    .orderBy('createdAt', 'desc')
    .limit(1)
    .onSnapshot(snap => {
      for (const d of snap.docChanges().filter(c => c.type === 'added')) {
        res.write(`event: notification\n`);
        res.write(`data: ${JSON.stringify({ id: d.doc.id, ...d.doc.data() })}\n\n`);
      }
    });

  // (Optional) comments stream by entity; in practice, mount per entity or filter on client
  const commentsUnsub = db.collection('comments')
    .orderBy('createdAt', 'desc')
    .limit(1)
    .onSnapshot(snap => {
      for (const d of snap.docChanges().filter(c => c.type === 'added')) {
        res.write(`event: comment\n`);
        res.write(`data: ${JSON.stringify({ id: d.doc.id, ...d.doc.data() })}\n\n`);
      }
    });

  req.on('close', () => { notifUnsub(); commentsUnsub(); res.end(); });
});

app.listen(4000, () => console.log('Express on :4000'));
```

---

# frontend integration (vite + react router + tanstack query)

## fetch wrapper (auth via httpOnly cookie + CSRF)

```ts
// src/http.ts
export async function api(path: string, init?: RequestInit) {
  const res = await fetch(path, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    ...init
  });
  if (!res.ok) throw new Error(await res.text());
  return res.headers.get('content-type')?.includes('application/json') ? res.json() : res.text();
}
```

## query client & router providers

```tsx
// src/main.tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import DashboardRoute, { dashboardLoader } from './routes/DashboardRoute';

const qc = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      refetchOnWindowFocus: true,
      gcTime: 5 * 60_000,
    },
  },
});

const router = createBrowserRouter([
  { path: '/dashboards/:dashboardId', element: <DashboardRoute />,
    loader: (args) => dashboardLoader(qc, args) }
]);

ReactDOM.createRoot(document.getElementById('root')!).render(
  <QueryClientProvider client={qc}>
    <RouterProvider router={router} />
    <ReactQueryDevtools />
  </QueryClientProvider>
);
```

## route loader: prefetch shell + widgets

```tsx
// src/routes/DashboardRoute.tsx
import * as React from 'react';
import { LoaderFunctionArgs, useParams } from 'react-router-dom';
import { QueryClient, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../http';

type DashboardSpec = { id: string; title: string; widgets: Array<{ id: string; type: string; params: any }> };

export async function fetchDashboard(id: string): Promise<DashboardSpec> {
  return api(`/api/dashboards/${id}`);
}
export async function fetchWidgetData(widgetId: string, params: any): Promise<any> {
  return api(`/api/widgets/${widgetId}/data`, { method: 'POST', body: JSON.stringify(params) });
}

export async function dashboardLoader(qc: QueryClient, { params }: LoaderFunctionArgs) {
  const id = params.dashboardId!;
  await qc.ensureQueryData({ queryKey: ['dashboard', id], queryFn: () => fetchDashboard(id), staleTime: 5 * 60_000 });
  // prewarm widget configs (data still fetched in components)
  const spec = qc.getQueryData<DashboardSpec>(['dashboard', id])!;
  (spec.widgets ?? []).forEach(w =>
    qc.prefetchQuery({
      queryKey: ['widgetData', { dashboardId: id, widgetId: w.id, paramsHash: JSON.stringify(w.params) }],
      // only prefetch cheap/critical widgets if desired
      queryFn: () => fetchWidgetData(w.id, w.params),
      staleTime: 5_000
    })
  );
  return null;
}

export default function DashboardRoute() {
  const { dashboardId } = useParams();
  const qc = useQueryClient();

  const specQ = useQuery({
    queryKey: ['dashboard', dashboardId],
    queryFn: () => fetchDashboard(dashboardId!),
    staleTime: 5 * 60_000,
  });

  if (specQ.isLoading) return <p>Loading dashboard…</p>;
  if (specQ.isError)   return <p style={{color:'crimson'}}>{(specQ.error as Error).message}</p>;

  return (
    <div style={{ padding: 16 }}>
      <h1>{specQ.data!.title}</h1>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(12, 1fr)', gap: 12 }}>
        {specQ.data!.widgets.map(w => (
          <Widget key={w.id} dashboardId={specQ.data!.id} widget={w}/>
        ))}
      </div>
    </div>
  );
}

// Widget renderer (parallel data)
function Widget({ dashboardId, widget }: { dashboardId: string, widget: { id: string; type: string; params: any } }) {
  const dataQ = useQuery({
    queryKey: ['widgetData', { dashboardId, widgetId: widget.id, paramsHash: JSON.stringify(widget.params) }],
    queryFn: () => fetchWidgetData(widget.id, widget.params),
    staleTime: 5_000,
    // avoid thrash when params change rapidly
    keepPreviousData: true,
  });

  return (
    <section style={{ border:'1px solid #ddd', borderRadius:8, padding:12, gridColumn: 'span 6' }}>
      <header style={{ display:'flex', justifyContent:'space-between' }}>
        <strong>{widget.type}</strong>
      </header>
      {dataQ.isLoading ? <p>Loading…</p> :
       dataQ.isError ? <p style={{color:'crimson'}}>{(dataQ.error as Error).message}</p> :
       <pre style={{whiteSpace:'pre-wrap'}}>{JSON.stringify(dataQ.data, null, 2)}</pre>}
      <Comments entityType="widget" entityId={widget.id}/>
    </section>
  );
}
```

## comments (firestore via express) with optimistic UX + SSE live updates

```tsx
// src/comments.tsx
import * as React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from './http';

type Comment = { id: string; text: string; authorId: string; entityType: string; entityId: string; createdAt: number };

function listComments(entityType: string, entityId: string): Promise<Comment[]> {
  return api(`/comments/${entityType}/${entityId}`);
}
function createComment(entityType: string, entityId: string, text: string): Promise<{id: string}> {
  return api(`/comments/${entityType}/${entityId}`, { method: 'POST', body: JSON.stringify({ text }) });
}

export function Comments({ entityType, entityId }: { entityType: string; entityId: string }) {
  const qc = useQueryClient();
  const key = ['comments', { entityType, entityId }];

  const q = useQuery({
    queryKey: key,
    queryFn: () => listComments(entityType, entityId),
    staleTime: 10_000,
  });

  const m = useMutation({
    mutationFn: (text: string) => createComment(entityType, entityId, text),
    onMutate: async (text) => {
      await qc.cancelQueries({ queryKey: key });
      const prev = qc.getQueryData<Comment[]>(key) ?? [];
      const optimistic: Comment = {
        id: `tmp-${Date.now()}`, text, authorId: 'me', entityType, entityId, createdAt: Date.now()
      };
      qc.setQueryData<Comment[]>(key, [optimistic, ...prev]);
      return { prev };
    },
    onError: (_e, _vars, ctx) => ctx?.prev && qc.setQueryData(key, ctx.prev),
    onSettled: () => qc.invalidateQueries({ queryKey: key }),
  });

  // Realtime (SSE). Debounce to avoid burst invalidations.
  React.useEffect(() => {
    const es = new EventSource('/events', { withCredentials: true });
    const handler = (ev: MessageEvent) => {
      const data = JSON.parse(ev.data) as Comment;
      if (data.entityType === entityType && data.entityId === entityId) {
        // insert new comment if not present
        const existing = q.data ?? [];
        const dup = existing.some(c => c.id === data.id);
        if (!dup) {
          qc.setQueryData<Comment[]>(key, [data, ...(existing || [])]);
        }
      }
    };
    es.addEventListener('comment', handler as any);
    return () => es.close();
  }, [entityType, entityId]);

  const [text, setText] = React.useState('');
  return (
    <div style={{ marginTop: 8 }}>
      <form onSubmit={e => { e.preventDefault(); if (text.trim()) m.mutate(text.trim(), { onSuccess: () => setText('') }); }}
            style={{ display:'flex', gap:8 }}>
        <input value={text} onChange={e => setText(e.target.value)} placeholder="Add comment…" style={{ flex:1 }}/>
        <button disabled={m.isPending}>Post</button>
      </form>
      <ul style={{ listStyle:'none', padding:0, marginTop:8 }}>
        {(q.data ?? []).map(c => (
          <li key={c.id} style={{ opacity: c.id.startsWith('tmp-') ? 0.6 : 1 }}>
            <small>{new Date(c.createdAt).toLocaleString()}</small>
            <div>{c.text}</div>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

## notifications (polling → SSE upgrade)

```tsx
// src/notifications.ts
import { useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './http';

export function useNotifications(userId: string) {
  const qc = useQueryClient();
  const key = ['notifications', userId];

  const q = useQuery({
    queryKey: key,
    queryFn: () => api('/notifications'),
    // fallback polling for environments without SSE (e.g., corporate proxies)
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  useEffect(() => {
    const es = new EventSource('/events', { withCredentials: true });
    const onNotif = (ev: MessageEvent) => {
      const notif = JSON.parse(ev.data);
      const prev = (qc.getQueryData<any[]>(key) ?? []);
      qc.setQueryData(key, [notif, ...prev]);
    };
    es.addEventListener('notification', onNotif as any);
    return () => es.close();
  }, [userId]);

  return q;
}
```

---

# widget data strategies (avoid waterfalls & overfetch)

1. **parallelize**: each widget uses its own key and fetch; router loader only ensures the spec is there so widgets can mount immediately.
2. **coalesce**: add a FastAPI `POST /widgets/data:batch` that accepts `[{widgetId, params}]` and returns a map. Then use **one** query per dashboard:

   * key: `['dashboardData', { dashboardId, specHash }]`
   * inside each widget, `select` to carve its slice to avoid extra requests.
3. **invalidate by scope**: when dashboard param changes, call

   ```ts
   qc.invalidateQueries({ predicate: q => q.queryKey[0] === 'widgetData' && q.queryKey[1]?.dashboardId === dashboardId })
   ```

   to refresh all widgets at once.

---

# defaults that work well

* **errors**: surfacing per-widget is fine; for global outages, add a toast boundary on `onError` in `defaultOptions.queries`.
* **loading UX**: `keepPreviousData: true` for smooth metric changes.
* **stale/focus**: keep `refetchOnWindowFocus` on for operator dashboards; turn off for static reporting pages.
* **persist** (optional offline/read-only): `@tanstack/query-persist-client` with localStorage/IDB.

---

# security & ops notes

* **httpOnly cookies** + **SameSite=Lax/Strict**; add a CSRF header for non-GET. Your `api()` wrapper can auto-inject it from a cookie meta tag.
* **rate limits** at Express (per session) for comment spam.
* **CORS**: `credentials: true` and explicit origin.
* **observability**: tag each query with `meta: { feature: 'dashboard', widgetId }` and log timing server-side; mirror keys in server logs.

---

# where React Query earns its keep here

* no `useEffect` fetch spaghetti in every widget.
* clean cache boundaries (`dashboard` vs `widgets` vs `widgetData`).
* optimistic collaboration flows (comments) with rollback.
* unified refresh semantics across REST (FastAPI) and Firestore (via Express).

If you want, I can also sketch the FastAPI side (batch widget endpoint + caching headers) and a compact ERD for Firestore collections (comments, notifications, subscriptions) to round this out.
