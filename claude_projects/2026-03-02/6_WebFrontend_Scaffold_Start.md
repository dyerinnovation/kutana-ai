# Plan: Web Frontend Scaffold (React + Vite + Tailwind v4)

## Date: 2026-03-02

## Objective
Create the full React + TypeScript + Vite + Tailwind CSS v4 web frontend for Convene AI. This includes project configuration, API client layer, auth context, UI components, and all pages (Login, Register, Dashboard, Agent CRUD, Meetings).

## Scope
- Project setup: package.json, vite.config.ts, tsconfig.json, index.html, Tailwind v4 CSS
- API client: fetch wrapper with JWT auth, endpoint modules for auth/agents/meetings
- Auth: React context + provider with JWT localStorage persistence
- UI components: Button, Input, Card, Dialog, Layout shell, ProtectedRoute
- Pages: Login, Register, Dashboard, AgentCreate, AgentDetail (most important), Meetings
- Types: User, Agent, AgentKey, KeyCreateResponse, Meeting
- Routing: React Router v7 with protected routes

## File List
1. `web/package.json`
2. `web/vite.config.ts`
3. `web/tsconfig.json`
4. `web/index.html`
5. `web/src/main.tsx`
6. `web/src/vite-env.d.ts`
7. `web/src/index.css`
8. `web/src/App.tsx`
9. `web/src/api/client.ts`
10. `web/src/api/auth.ts`
11. `web/src/api/agents.ts`
12. `web/src/api/meetings.ts`
13. `web/src/hooks/useAuth.tsx`
14. `web/src/lib/utils.ts`
15. `web/src/types/index.ts`
16. `web/src/components/ui/Button.tsx`
17. `web/src/components/ui/Input.tsx`
18. `web/src/components/ui/Card.tsx`
19. `web/src/components/ui/Dialog.tsx`
20. `web/src/components/Layout.tsx`
21. `web/src/components/ProtectedRoute.tsx`
22. `web/src/pages/LoginPage.tsx`
23. `web/src/pages/RegisterPage.tsx`
24. `web/src/pages/DashboardPage.tsx`
25. `web/src/pages/AgentCreatePage.tsx`
26. `web/src/pages/AgentDetailPage.tsx`
27. `web/src/pages/MeetingsPage.tsx`

## Key Decisions
- Tailwind v4: No tailwind.config.js needed, just `@import "tailwindcss";` in CSS
- No shadcn/ui CLI (requires interactive setup) - manual component creation
- Dark theme: bg-gray-950 base, subtle borders, white text
- React Router v7 (BrowserRouter)
- JWT stored in localStorage, sent as Bearer token
- AgentDetailPage is the most important page (MCP config snippet)

## Dependencies on Backend
- All API endpoints under /api/v1/ are already implemented
- Vite dev proxy will forward /api to localhost:8000
