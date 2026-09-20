"use client";

import CheckRoundedIcon from "@mui/icons-material/CheckRounded";
import CloseRoundedIcon from "@mui/icons-material/CloseRounded";
import ChevronRightRoundedIcon from "@mui/icons-material/ChevronRightRounded";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button, { type ButtonProps } from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import Drawer from "@mui/material/Drawer";
import IconButton from "@mui/material/IconButton";
import Link from "@mui/material/Link";
import Pagination from "@mui/material/Pagination";
import Paper from "@mui/material/Paper";
import Skeleton from "@mui/material/Skeleton";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import NextLink from "next/link";
import { useEffect, useState, type KeyboardEvent, type MouseEvent, type ReactNode } from "react";
import { apple, radius, shadow, space } from "@/app/ui/tokens";
import Stack from "@/app/ui/stack";

export const PAGE_SIZE = 10;

const wrap = {
  minWidth: 0,
  overflowWrap: "anywhere",
  wordBreak: "break-word",
} as const;

const reduce = {
  "@media (prefers-reduced-motion: reduce)": {
    transition: "none !important",
    transform: "none !important",
  },
} as const;

export function PageBody({ children, wide }: { children: ReactNode; wide?: boolean }) {
  return (
    <Box
      className="page-body"
      sx={{
        width: "100%",
        maxWidth: wide ? "none" : 1600,
        mx: "auto",
        boxSizing: "border-box",
        px: { xs: 2, md: 3, xl: 4 },
        py: { xs: 3, md: 4 },
        pb: 8,
        minWidth: 0,
      }}
    >
      {children}
    </Box>
  );
}

export function PageHeader({ title, subtitle, tabs }: { title: string; subtitle?: string; tabs?: ReactNode }) {
  return (
    <Box sx={{ mb: 2.5, ...wrap }}>
      <Typography component="p" className="module-page-label" sx={{ fontSize: 14, fontWeight: 600, color: apple.muted }}>
        {title}
      </Typography>
      {subtitle ? (
        <Typography sx={{ mt: 0.75, fontSize: 17, lineHeight: 1.47, color: apple.muted }}>{subtitle}</Typography>
      ) : null}
      {tabs ? <Box sx={{ mt: 2, maxWidth: 420 }}>{tabs}</Box> : null}
    </Box>
  );
}

export function Section({ title, count, children }: { title: string; count?: number; children?: ReactNode }) {
  return (
    <Box component="section" sx={{ mb: 3, minWidth: 0 }}>
      <Typography variant="h2" sx={{ mb: 1.25 }}>
        {title}
        {count != null ? <Box component="span" sx={{ ml: 1, px: 1, py: 0.25, borderRadius: "7px", bgcolor: apple.hoverFill, color: apple.muted, fontSize: 12, verticalAlign: "middle", fontVariantNumeric: "tabular-nums" }}>{count}</Box> : null}
      </Typography>
      {children}
    </Box>
  );
}

export function SubSection({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <Box sx={{ mb: 2, minWidth: 0 }}>
      <Typography
        sx={{
          fontSize: 12,
          fontWeight: 600,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          color: apple.muted,
          mb: 1,
        }}
      >
        {title}
      </Typography>
      {children}
    </Box>
  );
}

export function TicketLink({
  issueKey,
  href,
  children,
  onClick,
}: {
  issueKey?: string;
  href?: string;
  children?: ReactNode;
  onClick?: (event: MouseEvent<HTMLAnchorElement>) => void;
}) {
  const to = href || (issueKey ? `/issues/${issueKey}` : "");
  if (!to) return <>{children || issueKey}</>;
  const external = /^https?:\/\//.test(to);
  return (
    <Link
      component={external ? "a" : NextLink}
      href={to}
      underline="always"
      target={external ? "_blank" : undefined}
      rel={external ? "noreferrer" : undefined}
      onClick={onClick}
      sx={{
        fontWeight: 600,
        color: apple.ink,
        textDecoration: "underline",
        textDecorationThickness: "1.5px",
        textUnderlineOffset: "3px",
        "&:hover": { color: apple.inkHover },
      }}
    >
      {children || issueKey}
    </Link>
  );
}

export function FrostCard({ children, sx, id }: { children: ReactNode; sx?: object; id?: string }) {
  return (
    <Paper
      id={id}
      elevation={1}
      sx={{
        borderRadius: "18px",
        p: { xs: "18px", md: "22px" },
        transition: "box-shadow 180ms ease, border-color 180ms ease",
        "&:hover": { borderColor: apple.hairlineHover, boxShadow: shadow.hover },
        ...reduce,
        bgcolor: apple.page,
        width: "100%",
        overflow: "visible",
        ...wrap,
        ...sx,
      }}
    >
      {children}
    </Paper>
  );
}

export function ListRow({
  selected,
  current,
  onClick,
  href,
  children,
  disabled,
}: {
  selected?: boolean;
  current?: boolean;
  onClick?: () => void;
  href?: string;
  children: ReactNode;
  disabled?: boolean;
}) {
  const marked = Boolean(selected);
  const sx = {
    display: "flex",
    alignItems: "flex-start",
    gap: "14px",
    width: "100%",
    textAlign: "left" as const,
    appearance: "none",
    WebkitAppearance: "none",
    border: `1px solid ${marked || current ? apple.ink : apple.hairline}`,
    bgcolor: marked ? apple.selFill : apple.page,
    boxShadow: current && !marked ? `inset 3px 0 0 ${apple.ink}` : "none",
    borderRadius: "16px",
    px: "16px",
    py: "14px",
    cursor: disabled ? "not-allowed" : "pointer",
    fontFamily: "inherit",
    fontSize: 15,
    lineHeight: 1.47,
    color: "inherit",
    textDecoration: "none",
    boxSizing: "border-box" as const,
    opacity: disabled ? 0.55 : 1,
    pointerEvents: disabled ? "none" : "auto",
    overflow: "visible",
    willChange: "transform",
    transition: `border-color 0.3s ${apple.smooth}, background-color 0.3s ${apple.smooth}, transform 0.38s ${apple.pop}, box-shadow 0.3s ${apple.smooth}`,
    "&:hover": { bgcolor: marked ? apple.selFill : apple.hoverFill },
    "&:active": { transform: "scale(0.985)" },
    ...wrap,
    ...reduce,
  };
  const inner = (
    <>
      <Box
        component="span"
        sx={{
          width: 22,
          height: 22,
          mt: "1px",
          borderRadius: "999px",
          border: `1.5px solid ${marked ? apple.ink : apple.hairline}`,
          bgcolor: marked ? apple.ink : "transparent",
          display: "grid",
          placeItems: "center",
          flex: "none",
          transition: `background-color 0.3s ${apple.smooth}, border-color 0.3s ${apple.smooth}, transform 0.4s ${apple.pop}`,
          transform: marked ? "scale(1.05)" : "none",
          ...reduce,
        }}
      >
        <CheckRoundedIcon
          sx={{
            fontSize: 14,
            color: "#fff",
            opacity: marked ? 1 : 0,
            transform: marked ? "scale(1)" : "scale(0.4)",
            transition: `opacity 0.25s ${apple.smooth}, transform 0.4s ${apple.pop}`,
            ...reduce,
          }}
        />
      </Box>
      <Box sx={{ flex: 1, minWidth: 0 }}>{children}</Box>
    </>
  );
  if (href) {
    return (
      <Box component="a" href={href} sx={sx}>
        {inner}
      </Box>
    );
  }
  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (disabled) return;
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onClick?.();
    }
  }
  return (
    <Box
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-disabled={disabled || undefined}
      aria-pressed={marked || undefined}
      onClick={disabled ? undefined : onClick}
      onKeyDown={onKeyDown}
      sx={sx}
    >
      {inner}
    </Box>
  );
}

export function Segmented({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (id: string) => void;
  options: { id: string; label: ReactNode }[];
}) {
  const n = Math.max(options.length, 1);
  const index = Math.max(0, options.findIndex((option) => option.id === value));
  return (
    <Box
      role="tablist"
      aria-label="View options"
      sx={{
        position: "relative",
        display: "flex",
        width: "100%",
        bgcolor: apple.wash,
        border: "none",
        borderRadius: "9px",
        p: "2px",
        minWidth: 0,
      }}
    >
      <Box
        aria-hidden
        sx={{
          position: "absolute",
          top: 2,
          bottom: 2,
          left: 2,
          width: `calc((100% - 4px) / ${n})`,
          bgcolor: apple.page,
          borderRadius: "7px",
          boxShadow: "0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.04)",
          transform: `translateX(${index * 100}%)`,
          transition: `transform 0.35s ${apple.smooth}`,
          ...reduce,
        }}
      />
      {options.map((option) => {
        const on = option.id === value;
        return (
          <Box
            key={option.id}
            component="button"
            type="button"
            role="tab"
            aria-selected={on}
            tabIndex={on ? 0 : -1}
            onKeyDown={(event) => {
              const current = options.findIndex((entry) => entry.id === value);
              const next = event.key === "ArrowRight" ? (current + 1) % n : event.key === "ArrowLeft" ? (current - 1 + n) % n : event.key === "Home" ? 0 : event.key === "End" ? n - 1 : -1;
              if (next < 0) return;
              event.preventDefault();
              onChange(options[next].id);
              (event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[next])?.focus();
            }}
            onClick={() => onChange(option.id)}
            sx={{
              position: "relative",
              zIndex: 1,
              flex: 1,
              minWidth: 0,
              border: 0,
              bgcolor: "transparent",
              cursor: "pointer",
              fontFamily: "inherit",
              fontSize: 13,
              fontWeight: 500,
              py: "8px",
              px: 1,
              color: on ? apple.text : apple.muted,
              transition: `color 0.3s ${apple.smooth}`,
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {option.label}
          </Box>
        );
      })}
    </Box>
  );
}

type PillVariant = "filled" | "gray" | "text";

type PillButtonProps = Omit<ButtonProps, "variant" | "href"> & {
  variant?: PillVariant;
  href?: string;
  target?: string;
  rel?: string;
  download?: boolean | string;
};

export function PillButton({ variant = "filled", href, children, endIcon, target, rel, download, ...props }: PillButtonProps) {
  const muiVariant = variant === "filled" ? "contained" : variant === "gray" ? "outlined" : "text";
  const color = variant === "filled" ? "primary" : "inherit";
  const icon = variant === "text" ? endIcon ?? <ChevronRightRoundedIcon fontSize="small" /> : endIcon;
  if (href) {
    const external = /^https?:\/\//.test(href) || href.startsWith("/api/");
    if (external) {
      return (
        <Button component="a" href={href} target={target} rel={rel} download={download} variant={muiVariant} color={color} endIcon={icon} {...props}>
          {children}
        </Button>
      );
    }
    return (
      <Button component={NextLink} href={href} variant={muiVariant} color={color} endIcon={icon} {...props}>
        {children}
      </Button>
    );
  }
  return (
    <Button variant={muiVariant} color={color} endIcon={icon} {...props}>
      {children}
    </Button>
  );
}

export function StatusChip({ label, tone }: { label: string; tone?: "danger" | "ink" | "default" }) {
  return (
    <Chip
      size="small"
      label={label}
      sx={{
        maxWidth: "100%",
        height: "auto",
        minHeight: 24,
        "& .MuiChip-label": { whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 180, paddingTop: "3px", paddingBottom: "3px" },
        ...(tone === "danger" ? { bgcolor: apple.dangerFill, color: apple.danger, borderColor: apple.dangerLine } : {}),
        ...(tone === "ink" ? { bgcolor: apple.ink, color: "#fff", borderColor: apple.ink } : {}),
      }}
    />
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <Typography color="text.secondary" sx={{ fontSize: 14, lineHeight: 1.6, p: 3, border: `1px dashed ${apple.hairline}`, borderRadius: "14px", textAlign: "center", bgcolor: apple.hoverFill }}>
      {children}
    </Typography>
  );
}

export function Banner({
  children,
  severity = "warning",
}: {
  children: ReactNode;
  severity?: "warning" | "error" | "info" | "success";
}) {
  return (
    <Alert severity={severity} sx={{ mb: 2, borderRadius: "16px", ...wrap }}>
      {children}
    </Alert>
  );
}

export function RemoveButton({
  onClick,
  title = "Remove",
  disabled,
}: {
  onClick: () => void;
  title?: string;
  disabled?: boolean;
}) {
  return (
    <Tooltip title={title}>
      <span>
        <IconButton size="small" onClick={onClick} disabled={disabled} aria-label={title}>
          <CloseRoundedIcon fontSize="small" />
        </IconButton>
      </span>
    </Tooltip>
  );
}

export function PagedList<T>({
  items,
  getKey,
  renderItem,
  empty,
  resetKey,
  pageSize = PAGE_SIZE,
}: {
  items: T[];
  getKey: (item: T, index: number) => string | number;
  renderItem: (item: T, index: number) => ReactNode;
  empty?: ReactNode;
  resetKey?: string | number;
  pageSize?: number;
}) {
  const [page, setPage] = useState(1);

  useEffect(() => {
    setPage(1);
  }, [resetKey]);

  if (!items.length) return <>{empty ?? <EmptyState>None.</EmptyState>}</>;

  const pageCount = Math.max(1, Math.ceil(items.length / pageSize));
  const safePage = Math.min(page, pageCount);
  const slice = items.slice((safePage - 1) * pageSize, safePage * pageSize);

  return (
    <Stack spacing={1.25}>
      <Stack spacing={1.5}>
        {slice.map((item, index) => (
          <Box key={getKey(item, (safePage - 1) * pageSize + index)} sx={wrap}>
            {renderItem(item, (safePage - 1) * pageSize + index)}
          </Box>
        ))}
      </Stack>
      {pageCount > 1 ? (
        <Pagination
          count={pageCount}
          page={safePage}
          onChange={(_, next) => setPage(next)}
          size="small"
          siblingCount={0}
          sx={{ pt: 0.5 }}
        />
      ) : null}
    </Stack>
  );
}

export function MarkdownBlock({ children }: { children: ReactNode }) {
  return (
    <Box
      component="pre"
      sx={{
        whiteSpace: "pre-wrap",
        fontSize: 15,
        lineHeight: 1.47,
        bgcolor: apple.page,
        border: `1px solid ${apple.hairline}`,
        p: 2,
        ...wrap,
        overflow: "auto",
        borderRadius: "16px",
        color: apple.text,
        fontFamily: "inherit",
        m: 0,
      }}
    >
      {children}
    </Box>
  );
}

function inkDot(bgcolor: string) {
  return {
    width: 8,
    height: 8,
    borderRadius: "50%",
    bgcolor,
    flexShrink: 0,
  } as const;
}

export function QuietDot({ on, label }: { on?: boolean; label: string }) {
  return (
    <Stack direction="row" spacing={1} alignItems="center" sx={{ fontSize: 13, color: apple.muted }}>
      <Box component="span" sx={inkDot(on ? apple.ink : apple.hairline)} />
      {label ? label : null}
    </Stack>
  );
}

export function ConnectionDots({
  jira,
  cliq,
  llm,
}: {
  jira?: boolean | null;
  cliq?: boolean | null;
  llm?: boolean | null;
}) {
  const tone = (value: boolean | null | undefined) => (value ? apple.ink : value === false ? apple.muted : apple.hairline);
  return (
    <Stack direction="row" spacing={0.6} aria-hidden>
      <Box sx={inkDot(tone(jira))} />
      <Box sx={inkDot(tone(cliq))} />
      <Box sx={inkDot(tone(llm))} />
    </Stack>
  );
}

export function ModuleIntro({ children }: { children: ReactNode }) {
  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: `${space.xl}px`,
        mb: `${space.xxl}px`,
        flexWrap: "wrap",
      }}
    >
      {children}
    </Box>
  );
}

export function KnowledgeSplit({ sidebar, children }: { sidebar: ReactNode; children: ReactNode }) {
  return (
    <Box
      sx={{
        display: "grid",
        gridTemplateColumns: "250px minmax(0,1fr)",
        gap: `${space.xxl}px`,
        alignItems: "start",
        "@media (max-width: 900px)": { gridTemplateColumns: "1fr" },
      }}
    >
      <Box>{sidebar}</Box>
      {children}
    </Box>
  );
}

export function KnowledgeList({ children }: { children: ReactNode }) {
  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        gap: `${space.sm}px`,
        maxHeight: "65vh",
        overflow: "auto",
        "@media (max-width: 900px)": { maxHeight: 220 },
      }}
    >
      {children}
    </Box>
  );
}

export function AppDialog({
  open,
  onClose,
  title,
  titleId,
  children,
  actions,
  maxWidth = "sm",
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  titleId?: string;
  children: ReactNode;
  actions?: ReactNode;
  maxWidth?: "xs" | "sm" | "md" | "lg" | "xl";
}) {
  const labelledBy = titleId || "app-dialog-title";
  return (
    <Dialog aria-labelledby={labelledBy} open={open} onClose={onClose} maxWidth={maxWidth} fullWidth>
      <DialogTitle id={labelledBy} sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", pr: 1.5, fontSize: 17, fontWeight: 600 }}>
        {title}
        <RemoveButton onClick={onClose} title="Close" />
      </DialogTitle>
      <DialogContent sx={{ pt: 0, pb: 2.5 }}>{children}</DialogContent>
      {actions ? <DialogActions sx={{ px: 3, pb: 2.5 }}>{actions}</DialogActions> : null}
    </Dialog>
  );
}

export function SideDrawer({
  open,
  onClose,
  children,
  width,
}: {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  width?: { xs?: string | number; sm?: string | number; md?: string | number };
}) {
  return (
    <Drawer anchor="right" open={open} onClose={onClose} slotProps={{ paper: { sx: { width: width ?? { xs: "100%", sm: 480 }, p: 3, bgcolor: apple.page } } }}>
      {children}
    </Drawer>
  );
}

export function LoadingBlock({
  rows = 3,
  height = 72,
  label = "Loading",
}: {
  rows?: number;
  height?: number;
  label?: string;
}) {
  return (
    <Box role="status" aria-label={label} sx={{ display: "grid", gap: 1.5 }}>
      {Array.from({ length: rows }, (_, index) => (
        <Skeleton key={index} variant="rounded" height={height} sx={{ borderRadius: `${radius.card}px` }} />
      ))}
    </Box>
  );
}
