"use client";

import AutoAwesomeOutlinedIcon from "@mui/icons-material/AutoAwesomeOutlined";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import RefreshRoundedIcon from "@mui/icons-material/RefreshRounded";
import MenuItem from "@mui/material/MenuItem";
import Button from "@mui/material/Button";
import LinearProgress from "@mui/material/LinearProgress";
import { LINKS } from "@/app/navigation";
import Box from "@mui/material/Box";
import Stack from "@/app/ui/stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api, type Standup, type StandupItem } from "@/lib/api";
import { buildPulse } from "@/lib/pulse";
import { useRefresh } from "@/app/refresh";
import { useCopilot } from "@/app/copilot/context";
import { AppDialog, Banner, PillButton, TicketLink } from "@/app/ui";
import { apple } from "@/app/theme";

function asItems(raw: unknown): StandupItem[] {
  if (Array.isArray(raw)) return raw.filter((item) => item && typeof item === "object") as StandupItem[];
  return [];
}

function formatAge(seconds: number | null | undefined) {
  if (seconds == null) return "";
  if (seconds < 60) return "just now";
  const hours = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  if (hours >= 1) return `${hours}h ago`;
  return `${mins}m ago`;
}

export function PulseBar() {
  const [standup, setStandup] = useState<Standup | null>(null);
  const [name, setName] = useState("Arsalaan");
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState("");
  const [hits, setHits] = useState<StandupItem[]>([]);
  const [searched, setSearched] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
  const [health, setHealth] = useState<{ last_run_age_seconds?: number | null; last_run_stale?: boolean; dead_letter?: boolean }>({});
  const searchRef = useRef<HTMLInputElement>(null);
  const { tick, refreshing, message, refreshAll } = useRefresh();
  const { open: openCopilot } = useCopilot();
  const path = usePathname() || "/";
  const router = useRouter();

  useEffect(() => {
    api.workspaceSummary().then((data) => { setName(data.pm_display_name); setHealth(data); }).catch(() => null);
  }, [tick]);

  useEffect(() => {
    setOpen(false);
  }, [path]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const typing = target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable);
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen(true);
        return;
      }
      if (typing || open) return;
      if (event.key === "g") {
        const next = (event2: KeyboardEvent) => {
          window.removeEventListener("keydown", next, true);
          if (event2.key.toLowerCase() === "s") {
            event2.preventDefault();
            router.push("/");
          }
          if (event2.key.toLowerCase() === "u") {
            event2.preventDefault();
            router.push("/?view=uat");
          }
        };
        window.addEventListener("keydown", next, true);
        window.setTimeout(() => window.removeEventListener("keydown", next, true), 800);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [router, open]);

  const home = path === "/";
  const moduleTitle = LINKS.find((link) => link.href === "/" ? home : path.startsWith(link.href))?.label || (path.startsWith("/issues") ? "Ticket details" : "Workspace");
  const defaultScope = path.startsWith("/marketing") ? "all" : path.startsWith("/notes") || path.startsWith("/lms") ? "local" : path.startsWith("/jira") || path.startsWith("/issues") ? "jira" : path.startsWith("/cliq") ? "cliq" : path.startsWith("/roadmap") ? "roadmap" : path.startsWith("/codebase") ? "codebase" : "overview";
  const [scope, setScope] = useState(defaultScope);
  useEffect(() => setScope(defaultScope), [defaultScope]);
  const pulse = buildPulse(standup, name);

  function closeSearch() {
    setOpen(false);
  }

  async function ask(event: React.FormEvent) {
    event.preventDefault();
    const q = query.trim();
    if (!q) return;
    const key = q.match(/^\s*([A-Z][A-Z0-9]+-\d+)\s*$/i);
    if (key) {
      setOpen(false);
      router.push(`/issues/${key[1].toUpperCase()}`);
      return;
    }
    setBusy(true);
    setAnswer("");
    setHits([]);
    setSearched(null);
    setOpen(true);
    try {
      const result = await api.ask(q);
      setAnswer(result.answer);
      setHits(asItems(result.items));
      setSearched(typeof result.searched === "number" ? result.searched : null);
    } catch (err) {
      setAnswer(String(err));
    } finally {
      setBusy(false);
    }
  }

  const stale = Boolean(health.last_run_stale);
  const ageLabel = formatAge(health.last_run_age_seconds);
  const llmOff = Boolean(standup && standup.llm_used === false);

  return (
    <>
      <Box
        component="header"
        className="pulse"
        sx={{
          px: { xs: 2, md: 3, xl: 4 },
          py: 1.5,
          borderBottom: `1px solid ${apple.hairline}`,
          bgcolor: apple.page,
          backdropFilter: home ? "none" : "saturate(180%) blur(20px)",
          WebkitBackdropFilter: home ? "none" : "saturate(180%) blur(20px)",
          position: "sticky",
          top: 0,
          zIndex: 8,
        }}
      >
        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: {
              xs: "minmax(0, 1fr) auto",
              md: "minmax(120px, 1fr) minmax(200px, 380px) minmax(220px, 1fr)",
            },
            columnGap: 2,
            rowGap: 1.25,
            alignItems: "center",
          }}
        >
          <Box sx={{ minWidth: 0, gridColumn: { xs: "1 / -1", md: "auto" } }}>
            <Typography component="h1" sx={{ fontSize: 19, fontWeight: 650, letterSpacing: "-0.025em", m: 0 }}>{moduleTitle}</Typography>
          </Box>
          <Button variant="outlined" onClick={() => setOpen(true)} startIcon={<SearchRoundedIcon />} aria-label="Search workspace" sx={{ justifyContent: "flex-start", bgcolor: apple.page, color: apple.muted, borderColor: apple.hairline, borderRadius: "12px", fontWeight: 400, minWidth: 0, "&:hover": { bgcolor: apple.hoverFill, borderColor: "#c7c7cc" } }}>
            <Box component="span" sx={{ display: { xs: "none", sm: "inline" } }}>Search workspace…</Box><Box component="span" sx={{ display: { xs: "inline", sm: "none" } }}>Search</Box><Box component="kbd" sx={{ display: { xs: "none", sm: "inline" }, ml: "auto", pl: 2, fontSize: 11, whiteSpace: "nowrap" }}>⌘ K</Box>
          </Button>
          <Stack direction="row" justifyContent="flex-end" alignItems="center" spacing={1}>
            <Box sx={{ textAlign: "right", minWidth: 0, maxWidth: { xs: 120, sm: 160 } }}>
              <Typography role="status" title={message || ""} sx={{ fontSize: 11, whiteSpace: "nowrap", textOverflow: "ellipsis", overflow: "hidden", color: stale ? apple.danger : apple.muted }}>{message || (ageLabel ? `Updated ${ageLabel}` : "Not synced yet")}</Typography>
              <TextField select variant="standard" value={scope} onChange={(e) => setScope(e.target.value)} disabled={refreshing} slotProps={{ htmlInput: { "aria-label": "Refresh scope" } }} sx={{ "& .MuiInputBase-root": {fontSize:11}, "&:before":{display:"none"} }}>
                <MenuItem value="local">Reload this view</MenuItem><MenuItem value="overview">Overview only</MenuItem><MenuItem value="jira">Jira only</MenuItem><MenuItem value="cliq">Cliq only</MenuItem><MenuItem value="roadmap">Roadmap only</MenuItem><MenuItem value="codebase">Code index only</MenuItem><MenuItem value="all">All integrations</MenuItem>
              </TextField>
            </Box>
            <PillButton variant="gray" type="button" startIcon={<RefreshRoundedIcon className={refreshing ? "sync-spinning" : undefined} />} onClick={() => refreshAll(scope === "all" ? undefined : scope)} disabled={refreshing || busy} title={`Refresh ${scope}`}>
              {refreshing ? "Refreshing…" : "Refresh"}
            </PillButton>
          </Stack>
        </Box>
        {refreshing ? <LinearProgress aria-label="Refreshing workspace" sx={{ position: "absolute", bottom: 0, left: 0, right: 0 }} /> : null}
      </Box>

      {llmOff || health.dead_letter ? (
        <Box sx={{ px: { xs: 2, md: 3, xl: 4 }, pt: 2 }}>
          {message ? (
            <Typography sx={{ mb: llmOff || health.dead_letter ? 1.5 : 0, fontSize: 13, color: apple.muted }} role="status">{message}</Typography>
          ) : null}
          {llmOff ? (
            <Banner severity="warning">Standup built from rules — LLM unavailable{standup?.now_label ? ` at ${standup.now_label}` : ""}.</Banner>
          ) : null}
          {health.dead_letter ? <Banner severity="error">Scheduled standup failed after retries. Use Refresh.</Banner> : null}
        </Box>
      ) : null}

      <AppDialog open={open} onClose={closeSearch} title="Search workspace" titleId="workspace-search-title">
          <Box component="form" onSubmit={ask} sx={{ display: "flex", gap: 1, mt: 1, mb: 2 }}>
            <TextField disabled={busy} autoFocus inputRef={searchRef} value={query} onChange={(event) => { setQuery(event.target.value); setAnswer(""); setHits([]); setSearched(null); }} placeholder="Ticket key, person, or question…" slotProps={{ htmlInput: { "aria-label": "Search query" } }} size="small" fullWidth />
            <PillButton type="submit" disabled={busy || !query.trim()}>Search</PillButton>
          </Box>
          {busy ? <LinearProgress aria-label="Searching tickets" sx={{ mb: 2 }} /> : null}
          {!busy && !answer && !hits.length ? <Box sx={{ mb: 2 }}>
            <Typography className="nav-group">Jump to</Typography>
            {LINKS.filter((link) => !query.trim() || `${link.label} ${link.group}`.toLowerCase().includes(query.trim().toLowerCase())).map(({ href, label, Icon, group }) => <Button key={href} fullWidth onClick={() => { setOpen(false); router.push(href); }} startIcon={<Icon />} sx={{ justifyContent: "flex-start", borderRadius: "10px", px: 1.5, py: 1, color: apple.text }}>
              {label}<Typography component="span" sx={{ ml: "auto", fontSize: 11, color: apple.muted }}>{group}</Typography>
            </Button>)}
            {!query.trim() || "copilot chat".includes(query.trim().toLowerCase()) ? (
              <Button fullWidth onClick={() => { setOpen(false); openCopilot(); }} startIcon={<AutoAwesomeOutlinedIcon />} sx={{ justifyContent: "flex-start", borderRadius: "10px", px: 1.5, py: 1, color: apple.text }}>
                Copilot<Typography component="span" sx={{ ml: "auto", fontSize: 11, color: apple.muted }}>Chat</Typography>
              </Button>
            ) : null}
            <Typography sx={{ mt: 2, fontSize: 12, color: apple.muted }}>Enter a ticket key to open it, or search across your indexed work. Press Esc to close.</Typography>
          </Box> : null}
          {answer ? <Typography sx={{ fontSize: 15, mb: hits.length || searched != null ? 1.5 : 0 }}>{answer}</Typography> : null}
          {searched != null ? (
            <Typography sx={{ mb: 1, fontSize: 13, color: apple.muted }}>Searched {searched} tickets.</Typography>
          ) : null}
          {hits.length ? (
            <Box component="ul" sx={{ listStyle: "none", m: 0, p: 0 }}>
              {hits.slice(0, 8).map((item, index) => {
                const key = item.issue_key;
                return (
                  <Box component="li" key={`${key || item.title || index}`} sx={{ fontSize: 15, color: apple.text, mb: 1.25 }}>
                    {key ? <TicketLink issueKey={key} onClick={closeSearch} /> : null}
                    {key ? " · " : ""}
                    {item.title || item.body || item.action}
                    {item.why ? (
                      <Box component="span" sx={{ color: apple.muted }}>
                        {" "}
                        — {item.why}
                      </Box>
                    ) : null}
                    {item.snippet ? (
                      <Typography sx={{ mt: 0.5, fontSize: 13, color: apple.muted }}>{item.snippet}</Typography>
                    ) : null}
                  </Box>
                );
              })}
            </Box>
          ) : null}
      </AppDialog>
    </>
  );
}
