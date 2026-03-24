---
globs: ["web/**/*.tsx", "web/**/*.ts"]
---

# Frontend Rules

- **React 19** with TypeScript strict mode.
- **Vite** for build tooling. **Tailwind v4** for styling.
- No class components — functional components with hooks only.
- API calls go through the `src/api/` client layer, not inline `fetch`.
- All async state uses React Query (or equivalent) — no raw `useEffect` for data fetching.
- Run `tsc --noEmit` before committing to catch type errors.
- `web/` is a standalone Vite workspace — run `pnpm install` / `pnpm dev` from `web/`.
