# Kutana AI Design System

## Palette — Signal Green + Charcoal

The design language is inspired by dev-tools brands (Vercel dark, Supabase green) — a futuristic, terminal-native feel that reads "go, active, connected."

### Brand Colors (Signal Green / Emerald)

| Token | Value | Usage |
|---|---|---|
| `brand-500` | `#10B981` | Primary — buttons, active states, focus rings |
| `brand-400` | `#34d399` | Text accent — links, labels, badges |
| `brand-600` | `#059669` | Hover, pressed states |
| `brand-300` | `#6ee7b7` | Light accent on dark backgrounds |
| `brand-900` | `#064e3b` | Subtle tint backgrounds |
| `brand-950` | `#022c22` | Deepest tint |

### Surface Colors (Zinc / Charcoal)

In dark mode `gray-950` is the darkest background; in light mode the scale inverts.

| Token (dark) | Value | Light mode value | Usage |
|---|---|---|---|
| `gray-950` | `#09090b` | `#fafafa` | Page background |
| `gray-900` | `#18181b` | `#f4f4f5` | Card / sidebar surface |
| `gray-800` | `#27272a` | `#e4e4e7` | Borders, elevated surface |
| `gray-700` | `#3f3f46` | `#d4d4d8` | Hover border, scrollbar |
| `gray-500` | `#71717a` | `#71717a` | Muted text (unchanged) |
| `gray-400` | `#a1a1aa` | `#52525b` | Secondary text |
| `gray-200` | `#e4e4e7` | `#27272a` | Body text |
| `gray-50`  | `#fafafa`  | `#09090b` | Primary headings (via `text-gray-50`) |

> **Key mechanic:** `html[data-theme="light"]` overrides `--color-gray-*` CSS variables so the scale flips. All Tailwind `gray-*` classes adapt automatically.

### Semantic Colors

| Role | Token | Value |
|---|---|---|
| Success | `success-500` | `#10b981` (same as brand) |
| Error | `danger-500` | `#ef4444` |
| Warning | `warning-500` | `#f59e0b` |
| Info | `info-500` | `#06b6d4` |

---

## Typography

- **Sans:** Inter → fallback: system-ui
- **Mono:** JetBrains Mono → Fira Code → ui-monospace

No changes from the previous system. Font feature settings: `cv02 cv03 cv04 cv11` (Inter ligatures + alternate digits).

---

## Custom Utilities

Defined in `web/src/index.css`:

| Class | Effect |
|---|---|
| `bg-gradient-brand` | `135deg, #34d399 → #059669` — used on avatar, logo bg |
| `bg-gradient-brand-subtle` | Same gradient at low opacity |
| `bg-ambient-brand` | Radial green glow ellipse at page top — applied to `<main>` |
| `shadow-glow-brand` | Green glow ring — dialogs, logo on auth pages |
| `shadow-glow-brand-sm` | Smaller glow — button hover |
| `card-interactive` | Hover: green border tint + lift |
| `text-gradient-brand` | `#6ee7b7 → #10b981` text gradient |
| `code-block` | Monospace block using CSS variables |

---

## Light / Dark Mode

### How it works

1. `ThemeProvider` (`web/src/contexts/ThemeContext.tsx`) reads `localStorage("kutana-theme")` and OS preference on first load.
2. It sets `document.documentElement.setAttribute("data-theme", theme)`.
3. `html[data-theme="light"]` in `index.css` flips the `--color-gray-*` and `--color-ink-*` CSS variables.
4. Because `@layer theme` rules lose to unlayered rules in CSS cascade, the light mode overrides always take effect without specificity hacks.

### Toggle

The `Layout` sidebar has a sun/moon button that calls `useTheme().toggleTheme()`. Preference is persisted to `localStorage`.

### `text-gray-50` vs `text-white`

- Use `text-gray-50` for headings and primary text — it inverts to near-black in light mode.
- Keep `text-white` only for text on colored backgrounds (e.g. button labels, avatar initials).

---

## Google Stitch — Design Token Management

[Google Stitch](https://stitch.withgoogle.com) is Google's AI design tool for generating UI screens and extracting design systems from prompts or URLs.

### What it provides

- **`DESIGN.md`** — a portable markdown file encoding the color palette, typography, spacing, and layout rules for this project.
- **MCP server** — exposes Stitch tools to Claude Code and other AI agents.
- **Agent Skills library** (`google-labs-code/stitch-skills`) — pre-built prompts for design-to-code workflows.

### MCP Configuration

The project `.mcp.json` configures the Stitch MCP server for Claude Code:

```json
{
  "mcpServers": {
    "google-stitch": {
      "command": "npx",
      "args": ["-y", "@google/stitch-sdk@latest", "mcp"]
    }
  }
}
```

> **Setup:** Log in at [stitch.withgoogle.com](https://stitch.withgoogle.com) once. The SDK uses your browser session — no API key required.

### Generating a `DESIGN.md`

Once the MCP server is running in Claude Code, you can ask:

> "Use Google Stitch to extract the design system from our app and write a DESIGN.md."

This creates a machine-readable file at `DESIGN.md` that agents can reference to stay on-brand when generating new UI.

### Updating the palette in Stitch

1. Open Stitch, create or open a project
2. Update colors to match the Signal Green + Charcoal palette above
3. Export `DESIGN.md` and commit it to the repo root
4. Reference `DESIGN.md` in prompts: "Follow the palette in DESIGN.md"

---

## Environment Variables

No additional environment variables are required for the design system itself. Google Stitch uses browser-based auth.

If using the Stitch API programmatically in the future:

| Variable | Purpose |
|---|---|
| `STITCH_API_KEY` | (optional) Service account key for CI/CD token generation |
| `STITCH_PROJECT_ID` | (optional) Pin to a specific Stitch project |
