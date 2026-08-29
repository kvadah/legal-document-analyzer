# Frontend — Legal Document Analyzer

Next.js 15 (App Router) · TypeScript (strict) · Tailwind · shadcn/ui · TanStack Query ·
Recharts. See `../../10-frontend-spec.md` for structure/behavior and
`../../02-tech-stack.md` for the stack.

## Layout
```
src/
  app/          App Router routes (added next step)
  components/   shared components; components/ui = shadcn primitives
  lib/          api client, query hooks, utils
  hooks/
  types/
e2e/            Playwright tests
```

## Commands
```bash
pnpm install
pnpm dev          # http://localhost:3000 (needs the app shell — added next step)
pnpm build        # standalone output for Docker
pnpm lint
pnpm type-check
pnpm test         # Vitest unit tests
pnpm test:e2e     # Playwright
```

## Config
Copy `.env.example` → `.env.local`. `NEXT_PUBLIC_API_BASE_URL` points at the backend
(`/api/v1`). Add shadcn/ui components on demand: `pnpm dlx shadcn@latest add <name>`.

> This step ships tooling/config only — there is no `src/app/layout.tsx` or `page.tsx`
> yet, so `pnpm dev` won't render until the nav shell is added (Phase 0, next step).
