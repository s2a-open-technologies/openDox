# openDox Frontend

React 18 + TypeScript SPA (Vite, shadcn/ui, Tailwind CSS). It is part of the
openDox monorepo; see the [root README](../README.md) for the full stack.

```sh
npm install
npm run dev      # dev server on http://localhost:3000, proxies {ROOT_PATH}/api/ to localhost:5000
npm run build    # writes to ../backend/static (not frontend/dist), served by the backend
npm run test     # vitest
npm run lint     # eslint
```

- Path alias `@/` points to `src/`.
- UI strings are never hardcoded: translations live in
  `src/i18n/locales/<lang>/<namespace>.json` (German is the source language).
  See `AGENTS.md` → "i18n" for how to add a language.
- API calls and the WebSocket use `BASE_PATH` from `src/api.ts` (sub-path
  deployments via `ROOT_PATH`).
