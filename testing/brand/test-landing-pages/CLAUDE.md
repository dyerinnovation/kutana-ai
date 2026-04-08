# Landing Page Mocks

Self-contained HTML prototypes for the Kutana landing page. Each version is a complete standalone page (no build step required) used to iterate on design, layout, and animation before porting changes into the React app.

## Current Version

`kutanalandingpagev22.html` — the latest mock. Use this as the reference when comparing to the deployed landing page.

**IMPORTANT:** When you create a new version, update this file to reflect the new current version number. Other agents rely on this to know which mock is latest.

## Workflow

1. CoWork (or manual iteration) produces a new `kutanalandingpagev{N}.html` when design issues are found
2. Serve locally: `python3 -m http.server 8089` from this directory, then open `http://localhost:8089/kutanalandingpagev{N}.html`
3. Compare visually with the deployed landing page at `https://dev.kutana.ai`
4. Once validated, port the changes into the React components under `web/src/components/landing/`
5. **Update this CLAUDE.md** — set the "Current Version" section to point at your new file

## Key Components to Keep in Sync

| Mock Section | React Component |
|---|---|
| Nav bar (K icon + "Kutana AI") | `web/src/components/landing/LandingNav.tsx` |
| Meeting workflow diagram | `web/src/components/landing/MeetingDiagramSection.tsx` |
| Hero section | `web/src/components/landing/HeroSection.tsx` |
| Feeds section | `web/src/components/landing/FeedsSection.tsx` |
| Pricing section | `web/src/components/landing/PricingSection.tsx` |
| Logo mark (K icon) | `web/src/components/Logo.tsx` |

## Notes

- Mocks use vanilla HTML/CSS/JS — no React, no Tailwind, no build tools
- The animated workflow uses JS `mdAlignFlowLines()` to position flow lines at each node's vertical center — the React port should replicate this with refs + useEffect, not static CSS calc
- Brand colors: primary green `#10B981` / `#16A34A`, purple (AI) `#9B30FF`, teal `#14B8A6`
