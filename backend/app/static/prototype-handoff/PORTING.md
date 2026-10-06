# Reproduce this prototype in production

Treat the exported source as the visual specification. Start with `handoff/manifest.json`.
It records source hashes, exact dependencies, CSS inputs, page files, and the source lines
that own geometry. A shared class name is **not** proof of shared dimensions.

## Give the coding LLM this instruction

Implement the selected prototype screen in the existing production application. Preserve
the prototype's DOM structure, widths, spacing, alignment, breakpoints and type metrics.
Read the full page dependency graph, stylesheet, shell and handoff manifest before editing.
Do not redesign or replace precise values with the nearest production utility. Reuse the
compiled scoped CSS described below so production Tailwind cannot reinterpret the classes.
Keep production authentication, authorization, API calls, tenant routing, analytics and
error handling. Replace fixtures with production data at the component boundary. Preserve
loading, empty, long-content and error states. Implement one route first and verify it
against the reference before expanding to other routes. Report measured differences and
unverified states; do not claim pixel parity from successful compilation alone.

## Build the styling contract

From the exported project root, with its prototype dependencies installed:

```sh
node handoff/build-styles.mjs
```

This compiles `src/index.css` (or `src/styles.css` if that is the stylesheet) with the **prototype's Tailwind 4 compiler**, scans its current
source, and emits `handoff/reference.css` and `handoff/production-scoped.css`. It does not
run the app's Vite config or change production. The scoped file contains plain CSS, not
Tailwind directives. Copy it as an asset **after** production's CSS imports; exclude it
from Tailwind/PostCSS processing. Do not paste the prototype's Tailwind 4 source into the
production Tailwind 3 pipeline or replace production's global theme.

Set `data-prototype-ui="<prototype_id from manifest>"` on the route's visual root. Keep
copied components, header slots, and overlay portal containers inside a root with this
attribute. Multiple roots may share the attribute. The file scopes selectors, flattens
Tailwind layers, namespaces Tailwind variables/keyframes and converts rem lengths to px
using a 16px reference root. **Verify the reference root first**; use `--root-px=VALUE` if
the prototype changes it. Do not globally change production's html font size.

Portals are part of the layout: Radix Dialog/Popover and Headless UI menus can render into
`document.body`. Configure their portal container beneath the scoped root or apply the
scope attribute to an overlay wrapper. Otherwise they inherit production typography and
lose the copied styling. Preserve overlay position strategy, z-index and scroll locking.

This isolates normal CSS utilities; production inline styles or `!important` rules can
still win. Inspect the computed style when comparison fails. Fonts and referenced public
assets must also be copied/loaded; compiled CSS does not bundle fonts. Preserve the exact
font family, weight and loaded font files from `index.html` and the source stylesheet.

## Assign each dimension to one owner

- **Production Layout:** authentication/permissions, sidebar offset, header, banners, and
  outlet scroll behavior. Preserve its logic. Adapt only the targeted route's visual
  wrappers to the prototype measurements; never replace Layout wholesale.
- **Prototype page:** inner padding, centered/max-width container, toolbar, grid/table,
  cards, row heights and responsive behavior. Do not add a second padded/max-width wrapper.
- **Header:** one header only. If production supplies it, omit the prototype TopBar and
  reproduce its height/padding/search positioning in the existing slot. Removing a header
  without moving those rules changes the page origin and available width.
- **Sidebar:** match expanded/collapsed width and state, including the main content offset.
- **Scrolling:** compare document scroll versus outlet scroll explicitly. A sticky header
  sticks to its nearest scrolling ancestor; moving it changes behavior.

## Measure before calling it complete

1. Open reference and production at the same manifest viewport, browser zoom (100%),
   sidebar state, theme, data fixtures, scrollbar state and loaded font state.
2. Load `handoff/capture-layout.js` in each browser console. Use the same landmark keys
   with selectors appropriate to each DOM. Example:
   `await capturePrototypeLayout({header:'header', sidebar:'aside', content:'[data-layout="content"]', grid:'[data-layout="grid"]', card:'[data-layout="card"]'})`.
   Save the returned JSON as `reference-layout.json` and `production-layout.json`.
   Add stable `data-layout` attributes when a selector is ambiguous. No row/customer text
   or input values are included in these captures.
3. Run `node handoff/compare-layout.mjs reference-layout.json production-layout.json`.
   It fails for missing landmarks, different viewport/root conditions, geometry drift
   over 1px, or different typography/alignment. Intentional production root-size differences
   are allowed because the scoped CSS pins the prototype lengths.
4. Also compare screenshots for colors, shadows, icons, wrapping, open menus/dialogs,
   expanded/collapsed sidebar, mobile navigation, and long/empty/loading/error states.
   A geometry pass does not establish complete visual or behavioral equivalence.

Re-export after prototype edits. `handoff/manifest.json` hashes must match the source you
implement. `verification: unmeasured` means no visual acceptance has been claimed.
