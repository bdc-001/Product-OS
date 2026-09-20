/** Product chrome: Apple ink. Do not use `pmm` here. */
export const apple = {
  page: "#ffffff",
  /** Apple system grouped fill — cool translucent grey, not flat warm wash */
  wash: "rgba(118, 118, 128, 0.12)",
  nav: "#fbfbfd",
  text: "#1d1d1f",
  muted: "#86868b",
  hairline: "#d2d2d7",
  hairlineHover: "#c9cbd1",
  ink: "#1d1d1f",
  inkHover: "#000000",
  selFill: "rgba(0,0,0,0.04)",
  hoverFill: "#f5f5f7",
  danger: "#b80000",
  dangerFill: "#fff2f2",
  dangerLine: "rgba(184,0,0,0.25)",
  done: "#1d1d1f",
  pop: "cubic-bezier(0.34, 1.56, 0.64, 1)",
  smooth: "cubic-bezier(0.32, 0.72, 0, 1)",
  shadow: "0 2px 6px rgba(0,0,0,0.06), 0 10px 28px rgba(0,0,0,0.09)",
  /** @deprecated use ink — kept so leftover references stay monochrome */
  blue: "#1d1d1f",
  blueHover: "#000000",
} as const;

/** Product Marketing sheet only. Never on Shell, Pulse, Jira, Cliq, or Copilot. */
export const pmm = {
  blue: "#1A62F2",
  blueDeep: "#144ecf",
  green: "#157347",
  amber: "#986313",
  blueFill: "#eef4ff",
  greenFill: "#edf8f1",
  amberFill: "#fff6e5",
  muted: "#6a6a6a",
  mutedFill: "#f5f5f7",
} as const;

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
  md: 12,
  lg: 14,
  xl: 16,
  card: 18,
  sheet: 22,
  pill: 999,
} as const;

export const typeScale = {
  display: { fontSize: 44, fontWeight: 600, letterSpacing: "-0.035em", lineHeight: 1.08 },
  title: { fontSize: 21, fontWeight: 600, letterSpacing: "-0.022em", lineHeight: 1.25 },
  heading: { fontSize: 17, fontWeight: 600, letterSpacing: "-0.02em", lineHeight: 1.3 },
  body: { fontSize: 17, lineHeight: 1.47 },
  bodySm: { fontSize: 15, lineHeight: 1.47 },
  caption: { fontSize: 13, lineHeight: 1.4 },
  micro: { fontSize: 12 },
  tiny: { fontSize: 11 },
} as const;

export const motion = {
  pop: apple.pop,
  smooth: apple.smooth,
} as const;

export const shadow = {
  rest: apple.shadow,
  hover: "0 4px 12px rgba(0,0,0,0.06), 0 14px 32px rgba(0,0,0,0.08)",
  raised: "0 6px 16px rgba(0,0,0,0.07), 0 22px 55px rgba(0,0,0,0.11)",
  focus: "0 0 0 3px rgba(0,0,0,0.12)",
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
