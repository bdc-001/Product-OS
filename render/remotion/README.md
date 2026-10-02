# Marketing films

Remotion compositions the Product Marketing pipeline renders. The backend stages narration, scene props and the workspace brand (`brand-logo-dark.svg`, `brand-logo-light.svg`, `brand-mark.svg`) into a per-film `public/` folder, then renders `MarketingFilm` from `src/marketing/index.tsx`.

```bash
npm install
npm run studio
```

`src/marketing/` is the only tracked source. Anything else under `src/` or `public/` is local to an install and git-ignored.
