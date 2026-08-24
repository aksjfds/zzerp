# zzerp frontend

Vue 3 frontend for zzerp v6. Feature code is grouped by business capability under
`src/features/`. Production departments are registered independently under
`src/features/departments/`; the router and post-login default route consume
that registry instead of maintaining separate department lists. Department
capabilities are injected into production pages, so the production feature does
not read the department registry in reverse.

## Main folders

- `src/api`: shared HTTP client, authentication and organization lookups.
- `src/features/departments`: department module metadata, permissions and routes.
- `src/features/production`: production tasks, workbench, work orders and QC progress views.
- `src/features/process-designer`: engineering product, BOM and process-flow editor.
- `src/features/customer-orders`: sales orders and production progress.
- `src/features/admin`: administration and PMC projections.
- `src/permission`: permission constants, route guard and default-route selection.
- `src/shared`: reusable layout, table and read-only process-flow capabilities.

Routes remain lazy-loaded. `vite.config.ts` splits Vue, Element Plus, LogicFlow
and remaining vendor code into cacheable chunks so department growth does not
create one oversized shared bundle.

## Project setup

```sh
pnpm install
```

### Development

```sh
pnpm dev
```

### Type-check and production build

```sh
pnpm build
```
