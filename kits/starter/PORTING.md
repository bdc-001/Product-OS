# Starter prototype kit

A neutral product shell for prototypes in workspaces that have not brought their own UI kit.

- `src/App.tsx` holds the routes. Pages live in `src/pages/`, shared pieces in `src/components/`.
- Fixtures live in `src/data/fixtures.ts`. Prototypes never call real APIs.
- Styling is Tailwind v4 with tokens in `src/index.css` (`--color-brand`, `--color-surface`, …). Change the
  tokens to match the workspace brand rather than hardcoding colours in components.
- Routing uses `HashRouter` so a static `vite build` works under any preview path.

To port a prototype into a real product, copy the page component and replace the fixture imports with
the product's data hooks.
