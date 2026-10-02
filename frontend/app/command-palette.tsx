"use client";

import AddRoundedIcon from "@mui/icons-material/AddRounded";
import AutoAwesomeOutlinedIcon from "@mui/icons-material/AutoAwesomeOutlined";
import ConfirmationNumberOutlinedIcon from "@mui/icons-material/ConfirmationNumberOutlined";
import DarkModeOutlinedIcon from "@mui/icons-material/DarkModeOutlined";
import LightModeOutlinedIcon from "@mui/icons-material/LightModeOutlined";
import PlayArrowRoundedIcon from "@mui/icons-material/PlayArrowRounded";
import QuestionAnswerOutlinedIcon from "@mui/icons-material/QuestionAnswerOutlined";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import SettingsBrightnessOutlinedIcon from "@mui/icons-material/SettingsBrightnessOutlined";
import SwapHorizRoundedIcon from "@mui/icons-material/SwapHorizRounded";
import Box from "@mui/material/Box";
import Dialog from "@mui/material/Dialog";
import InputBase from "@mui/material/InputBase";
import LinearProgress from "@mui/material/LinearProgress";
import Typography from "@mui/material/Typography";
import { useColorScheme } from "@mui/material/styles";
import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ElementType, type ReactNode } from "react";
import { useCopilot } from "@/app/copilot/context";
import { LINKS, SETTINGS_LINKS, visibleOutputs, PRIMARY } from "@/app/navigation";
import { usePlatform } from "@/app/platform-state";
import { TicketLink } from "@/app/ui";
import { apple, categoryAccent, shadow } from "@/app/ui/tokens";
import { useWorkspace } from "@/app/workspace";
import { api, type StandupItem } from "@/lib/api";
import { prefetchSection } from "@/lib/prefetch";
import { clerkEnabled } from "@/lib/session";

type Command = {
  id: string;
  group: string;
  label: string;
  hint?: string;
  Icon: ElementType;
  color?: string;
  keywords?: string;
  href?: string;
  run?: () => void | Promise<void>;
  /** Keep the palette open after running (used by Ask). */
  stay?: boolean;
};

const PaletteContext = createContext<{ openPalette: (query?: string) => void }>({ openPalette: () => undefined });

export function useCommandPalette() {
  return useContext(PaletteContext);
}

function score(command: Command, needle: string): number {
  if (!needle) return 1;
  const label = command.label.toLowerCase();
  const hay = `${label} ${command.group.toLowerCase()} ${(command.keywords || "").toLowerCase()} ${(command.hint || "").toLowerCase()}`;
  if (label.startsWith(needle)) return 4;
  if (label.split(/\s+/).some((word) => word.startsWith(needle))) return 3;
  if (hay.includes(needle)) return 2;
  const letters = needle.replace(/\s+/g, "");
  let at = 0;
  for (const char of label) if (char === letters[at]) at += 1;
  return at === letters.length ? 1 : 0;
}

const TICKET = /^\s*([A-Z][A-Z0-9]+-\d+)\s*$/i;

export function CommandPaletteProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { me, switchTo } = useWorkspace();
  const { pipelines, enabled, runPipeline } = usePlatform();
  const { open: openCopilot } = useCopilot();
  const { mode, setMode } = useColorScheme();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);
  const [asking, setAsking] = useState(false);
  const [answer, setAnswer] = useState<{ text: string; items: StandupItem[]; searched: number | null } | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const openPalette = useCallback((initial = "") => {
    setQuery(initial);
    setAnswer(null);
    setCursor(0);
    setOpen(true);
  }, []);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((value) => {
          if (!value) {
            setQuery("");
            setAnswer(null);
            setCursor(0);
          }
          return !value;
        });
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const ask = useCallback(async (question: string) => {
    setAsking(true);
    setAnswer(null);
    try {
      const result = await api.ask(question);
      const items = Array.isArray(result.items) ? (result.items as StandupItem[]).filter((item) => item && typeof item === "object") : [];
      setAnswer({ text: result.answer, items, searched: typeof result.searched === "number" ? result.searched : null });
    } catch (err) {
      setAnswer({ text: err instanceof Error ? err.message : String(err), items: [], searched: null });
    } finally {
      setAsking(false);
    }
  }, []);

  const commands = useMemo<Command[]>(() => {
    const out: Command[] = [];
    const q = query.trim();
    const ticket = q.match(TICKET);
    if (ticket) {
      const key = ticket[1].toUpperCase();
      out.push({ id: `ticket-${key}`, group: "Ticket", label: `Open ${key}`, Icon: ConfirmationNumberOutlinedIcon, href: `/issues/${key}` });
    }
    for (const link of [...PRIMARY, ...visibleOutputs(enabled)]) {
      out.push({ id: `go-${link.href}`, group: "Go to", label: link.label, hint: link.group, Icon: link.Icon, color: link.category ? categoryAccent(link.category).main : undefined, keywords: link.keywords, href: link.href });
    }
    for (const link of SETTINGS_LINKS) {
      out.push({ id: `go-${link.href}`, group: "Settings", label: link.label, hint: "Settings", Icon: link.Icon, keywords: `settings ${link.keywords || ""}`, href: link.href });
    }
    for (const pipeline of pipelines?.pipelines || []) {
      if (!pipeline.runnable || !pipeline.enabled) continue;
      const blocked = pipeline.status === "needs_connection";
      const busy = pipeline.status === "running" || pipeline.status === "queued";
      out.push({
        id: `run-${pipeline.id}`,
        group: "Run pipeline",
        label: `Run ${pipeline.name}`,
        hint: busy ? "Running now" : blocked ? `Connect ${pipeline.readiness.missing.join(", ")}` : pipeline.category_label,
        Icon: PlayArrowRoundedIcon,
        color: categoryAccent(pipeline.category).main,
        keywords: `${pipeline.description} run start pipeline`,
        href: blocked || busy ? `/settings/pipelines/${pipeline.id}` : undefined,
        run: blocked || busy ? undefined : () => void runPipeline(pipeline.id),
      });
    }
    if (me && !clerkEnabled) {
      for (const ws of me.workspaces) {
        if (ws.slug === me.workspace.slug) continue;
        out.push({ id: `ws-${ws.slug}`, group: "Workspaces", label: `Switch to ${ws.name}`, hint: ws.product_name || ws.role, Icon: SwapHorizRoundedIcon, keywords: "workspace switch", run: () => switchTo(ws.slug) });
      }
      out.push({ id: "ws-new", group: "Workspaces", label: "Create a workspace", Icon: AddRoundedIcon, keywords: "workspace new", href: "/onboarding?new=1" });
    }
    out.push({ id: "copilot", group: "Actions", label: "Open Copilot", Icon: AutoAwesomeOutlinedIcon, keywords: "chat jira assistant", run: () => openCopilot() });
    const themes: { id: "light" | "dark" | "system"; label: string; Icon: ElementType }[] = [
      { id: "light", label: "Light", Icon: LightModeOutlinedIcon },
      { id: "dark", label: "Dark", Icon: DarkModeOutlinedIcon },
      { id: "system", label: "Match system", Icon: SettingsBrightnessOutlinedIcon },
    ];
    for (const theme of themes) {
      if (theme.id === mode) continue;
      out.push({ id: `theme-${theme.id}`, group: "Actions", label: `Appearance: ${theme.label}`, Icon: theme.Icon, keywords: "theme dark light mode appearance", run: () => setMode(theme.id) });
    }
    const needle = q.toLowerCase();
    const ranked = out
      .map((command, index) => ({ command, rank: command.group === "Ticket" ? 9 : score(command, needle), index }))
      .filter((row) => row.rank > 0)
      .sort((a, b) => (needle ? b.rank - a.rank : 0) || a.index - b.index)
      .map((row) => row.command);
    if (q && !ticket) {
      ranked.push({ id: "ask", group: "Search", label: `Ask: “${q}”`, hint: "Tickets, chats and notes", Icon: QuestionAnswerOutlinedIcon, run: () => ask(q), stay: true });
    }
    return ranked;
  }, [query, enabled, pipelines, me, switchTo, openCopilot, mode, setMode, runPipeline, ask]);

  useEffect(() => setCursor(0), [query]);
  useEffect(() => {
    const node = listRef.current?.querySelector<HTMLElement>(`[data-index="${cursor}"]`);
    node?.scrollIntoView({ block: "nearest" });
  }, [cursor]);

  function execute(command: Command | undefined) {
    if (!command) return;
    if (command.href) {
      setOpen(false);
      router.push(command.href);
      return;
    }
    if (!command.stay) setOpen(false);
    void command.run?.();
  }

  function onKeyDown(event: React.KeyboardEvent) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setCursor((value) => Math.min(commands.length - 1, value + 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setCursor((value) => Math.max(0, value - 1));
    } else if (event.key === "Enter") {
      event.preventDefault();
      execute(commands[cursor]);
    }
  }

  const value = useMemo(() => ({ openPalette }), [openPalette]);
  const activeId = commands[cursor] ? `cmd-${commands[cursor].id}` : undefined;

  return (
    <PaletteContext.Provider value={value}>
      {children}
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        maxWidth="sm"
        fullWidth
        aria-label="Command palette"
        slotProps={{
          paper: { sx: { position: "fixed", top: { xs: 16, sm: "12vh" }, m: 0, mx: 2, width: "calc(100% - 32px)", maxWidth: 640, borderRadius: "16px", overflow: "hidden", bgcolor: apple.raised, border: `1px solid ${apple.hairline}`, boxShadow: shadow.raised } },
          backdrop: { sx: { backdropFilter: "blur(4px)" } },
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.25, px: 2, py: 1.5, borderBottom: `1px solid ${apple.hairline}` }}>
          <SearchRoundedIcon sx={{ color: apple.muted }} />
          <InputBase
            autoFocus
            fullWidth
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setAnswer(null);
            }}
            onKeyDown={onKeyDown}
            placeholder="Go to a page, run a pipeline, open a ticket or ask a question…"
            inputProps={{ "aria-label": "Command", role: "combobox", "aria-expanded": true, "aria-controls": "command-list", "aria-activedescendant": activeId }}
            sx={{ fontSize: 16 }}
          />
          <Box component="kbd" sx={{ fontSize: 11, color: apple.muted, border: `1px solid ${apple.hairline}`, borderRadius: "6px", px: 0.75, py: 0.25 }}>esc</Box>
        </Box>
        {asking ? <LinearProgress aria-label="Searching" /> : null}
        {answer ? (
          <Box sx={{ px: 2.5, py: 2, borderBottom: `1px solid ${apple.hairline}`, maxHeight: 260, overflow: "auto" }}>
            <Typography sx={{ fontSize: 15, lineHeight: 1.55 }}>{answer.text}</Typography>
            {answer.searched != null ? <Typography sx={{ mt: 1, fontSize: 12, color: apple.muted }}>Searched {answer.searched} tickets.</Typography> : null}
            {answer.items.length ? (
              <Box component="ul" sx={{ listStyle: "none", m: 0, mt: 1.5, p: 0, display: "grid", gap: 1 }}>
                {answer.items.slice(0, 6).map((item, index) => (
                  <Box component="li" key={`${item.issue_key || item.title || index}`} sx={{ fontSize: 14 }}>
                    {item.issue_key ? <TicketLink issueKey={item.issue_key} onClick={() => setOpen(false)} /> : null}
                    {item.issue_key ? " · " : ""}
                    {item.title || item.body || item.action}
                  </Box>
                ))}
              </Box>
            ) : null}
          </Box>
        ) : null}
        <Box ref={listRef} id="command-list" role="listbox" sx={{ maxHeight: { xs: "60vh", sm: 420 }, overflow: "auto", py: 1 }}>
          {commands.length ? (
            commands.map((command, index) => {
              const header = commands[index - 1]?.group !== command.group;
              const on = index === cursor;
              const Icon = command.Icon;
              return (
                <Box key={command.id}>
                  {header ? <Typography sx={{ px: 2.5, pt: index ? 1.5 : 0.5, pb: 0.5, fontSize: 11, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", color: apple.muted }}>{command.group}</Typography> : null}
                  <Box
                    id={`cmd-${command.id}`}
                    role="option"
                    aria-selected={on}
                    data-index={index}
                    onMouseMove={() => setCursor(index)}
                    onMouseEnter={() => command.href && prefetchSection(command.href)}
                    onClick={() => execute(command)}
                    sx={{
                      mx: 1,
                      px: 1.5,
                      py: 1,
                      display: "flex",
                      alignItems: "center",
                      gap: 1.5,
                      borderRadius: "10px",
                      cursor: "pointer",
                      bgcolor: on ? apple.hoverFill : "transparent",
                      transition: `background-color 120ms ${apple.smooth}`,
                    }}
                  >
                    <Box sx={{ width: 28, height: 28, borderRadius: "8px", display: "grid", placeItems: "center", bgcolor: on ? apple.raised : apple.hoverFill, border: `1px solid ${apple.hairline}`, color: command.color || apple.text, flexShrink: 0 }}>
                      <Icon sx={{ fontSize: 17 }} />
                    </Box>
                    <Typography sx={{ fontSize: 14, fontWeight: on ? 550 : 450, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{command.label}</Typography>
                    {command.hint ? <Typography sx={{ ml: "auto", pl: 2, fontSize: 12, color: apple.muted, whiteSpace: "nowrap" }}>{command.hint}</Typography> : null}
                  </Box>
                </Box>
              );
            })
          ) : (
            <Typography sx={{ px: 2.5, py: 3, fontSize: 14, color: apple.muted, textAlign: "center" }}>No matches.</Typography>
          )}
        </Box>
        <Box sx={{ display: "flex", gap: 2, px: 2.5, py: 1.25, borderTop: `1px solid ${apple.hairline}`, fontSize: 11, color: apple.muted }}>
          <span>↑↓ to move</span>
          <span>↵ to open</span>
          <Box component="span" sx={{ ml: "auto" }}>{LINKS.length + SETTINGS_LINKS.length} pages · {(pipelines?.pipelines || []).filter((p) => p.runnable).length} runnable pipelines</Box>
        </Box>
      </Dialog>
    </PaletteContext.Provider>
  );
}
