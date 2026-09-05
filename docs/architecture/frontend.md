# Frontend structure

Stack: React 18, TypeScript, Vite, Tailwind CSS, React Router, TanStack Query, Axios, Zustand, Lucide, Leaflet (installed, unused on screen).

## Folders

| Path | Why it exists |
| --- | --- |
| `src/app/` | Shell: `App.tsx`, router, React Query provider |
| `src/pages/` | One folder per route. Pages stay thin. |
| `src/features/` | Feature-specific widgets (Dashboard health card lives here) |
| `src/components/` | Shared UI. Subfolders (`map`, `camera`, …) are reserved. |
| `src/services/` | Axios wrappers. One file per backend domain. |
| `src/stores/` | Zustand: UI state that is awkward in the URL or the server |
| `src/hooks/` | Shared hooks (empty for now) |
| `src/types/` | Shared TypeScript types |
| `src/utils/` | Small helpers |
| `src/assets/` | Images and static imports |

**pages vs features vs components:** a page composes features; a feature may use shared components. Do not put API calls in deep presentational components if you can keep them in `services/` + TanStack Query.

## Talking to Django

`src/services/api.ts` creates Axios with `baseURL` = `import.meta.env.VITE_API_BASE_URL` or `/api`.

Vite proxies `/api` → Django (`vite.config.ts`). The dashboard calls `GET /api/health/` through TanStack Query.

## Zustand vs TanStack Query

- Server state (health, later camera lists) → Query
- Client-only view state (map center, selected investigation id) → Zustand
