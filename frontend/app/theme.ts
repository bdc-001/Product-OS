"use client";

import { createTheme } from "@mui/material/styles";
import { apple, fontFamily, motion, radius, shadow, typeScale } from "@/app/ui/tokens";

export { apple, fontFamily, motion, pmm, radius, shadow, space, typeScale } from "@/app/ui/tokens";

const reduceMotion = {
  "@media (prefers-reduced-motion: reduce)": {
    transition: "none !important",
    animation: "none !important",
    transform: "none !important",
  },
};

export const theme = createTheme({
  palette: {
    primary: { main: apple.ink, contrastText: "#ffffff" },
    error: { main: apple.danger },
    success: { main: apple.ink },
    text: { primary: apple.text, secondary: apple.muted },
    divider: apple.hairline,
    background: { default: apple.page, paper: apple.page },
  },
  typography: {
    fontFamily,
    fontSize: 16,
    h1: { ...typeScale.display, color: apple.text },
    h2: { ...typeScale.title, color: apple.text },
    h3: { ...typeScale.heading, color: apple.text },
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
          "--page": apple.page,
          "--wash": apple.wash,
          "--text": apple.text,
          "--muted": apple.muted,
          "--hairline": apple.hairline,
          "--ink": apple.ink,
          "--ink-hover": apple.inkHover,
          "--sel-fill": apple.selFill,
          "--danger": apple.danger,
          "--pop": motion.pop,
          "--smooth": motion.smooth,
          "--shadow": shadow.rest,
        },
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
          padding: "10px 18px",
          transition: `transform 0.4s ${motion.pop}, background-color 0.3s ${motion.smooth}, box-shadow 0.3s ${motion.smooth}, color 0.3s ${motion.smooth}, border-color 0.3s ${motion.smooth}`,
          willChange: "transform",
          "&:active": { transform: "scale(0.98)" },
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
          "&:hover": { borderColor: "#c7c7cc", backgroundColor: apple.hoverFill },
        },
        text: {
          color: apple.ink,
          padding: "11px 14px",
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
          "&:active": { transform: "scale(0.9)" },
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
          minHeight: 24,
          fontSize: typeScale.micro.fontSize,
          backgroundColor: apple.wash,
          color: apple.muted,
          border: `1px solid ${apple.hairline}`,
          transition: `transform 0.4s ${motion.pop}`,
          "&:active": { transform: "scale(0.9)" },
          "& .MuiChip-label": { paddingTop: "3px", paddingBottom: "3px" },
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
        root: { overflowWrap: "anywhere", borderColor: apple.hairline, fontSize: typeScale.bodySm.fontSize },
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
          "&:active": { transform: "scale(0.9)" },
          "&.Mui-selected": { backgroundColor: apple.ink, color: "#fff" },
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
        switchBase: { color: "#fff" },
        track: { backgroundColor: apple.hairline, opacity: 1 },
        thumb: { boxShadow: shadow.switch },
        root: {
          width: 52,
          height: 32,
          padding: 3,
          "& .MuiSwitch-switchBase": { padding: 3 },
          "& .MuiSwitch-switchBase.Mui-checked": { color: "#fff", transform: "translateX(20px)" },
          "& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track": { backgroundColor: apple.ink, opacity: 1 },
          "& .MuiSwitch-thumb": { width: 26, height: 26 },
        },
      },
    },
  },
});
