# PM Platform frontend design system

Two visual languages. Product chrome is Apple ink. Product Marketing (`/marketing`) keeps the Convin blue / green / amber sheet language. Copilot keeps its CSS grid chat shell in `frontend/app/globals.css` — do not wrap it in `PageBody`.

There is no Storybook. The source of truth is `frontend/app/ui/tokens.ts`, the MUI theme in `frontend/app/theme.ts`, and the kit in `frontend/app/ui/kit.tsx`. Browse the unlisted gallery at `/design` (not in product nav).

## Languages

| Surface | Palette | Buttons |
|---|---|---|
| Shell, Pulse, Jira, Cliq, Codebase, Prototype (PM chrome), Copilot, Notes, LMS, Roadmap | `apple` ink (`#1d1d1f`) | `PillButton` |
| `/marketing` mastersheet | `pmm` (`#1A62F2` / green / amber) | Keep MUI `Button` — do not restyle to ink |
| Copilot chat | Copilot CSS classes | Existing Copilot controls |

`success.main` stays ink. `apple.blue` is deprecated and equals ink.

## Tokens

Import from `@/app/ui/tokens` (also re-exported from `@/app/theme` and `@/app/ui`).

| Token | Use |
|---|---|
| `apple` | Page, wash, nav, text, muted, hairline, ink, fills, danger |
| `space` | 2–40 plus `xs` / `sm` / `md` / `lg` / `xl` / `xxl` |
| `radius` | 7 / 9 / 12 / 14 / 16 / 18 / 22 / `pill` |
| `typeScale` | display 44, title 21, heading 17, body 17/15, caption 13 |
| `motion` | `pop`, `smooth` (respect `prefers-reduced-motion`) |
| `shadow` | `rest`, `hover`, `raised`, `focus` |
| `pmm` | Marketing sheet only |

Named CSS variables on `:root` still match `apple` (`--ink`, `--hairline`, `--pop`, …). Prefer tokens in `sx` over new hex values.

## Kit

Use these instead of copying layout classes or raw MUI chrome:

- Layout: `PageBody`, `PageHeader`, `ModuleIntro`, `KnowledgeSplit` / `KnowledgeList`, `Section`, `SubSection`
- Surfaces: `FrostCard`, `ListRow`, `Banner`, `EmptyState`, `LoadingBlock`, `MarkdownBlock`
- Actions: `PillButton`, `RemoveButton`, `Segmented`, `StatusChip`, `TicketLink`
- Overlays: `AppDialog`, `SideDrawer`
- Status: `QuietDot`, `ConnectionDots`
- Lists: `PagedList`

Do **not** introduce a new `Button` look on product pages. Use `PillButton` (`filled` / `gray` / `text`).

Raw MUI `Dialog`, `Drawer`, `Accordion`, `Tabs`, `LinearProgress`, and `Skeleton` inherit ink `styleOverrides` when a kit wrapper is not in place.

## Exceptions

- Copilot: CSS grid shell, not `PageBody`.
- Product Marketing: `pmm` tokens and existing contained blue buttons. Do not flatten to ink.
- Prototype (`/prototype`): the session list stays Apple ink / kit. The studio itself is Lovable-shaped — chat + prompt on the left, live Sense frontend filling the canvas, code only in a Preview / Code tab. Pulse is hidden on `/prototype/:id` so the canvas is the product, not the PM chrome. The iframe and zip reconstruct Sense with the Lovable product design (`#f6f8fb` sidebar, Main / AI / Human, white top bar with title + moon + bell + avatar, 4px controls, campaign/agent cards, Agent Training) from `frontend/app/prototype/sense-preview.css`, written in Sense-style JSX. Do not flatten that preview to MUI ink, and do not restyle PM chrome to Convin blue.
- Do not invent colors, radii, or motion curves in page `sx`.
