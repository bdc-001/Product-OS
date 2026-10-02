/**
 * Raw light and dark palettes. Components read `apple`, `pmm` and `accent`, which resolve through CSS
 * variables, so a colour written once follows the active colour scheme. Theme palettes (which MUI
 * must parse) use the raw values.
 */
export const lightPalette = {
  page: "#ffffff",
  raised: "#ffffff",
  wash: "rgba(118, 118, 128, 0.12)",
  nav: "#f8f9fb",
  text: "#1d1d1f",
  muted: "#646b76",
  hairline: "#e1e4e8",
  hairlineHover: "#c9cbd1",
  ink: "#1d1d1f",
  inkHover: "#000000",
  onInk: "#ffffff",
  selFill: "rgba(0,0,0,0.04)",
  hoverFill: "#f5f5f7",
  danger: "#b80000",
  dangerFill: "#fff2f2",
  dangerLine: "rgba(184,0,0,0.25)",
  green: "#157347",
  greenFill: "#edf8f1",
  greenLine: "#c7e7d2",
  amber: "#986313",
  amberFill: "#fff6e5",
  amberLine: "#ecd9b2",
  slate: "#394150",
  slateFill: "#f2f4f7",
  shadow: "0 1px 2px rgba(16,24,40,0.03)",
  shadowHover: "0 4px 12px rgba(0,0,0,0.06), 0 14px 32px rgba(0,0,0,0.08)",
  shadowRaised: "0 6px 16px rgba(0,0,0,0.07), 0 22px 55px rgba(0,0,0,0.11)",
  focusRing: "0 0 0 3px rgba(0,0,0,0.12)",
  accentSystem: "#5b5bd6",
  accentSystemFill: "#f0f0ff",
  accentProduct: "#0b6bcb",
  accentProductFill: "#eaf3fd",
  accentMarketing: "#d6409f",
  accentMarketingFill: "#fdf0f8",
  accentKnowledge: "#12a594",
  accentKnowledgeFill: "#e9f8f5",
} as const;

export type PaletteKey = keyof typeof lightPalette;

export const darkPalette: Record<PaletteKey, string> = {
  page: "#0e1013",
  raised: "#15181d",
  wash: "rgba(140, 146, 160, 0.18)",
  nav: "#121418",
  text: "#eef0f3",
  muted: "#9ba3af",
  hairline: "#262a31",
  hairlineHover: "#3a3f48",
  ink: "#eef0f3",
  inkHover: "#ffffff",
  onInk: "#0e1013",
  selFill: "rgba(255,255,255,0.06)",
  hoverFill: "#1a1d23",
  danger: "#ff7a7a",
  dangerFill: "rgba(255,122,122,0.12)",
  dangerLine: "rgba(255,122,122,0.35)",
  green: "#4cc38a",
  greenFill: "rgba(76,195,138,0.12)",
  greenLine: "rgba(76,195,138,0.35)",
  amber: "#f1b45a",
  amberFill: "rgba(241,180,90,0.12)",
  amberLine: "rgba(241,180,90,0.35)",
  slate: "#c4cad4",
  slateFill: "#1b1f26",
  shadow: "0 1px 2px rgba(0,0,0,0.4)",
  shadowHover: "0 4px 12px rgba(0,0,0,0.35), 0 14px 32px rgba(0,0,0,0.4)",
  shadowRaised: "0 6px 16px rgba(0,0,0,0.45), 0 22px 55px rgba(0,0,0,0.5)",
  focusRing: "0 0 0 3px rgba(255,255,255,0.18)",
  accentSystem: "#9b9ef0",
  accentSystemFill: "rgba(155,158,240,0.14)",
  accentProduct: "#6cb4f7",
  accentProductFill: "rgba(108,180,247,0.14)",
  accentMarketing: "#f07fc4",
  accentMarketingFill: "rgba(240,127,196,0.14)",
  accentKnowledge: "#4fd1bf",
  accentKnowledgeFill: "rgba(79,209,191,0.14)",
};

const varName = (key: string) => `--${key.replace(/[A-Z]/g, (char) => `-${char.toLowerCase()}`)}`;
const ref = (key: PaletteKey) => `var(${varName(key)})`;

/** `{"--page": "#fff", …}` for one palette; the theme writes these for `:root` and `:root.dark`. */
export function paletteVars(palette: Record<PaletteKey, string>): Record<string, string> {
  return Object.fromEntries(Object.entries(palette).map(([key, value]) => [varName(key), value]));
}

const pop = "cubic-bezier(0.2, 0, 0, 1)";
const smooth = "cubic-bezier(0.32, 0.72, 0, 1)";

/** Product chrome. Do not use `pmm` here. */
export const apple = {
  page: ref("page"),
  raised: ref("raised"),
  wash: ref("wash"),
  nav: ref("nav"),
  text: ref("text"),
  muted: ref("muted"),
  hairline: ref("hairline"),
  hairlineHover: ref("hairlineHover"),
  ink: ref("ink"),
  inkHover: ref("inkHover"),
  onInk: ref("onInk"),
  selFill: ref("selFill"),
  hoverFill: ref("hoverFill"),
  danger: ref("danger"),
  dangerFill: ref("dangerFill"),
  dangerLine: ref("dangerLine"),
  done: ref("ink"),
  pop,
  smooth,
  shadow: ref("shadow"),
  /** @deprecated use ink — kept so leftover references stay monochrome */
  blue: ref("ink"),
  blueHover: ref("inkHover"),
} as const;

/** Semantic statuses shared across modules. */
export const pmm = {
  blue: ref("ink"),
  blueDeep: ref("slate"),
  green: ref("green"),
  amber: ref("amber"),
  blueFill: ref("slateFill"),
  greenFill: ref("greenFill"),
  amberFill: ref("amberFill"),
  greenLine: ref("greenLine"),
  amberLine: ref("amberLine"),
  muted: ref("muted"),
  mutedFill: ref("hoverFill"),
} as const;

export type Category = "system" | "product" | "marketing" | "knowledge";

/** One expressive accent per pipeline category: navigation dots, catalog cards, run progress. */
export const accent: Record<Category, { main: string; fill: string; label: string }> = {
  system: { main: ref("accentSystem"), fill: ref("accentSystemFill"), label: "Platform" },
  product: { main: ref("accentProduct"), fill: ref("accentProductFill"), label: "Product" },
  marketing: { main: ref("accentMarketing"), fill: ref("accentMarketingFill"), label: "Marketing" },
  knowledge: { main: ref("accentKnowledge"), fill: ref("accentKnowledgeFill"), label: "Knowledge" },
};

export function categoryAccent(category?: string) {
  return accent[(category as Category) in accent ? (category as Category) : "system"];
}

export const space = {
  2: 2,
  4: 4,
  6: 6,
  8: 8,
  10: 10,
  12: 12,
  14: 14,
  16: 16,
  18: 18,
  20: 20,
  22: 22,
  24: 24,
  28: 28,
  32: 32,
  40: 40,
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 28,
} as const;

export const radius = {
  7: 7,
  9: 9,
  12: 12,
  14: 14,
  16: 16,
  18: 18,
  22: 22,
  xs: 7,
  sm: 9,
  md: 8,
  lg: 10,
  xl: 12,
  card: 12,
  sheet: 16,
  pill: 999,
} as const;

export const typeScale = {
  display: { fontSize: 32, fontWeight: 600, letterSpacing: "-0.035em", lineHeight: 1.08 },
  title: { fontSize: 21, fontWeight: 600, letterSpacing: "-0.022em", lineHeight: 1.25 },
  heading: { fontSize: 17, fontWeight: 600, letterSpacing: "-0.02em", lineHeight: 1.3 },
  body: { fontSize: 15, lineHeight: 1.47 },
  bodySm: { fontSize: 14, lineHeight: 1.47 },
  caption: { fontSize: 13, lineHeight: 1.4 },
  micro: { fontSize: 12 },
  tiny: { fontSize: 11 },
} as const;

export const motion = {
  pop,
  smooth,
} as const;

export const shadow = {
  rest: ref("shadow"),
  hover: ref("shadowHover"),
  raised: ref("shadowRaised"),
  focus: ref("focusRing"),
  switch: "0 1px 3px rgba(0,0,0,0.25)",
} as const;

export const fontFamily = [
  "-apple-system",
  "BlinkMacSystemFont",
  '"SF Pro Text"',
  '"SF Pro Display"',
  '"Segoe UI"',
  "var(--font-inter)",
  "sans-serif",
].join(", ");
