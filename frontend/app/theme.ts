"use client";

import { createTheme } from "@mui/material/styles";
import { apple, darkPalette, fontFamily, lightPalette, motion, paletteVars, pmm, radius, shadow, typeScale } from "@/app/ui/tokens";

export { accent, apple, categoryAccent, fontFamily, motion, pmm, radius, shadow, space, typeScale } from "@/app/ui/tokens";

const reduceMotion = {
  "@media (prefers-reduced-motion: reduce)": {
    transition: "none !important",
    animation: "none !important",
    transform: "none !important",
  },
};

function schemePalette(raw: typeof lightPalette | typeof darkPalette, mode: "light" | "dark") {
  return {
    mode,
    primary: { main: raw.ink, contrastText: raw.onInk },
    error: { main: raw.danger },
    success: { main: raw.green },
    warning: { main: mode === "light" ? "#946200" : raw.amber },
    info: { main: mode === "light" ? "#465d85" : "#8fb3e8" },
    text: { primary: raw.text, secondary: raw.muted },
    divider: raw.hairline,
    background: { default: raw.page, paper: raw.raised },
  };
}

export const theme = createTheme({
  cssVariables: { colorSchemeSelector: "class" },
  colorSchemes: {
    light: { palette: schemePalette(lightPalette, "light") },
    dark: { palette: schemePalette(darkPalette, "dark") },
  },
  typography: {
    fontFamily,
    fontSize: 14,
    h1: { ...typeScale.display, color: apple.text },
    h2: { ...typeScale.title, color: apple.text },
    h3: { ...typeScale.heading, color: apple.text },
    h4: { fontSize: 24, fontWeight: 600, lineHeight: 1.3, letterSpacing: "-0.02em" },
    h5: { fontSize: 20, fontWeight: 600, lineHeight: 1.35 },
    h6: { fontSize: 16, fontWeight: 600, lineHeight: 1.4 },
    body1: { ...typeScale.body, color: apple.text },
    body2: { ...typeScale.bodySm, color: apple.text },
    caption: { ...typeScale.caption, color: apple.muted },
    button: { fontFamily, fontWeight: 500, textTransform: "none", letterSpacing: 0 },
  },
  shape: { borderRadius: radius.md },
  shadows: [
    "none",
    shadow.rest,
    shadow.raised,
    "none",
    "none",
    "none",
    "none",
    "none",
    "none",
    "none",
    "none",
    "none",
    "none",
    "none",
    "none",
    "none",
    "none",
    "none",
    "none",
    "none",
    "none",
    "none",
    "none",
    "none",
    "none",
  ],
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        ":root": {
          ...paletteVars(lightPalette),
          "--pop": motion.pop,
          "--smooth": motion.smooth,
        },
        ":root.dark": paletteVars(darkPalette),
        body: {
          backgroundColor: apple.page,
          color: apple.text,
          fontFamily,
          WebkitFontSmoothing: "antialiased",
        },
        "@media (prefers-reduced-motion: reduce)": {
          "*, *::before, *::after": {
            animationDuration: "0.01ms !important",
            animationIterationCount: "1 !important",
            transitionDuration: "0.01ms !important",
            scrollBehavior: "auto !important",
          },
        },
        "a:focus-visible, button:focus-visible, input:focus-visible, textarea:focus-visible, select:focus-visible, [tabindex]:focus-visible": {
          outline: `3px solid ${apple.ink}`,
          outlineOffset: 2,
        },
      },
    },
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: {
        root: {
          borderRadius: radius.md,
          textTransform: "none",
          fontWeight: 500,
          fontSize: typeScale.bodySm.fontSize,
          padding: "8px 14px",
          minHeight: 36,
          lineHeight: 1.4,
          flexShrink: 0,
          transition: `transform 0.4s ${motion.pop}, background-color 0.3s ${motion.smooth}, box-shadow 0.3s ${motion.smooth}, color 0.3s ${motion.smooth}, border-color 0.3s ${motion.smooth}`,


          "&.Mui-focusVisible": { outline: `3px solid ${apple.ink}`, outlineOffset: 2 },
          "&.MuiButton-containedPrimary": {
            backgroundColor: apple.ink,
            "&:hover": { backgroundColor: apple.inkHover, boxShadow: shadow.rest },
          },
          ...reduceMotion,
        },
        outlined: {
          borderColor: apple.hairline,
          color: apple.text,
          backgroundColor: apple.page,
          "&:hover": { borderColor: apple.hairlineHover, backgroundColor: apple.hoverFill },
        },
        text: {
          color: apple.ink,
          padding: "8px 12px",
          "&:hover": { backgroundColor: apple.selFill },
        },
      },
    },
    MuiIconButton: {
      styleOverrides: {
        root: {
          color: apple.muted,
          transition: `transform 0.4s ${motion.pop}, background-color 0.3s ${motion.smooth}, color 0.3s ${motion.smooth}`,
          "&:hover": { backgroundColor: apple.wash, color: apple.text },

          "&.Mui-focusVisible": { outline: `3px solid ${apple.ink}`, outlineOffset: 2 },
          ...reduceMotion,
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          borderRadius: radius.pill,
          height: "auto",
          maxWidth: "100%",
          minHeight: 24,
          fontSize: typeScale.micro.fontSize,
          backgroundColor: apple.wash,
          color: apple.muted,
          border: `1px solid ${apple.hairline}`,
          "&.MuiChip-colorSuccess": { color: pmm.green, backgroundColor: pmm.greenFill, borderColor: pmm.greenLine },
          "&.MuiChip-colorWarning": { color: pmm.amber, backgroundColor: pmm.amberFill, borderColor: pmm.amberLine },
          "&.MuiChip-colorError": { color: apple.danger, backgroundColor: apple.dangerFill, borderColor: apple.dangerLine },
          transition: `transform 0.4s ${motion.pop}`,

          "& .MuiChip-label": { overflow: "hidden", textOverflow: "ellipsis", paddingTop: "3px", paddingBottom: "3px" },
          ...reduceMotion,
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        rounded: { borderRadius: radius.sheet },
        elevation1: {
          boxShadow: shadow.rest,
          border: `1px solid ${apple.hairline}`,
          overflow: "visible",
        },
      },
    },
    MuiTextField: { defaultProps: { size: "small" } },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          borderRadius: radius.md,
          backgroundColor: apple.page,
          transition: `box-shadow 0.3s ${motion.smooth}`,
          "&:hover .MuiOutlinedInput-notchedOutline": { borderColor: apple.hairline },
          "&.Mui-focused": { boxShadow: shadow.focus },
          "&.Mui-focused .MuiOutlinedInput-notchedOutline": { borderColor: apple.ink, borderWidth: 1 },
        },
        input: { fontSize: typeScale.bodySm.fontSize, padding: "10px 12px" },
      },
    },
    MuiInputLabel: {
      styleOverrides: { root: { fontSize: typeScale.caption.fontSize, color: apple.muted } },
    },
    MuiAlert: {
      styleOverrides: {
        root: { borderRadius: radius.xl, fontSize: 14 },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        head: { backgroundColor: apple.nav, fontWeight: 600, fontSize: 12, color: apple.muted },
        root: { padding: "12px 16px", overflowWrap: "anywhere", borderColor: apple.hairline, fontSize: typeScale.bodySm.fontSize },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          backgroundColor: apple.page,
          color: apple.text,
          borderLeft: `1px solid ${apple.hairline}`,
        },
      },
    },
    MuiDialog: {
      styleOverrides: {
        paper: {
          borderRadius: radius.sheet,
          boxShadow: shadow.raised,
          border: `1px solid ${apple.hairline}`,
          backgroundColor: apple.page,
        },
      },
    },
    MuiAccordion: {
      styleOverrides: {
        root: {
          boxShadow: "none",
          border: `1px solid ${apple.hairline}`,
          borderRadius: `${radius.xl}px !important`,
          backgroundColor: apple.page,
          overflow: "visible",
          "&:before": { display: "none" },
          "&.Mui-expanded": { margin: 0 },
        },
      },
    },
    MuiAccordionSummary: {
      styleOverrides: {
        root: { minHeight: 48 },
        content: { margin: "12px 0" },
      },
    },
    MuiTabs: {
      styleOverrides: {
        indicator: { backgroundColor: apple.ink, height: 2, borderRadius: radius.pill },
      },
    },
    MuiLinearProgress: {
      styleOverrides: {
        root: { backgroundColor: apple.wash, borderRadius: radius.pill },
        bar: { backgroundColor: apple.ink, borderRadius: radius.pill },
      },
    },
    MuiSkeleton: {
      styleOverrides: {
        root: { backgroundColor: apple.wash },
        rounded: { borderRadius: radius.card },
      },
    },
    MuiPaginationItem: {
      styleOverrides: {
        root: {
          borderRadius: radius.pill,
          transition: `transform 0.4s ${motion.pop}, background-color 0.3s ${motion.smooth}`,

          "&.Mui-selected": { backgroundColor: apple.ink, color: apple.onInk },
          "&.Mui-selected:hover": { backgroundColor: apple.inkHover },
          ...reduceMotion,
        },
      },
    },
    MuiTab: {
      styleOverrides: {
        root: {
          textTransform: "none",
          borderRadius: radius.pill,
          minHeight: 36,
          fontWeight: 500,
        },
      },
    },
    MuiLink: {
      styleOverrides: {
        root: { color: apple.ink },
        underlineNone: { textDecoration: "none", "&:hover": { textDecoration: "none" } },
        underlineHover: { textDecoration: "none", "&:hover": { textDecoration: "underline", textUnderlineOffset: "3px" } },
        underlineAlways: { textDecoration: "underline", textUnderlineOffset: "3px" },
      },
    },
    MuiSwitch: {
      styleOverrides: {
        switchBase: { color: "#ffffff" },
        track: { backgroundColor: apple.hairline, opacity: 1 },
        thumb: { boxShadow: shadow.switch },
        root: {
          width: 52,
          height: 32,
          padding: 3,
          "& .MuiSwitch-switchBase": { padding: 3 },
          "& .MuiSwitch-switchBase.Mui-checked": { color: apple.onInk, transform: "translateX(20px)" },
          "& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track": { backgroundColor: apple.ink, opacity: 1 },
          "& .MuiSwitch-thumb": { width: 26, height: 26 },
        },
      },
    },
  },
});
