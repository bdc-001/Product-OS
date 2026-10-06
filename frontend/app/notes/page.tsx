"use client";

import AddRoundedIcon from "@mui/icons-material/AddRounded";
import ChevronLeftRoundedIcon from "@mui/icons-material/ChevronLeftRounded";
import ChevronRightRoundedIcon from "@mui/icons-material/ChevronRightRounded";
import DeleteOutlineRoundedIcon from "@mui/icons-material/DeleteOutlineRounded";
import { Collapse, IconButton, Skeleton, Tooltip, Menu } from "@mui/material";
import Box from "@mui/material/Box";
import MenuItem from "@mui/material/MenuItem";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useRefresh } from "@/app/refresh";
import { useCopilot } from "@/app/copilot/context";
import { api, type DailyNote, type NoteBlock } from "@/lib/api";
import { Banner, EmptyState, PillButton, Segmented, StatusChip } from "@/app/ui";
import { apple, radius } from "@/app/ui/tokens";
import { singleFlight } from "@/lib/single-flight";
import { NotePad } from "./pad";
import { KIND_LABEL, NOTE_KINDS, draftFromNote, emptyDraft, previewText, todayIst, type NoteDraft, type NoteKind } from "./model";

function formatDay(day: string) {
  const date = new Date(`${day}T12:00:00`);
  if (Number.isNaN(date.getTime())) return day;
  return date.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });
}

function NoteListCard({
  selected,
  disabled,
  onClick,
  onDelete,
  chips,
  title,
  preview,
}: {
  selected: boolean;
  disabled?: boolean;
  onClick: () => void;
  onDelete?: () => void;
  chips: ReactNode;
  title: string;
  preview: string;
}) {
  return (
    <Box
      sx={{
        position: "relative",
        mb: 1,
        "&:hover .note-list-delete": { opacity: 1, pointerEvents: "auto" },
      }}
    >
      <Box
        component="button"
        type="button"
        disabled={disabled}
        onClick={onClick}
        aria-pressed={selected}
        sx={{
          display: "flex",
          flexDirection: "column",
          alignItems: "flex-start",
          gap: 0.6,
          width: "100%",
          textAlign: "left",
          appearance: "none",
          WebkitAppearance: "none",
          border: `1px solid ${selected ? apple.ink : apple.hairline}`,
          bgcolor: selected ? apple.selFill : apple.page,
          borderRadius: `${radius.lg}px`,
          px: 1.5,
          pr: onDelete ? 4.5 : 1.5,
          py: 1.25,
          cursor: disabled ? "not-allowed" : "pointer",
          font: "inherit",
          color: "inherit",
          boxSizing: "border-box",
          transition: `border-color 0.2s ${apple.smooth}, background-color 0.2s ${apple.smooth}`,
          "&:hover": { bgcolor: selected ? apple.selFill : apple.hoverFill },
          "&:disabled": { opacity: 0.55 },
          overflowWrap: "anywhere",
        }}
      >
        <Box sx={{ display: "flex", gap: 0.75, flexWrap: "wrap" }}>{chips}</Box>
        <Typography sx={{ fontSize: 14, fontWeight: 650, lineHeight: 1.35 }}>{title}</Typography>
        <Typography
          sx={{
            fontSize: 12,
            color: apple.muted,
            lineHeight: 1.45,
            display: "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
          }}
        >
          {preview}
        </Typography>
      </Box>
      {onDelete ? (
        <Tooltip title="Delete note">
          <IconButton
            className="note-list-delete"
            size="small"
            aria-label="Delete note"
            disabled={disabled}
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              onDelete();
            }}
            sx={{
              position: "absolute",
              top: 6,
              right: 4,
              opacity: { xs: 1, md: 0 },
              pointerEvents: { xs: "auto", md: "none" },
              color: apple.muted,
              "&:hover": { color: apple.danger, bgcolor: apple.dangerFill },
            }}
          >
            <DeleteOutlineRoundedIcon sx={{ fontSize: 18 }} />
          </IconButton>
        </Tooltip>
      ) : null}
    </Box>
  );
}

export default function NotesPage() {
  const { tick } = useRefresh();
  const { open } = useCopilot();
  const [rows, setRows] = useState<DailyNote[]>([]);
  const [draft, setDraft] = useState<NoteDraft>(emptyDraft("meeting"));
  const [id, setId] = useState<number>();
  const [q, setQ] = useState("");
  const [kind, setKind] = useState<"all" | "actionable" | NoteKind>("all");
  const [dayFilter, setDayFilter] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [listCollapsed, setListCollapsed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [assistMenu, setAssistMenu] = useState<HTMLElement | null>(null);
  const [noteMenu, setNoteMenu] = useState<HTMLElement | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailFailed, setDetailFailed] = useState(false);
  const saveFlight = useRef<Promise<number | undefined> | null>(null);
  const selectionGen = useRef(0);
  const saveGen = useRef(0);
  const draftRef = useRef(draft);
  const idRef = useRef(id);
  draftRef.current = draft;
  idRef.current = id;

  useEffect(() => {
    try {
      setListCollapsed(window.localStorage.getItem("pm-notes-list-collapsed") === "1");
    } catch {
      /* ignore */
    }
  }, []);

  function toggleList() {
    setListCollapsed((value) => {
      const next = !value;
      try {
        window.localStorage.setItem("pm-notes-list-collapsed", next ? "1" : "0");
      } catch {
        /* ignore */
      }
      return next;
    });
  }

  function kindParam() {
    return kind === "all" ? "" : kind;
  }

  function load() {
    return api.notes(q, 0, kindParam(), dayFilter).then((data) => {
      setRows(data.notes);
      setTotal(data.total);
      return data;
    }).catch((err) => {
      setError(String(err));
      return null;
    });
  }

  useEffect(() => {
    let active = true;
    setLoading(true);
    const timer = setTimeout(() => {
      api.notes(q, 0, kindParam(), dayFilter).then((data) => {
        if (!active) return;
        setRows(data.notes);
        setTotal(data.total);
      }).catch((err) => active && setError(String(err))).finally(() => { if (active) setLoading(false); });
    }, 200);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [q, kind, dayFilter, tick]);

  useEffect(() => {
    const wanted = Number(new URLSearchParams(window.location.search).get("note"));
    if (!wanted) return;
    let active = true;
    const generation = ++selectionGen.current;
    setDetailLoading(true);
    api.note(wanted).then((row) => {
      if (!active || generation !== selectionGen.current) return;
      idRef.current = row.id; setId(row.id); setDraft(draftFromNote(row));
      if (window.matchMedia("(max-width: 899px)").matches) setListCollapsed(true);
    }).catch((err) => { if (active && generation === selectionGen.current) { setError(String(err)); setDetailFailed(true); } }).finally(() => { if (active && generation === selectionGen.current) setDetailLoading(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    const handler = (event: BeforeUnloadEvent) => {
      if (dirty) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);

  function isBlank(note: NoteDraft) {
    return !note.title.trim() && note.blocks.every((item) => !item.text.trim());
  }

  function patch(next: Partial<NoteDraft>) {
    setDraft((current) => ({ ...current, ...next }));
    setDirty(true);
    setStatus("");
    setError("");
  }

  function select(row?: DailyNote) {
    if (saveFlight.current || busy) return;
    if (dirty && !window.confirm("Discard unsaved changes to this note?")) return;
    const generation = ++selectionGen.current;
    if (window.matchMedia("(max-width: 899px)").matches) setListCollapsed(true);
    setDetailFailed(false);
    setDirty(false);
    setStatus("");
    setError("");
    if (!row) {
      idRef.current = undefined;
      setId(undefined);
      setDetailLoading(false);
      setDraft(emptyDraft(kind === "all" || kind === "actionable" ? "meeting" : kind));
      return;
    }
    idRef.current = row.id;
    setId(row.id);
    setDetailLoading(true);
    setDraft(draftFromNote(row));
    api.note(row.id).then((full) => {
      if (generation !== selectionGen.current) return;
      setDraft(draftFromNote(full));
    }).catch((err) => { if (generation === selectionGen.current) { setDetailFailed(true); setError(String(err)); } }).finally(() => { if (generation === selectionGen.current) setDetailLoading(false); });
  }

  async function persist(current = draftRef.current, currentId = idRef.current) {
    if (!current.day || isBlank(current)) return currentId;
    const title = current.title.trim() || (current.kind === "meeting" ? "Untitled meeting" : "Untitled note");
    setBusy("save");
    setError("");
    const gen = ++saveGen.current;
    try {
      const row = await api.saveNote(
        { day: current.day, title, body: current.body, learning: current.learning, kind: current.kind, blocks: current.blocks, tags: current.tags },
        currentId,
      );
      if (gen !== saveGen.current) return row.id;
      const latest = draftRef.current;
      const editedWhileSaving =
        latest.kind !== current.kind ||
        latest.day !== current.day ||
        latest.title !== current.title ||
        JSON.stringify(latest.blocks) !== JSON.stringify(current.blocks);
      idRef.current = row.id;
      setId(row.id);
      if (!editedWhileSaving) {
        setDraft((existing) => ({ ...existing, title: existing.title.trim() ? existing.title : row.title }));
        setDirty(false);
      }
      setStatus("Saved");
      await load();
      return row.id;
    } catch (err) {
      if (gen === saveGen.current) setError(String(err));
      return undefined;
    } finally {
      if (gen === saveGen.current) setBusy("");
    }
  }

  function save() {
    return singleFlight(saveFlight, () => persist());
  }

  useEffect(() => {
    if (!dirty || busy || error || detailLoading || detailFailed) return;
    if (isBlank(draft)) return;
    const timer = window.setTimeout(() => {
      void save();
    }, 900);
    return () => window.clearTimeout(timer);
  }, [draft, dirty, busy, error, detailLoading, detailFailed]);

  async function runAssist(action: "summarize" | "structure" | "extract") {
    setBusy(action);
    setError("");
    try {
      const result = await api.assistNote({ action, title: draft.title, body: draft.body, learning: draft.learning, blocks: draft.blocks });
      patch({ title: result.title || draft.title, blocks: result.blocks });
      setStatus(result.llm_used ? "Structured with AI" : "Structured locally — AI unavailable");
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy("");
    }
  }

  async function createTicket(block: NoteBlock) {
    const noteId = dirty ? await save() : id;
    if (!noteId) return;
    open({
      note: noteId,
      prompt: "Create a Jira ticket from this action item in the configured project. Nothing is written until I Approve.",
      notes: block.text.trim(),
    });
  }

  async function exportPdf() {
    const noteId = dirty ? await save() : id;
    if (!noteId) return;
    window.open(api.notePdfUrl(noteId), "_blank", "noopener,noreferrer");
  }

  async function removeNote(noteId = id) {
    if (!noteId) {
      select();
      return;
    }
    if (!window.confirm("Delete this note? This cannot be undone.")) return;
    saveGen.current += 1;
    setBusy("delete");
    setError("");
    try {
      await api.deleteNote(noteId);
      if (idRef.current === noteId) {
        setId(undefined);
        setDraft(emptyDraft(kind === "all" || kind === "actionable" ? "meeting" : kind));
        setDirty(false);
      }
      setStatus("Deleted");
      await load();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy("");
    }
  }

  const groups = useMemo(() => {
    const map = new Map<string, DailyNote[]>();
    for (const row of rows) {
      const list = map.get(row.day) || [];
      list.push(row);
      map.set(row.day, list);
    }
    return [...map.entries()];
  }, [rows]);

  const openActions = draft.blocks.filter((item) => item.type === "actionable" && !item.done).length;
  const locked = (Boolean(busy) && busy !== "save") || detailLoading || detailFailed;
  const assistDisabled = Boolean(busy) || locked || draft.blocks.every((item) => !item.text.trim());

  return (
    <Box
      sx={{
        flex: 1,
        minHeight: 0,
        height: { xs: "auto", md: "100%" },
        display: "grid",
        gridTemplateColumns: { xs: "1fr", md: listCollapsed ? "56px minmax(0,1fr)" : "280px minmax(0,1fr)" },
        overflow: { xs: "visible", md: "hidden" },
        transition: `grid-template-columns 0.3s ${apple.smooth}`,
      }}
    >
      <Box
        component="nav"
        aria-label="Notes list"
        sx={{
          display: { xs: listCollapsed ? "none" : "block", md: "flex" },
          flexDirection: "column",
          alignSelf: "stretch",
          minHeight: 0,
          height: {xs:"auto",md:"100%"},
          overflow: {xs:"auto",md:"hidden"},
          borderRight: { md: "1px solid" },
          borderRightColor: { md: "divider" },
          borderBottom: { xs: "1px solid", md: 0 },
          borderBottomColor: { xs: "divider" },
          bgcolor: apple.page,
          maxHeight: { xs: "55vh", md: "none" },
        }}
      >
        {listCollapsed ? (
          <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 0.5, py: 1.5 }}>
            <Tooltip title="Show notes list" placement="right">
              <IconButton aria-label="Show notes list" onClick={toggleList} size="small">
                <ChevronRightRoundedIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title="New note" placement="right">
              <IconButton aria-label="New note" onClick={() => select()} disabled={Boolean(busy)} size="small">
                <AddRoundedIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
        ) : (
          <Box sx={{ px: 2, py: 1.5, borderBottom: "1px solid", borderColor: "divider", display: "flex", alignItems: "center", gap: 1 }}>
            <Typography variant="overline" color="text.secondary" sx={{ flex: 1, px: 0.5, lineHeight: 1.2 }}>
              Library
            </Typography>
            <Tooltip title="Hide notes list">
              <IconButton aria-label="Hide notes list" onClick={toggleList} size="small">
                <ChevronLeftRoundedIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
        )}
        {listCollapsed ? null : (
          <>
          <Box sx={{ px: 1.5, pt: 1.5, pb: 1.25, borderBottom: `1px solid ${apple.hairline}` }}>
            <PillButton fullWidth onClick={() => select()} disabled={Boolean(busy)}>
              New note
            </PillButton>
          </Box>
          <Box sx={{ px: 1.5, py: 1.25, borderBottom: `1px solid ${apple.hairline}`, display: "flex", flexDirection: "column", gap: 1.25 }}>
            <TextField size="small" fullWidth label="Search your notes" value={q} onChange={(event) => setQ(event.target.value)} />
            <TextField
              select
              size="small"
              fullWidth
              label="Show"
              value={kind}
              onChange={(event) => setKind(event.target.value as typeof kind)}
            >
              {NOTE_KINDS.map((item) => (
                <MenuItem key={item.id} value={item.id}>
                  {item.label}
                </MenuItem>
              ))}
            </TextField>
            <PillButton variant="text" onClick={() => setFiltersOpen(value => !value)} aria-expanded={filtersOpen}>{filtersOpen ? "Hide date filter" : dayFilter ? `Date: ${dayFilter}` : "Filter by date"}</PillButton>
            <Collapse in={filtersOpen}><TextField
              size="small"
              fullWidth
              type="date"
              label="On date"
              value={dayFilter}
              onChange={(event) => setDayFilter(event.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
              helperText={dayFilter ? "Showing that day only." : "Leave blank for all dates."}
            />
            </Collapse>
            <Typography variant="caption" color="text.secondary">{loading ? "Finding notes…" : `${total} ${total === 1 ? "note" : "notes"}`}</Typography>
            {dayFilter ? (
              <PillButton variant="text" type="button" onClick={() => setDayFilter("")}>
                All dates
              </PillButton>
            ) : null}
          </Box>
          <Box sx={{ flex: 1, minHeight: 0, overflow: "auto", px: 1.5, py: 1.5 }}>
            {loading && !rows.length && [0, 1, 2].map(n => <Skeleton key={n} height={90}/>)}
            {groups.map(([day, items]) => (
              <Box key={day} sx={{ mb: 1.5 }}>
                <Typography
                  sx={{
                    px: 0.5,
                    mb: 1,
                    fontSize: 11,
                    fontWeight: 700,
                    letterSpacing: "0.08em",
                    textTransform: "uppercase",
                    color: apple.muted,
                  }}
                >
                  {formatDay(day)}
                </Typography>
                {kind === "actionable"
                  ? items.flatMap((row) =>
                      (row.blocks || [])
                        .filter((block) => block.type === "actionable")
                        .map((block) => (
                          <NoteListCard
                            key={`${row.id}-${block.id}`}
                            selected={id === row.id}
                            disabled={Boolean(busy) || detailLoading}
                            onClick={() => select(row)}
                            onDelete={row.id ? () => void removeNote(row.id) : undefined}
                            chips={
                              <>
                                <StatusChip label={block.done ? "Done" : "Open"} tone={block.done ? "default" : "ink"} />
                                {block.ticket_key ? <StatusChip label={block.ticket_key} /> : null}
                              </>
                            }
                            title={block.text || "Untitled follow-up"}
                            preview={row.title || "Untitled note"}
                          />
                        )),
                    )
                  : items.map((row) => (
                      <NoteListCard
                        key={row.id}
                        selected={id === row.id}
                        disabled={Boolean(busy) || detailLoading}
                        onClick={() => select(row)}
                        onDelete={row.id ? () => void removeNote(row.id) : undefined}
                        chips={
                          <>
                            <StatusChip label={KIND_LABEL[(row.kind as NoteKind) || "daily"]} />
                            {(row.actionable_count || 0) > 0 ? <StatusChip label={`${row.actionable_count} open`} tone="ink" /> : null}
                          </>
                        }
                        title={row.title || "Untitled"}
                        preview={previewText(row).slice(0, 120) || "Empty note"}
                      />
                    ))}
              </Box>
            ))}
            {!loading && !rows.length ? <EmptyState>{q || kind !== "all" || dayFilter ? "No notes match these filters." : "Start a meeting note, or dump the day and Structure it."}</EmptyState> : null}
            {rows.length < total ? (
              <Box sx={{ pt: 0.5 }}>
                <PillButton variant="gray" fullWidth onClick={() => api.notes(q, rows.length, kindParam(), dayFilter).then((data) => setRows((current) => [...current, ...data.notes])).catch((err) => setError(String(err)))}>
                  Load more
                </PillButton>
              </Box>
            ) : null}
          </Box>
          </>
        )}
      </Box>

      <Box sx={{ minWidth: 0, display: "flex", flexDirection: "column", minHeight: 0, height: { md: "100%" }, overflow: "hidden" }}>
        {listCollapsed ? (
          <Box sx={{ display: { xs: "flex", md: "none" }, px: 2, py: 1, borderBottom: `1px solid ${apple.hairline}` }}>
            <PillButton variant="text" onClick={toggleList}>Show notes list</PillButton>
          </Box>
        ) : null}
        {error ? <Box sx={{ px: 2, pt: 2 }}><Banner severity="error">{error}</Banner></Box> : null}
        <Box
          sx={{
            px: 2.5,
            py: 1.5,
            borderBottom: `1px solid ${apple.hairline}`,
            display: "flex",
            alignItems: "center",
            gap: 2,
            flexWrap: "wrap",
          }}
        >
          <Box sx={{ flex: 1, minWidth: 240, maxWidth: 420 }}>
            <Segmented
              value={draft.kind}
              onChange={(next) => {
                if (locked) return;
                if (next === "meeting" || next === "daily" || next === "decision" || next === "learning") patch({ kind: next });
              }}
              options={[
                { id: "meeting", label: "Meeting" },
                { id: "daily", label: "Daily" },
                { id: "decision", label: "Decision" },
                { id: "learning", label: "Learning" },
              ]}
            />
          </Box>
          <TextField
            label="Date"
            type="date"
            size="small"
            value={draft.day}
            disabled={Boolean(busy)}
            onChange={(event) => patch({ day: event.target.value || todayIst() })}
            slotProps={{ inputLabel: { shrink: true } }}
            sx={{ width: 168, ml: { md: "auto" } }}
          />
          <PillButton variant="text" disabled={Boolean(busy) || detailLoading} onClick={event => setNoteMenu(event.currentTarget)} aria-haspopup="menu" aria-expanded={Boolean(noteMenu)}>More</PillButton>
          <Menu anchorEl={noteMenu} open={Boolean(noteMenu)} onClose={() => setNoteMenu(null)}>
            <MenuItem disabled={Boolean(busy) || isBlank(draft) || detailFailed} onClick={() => { setNoteMenu(null); void exportPdf(); }}>Export PDF</MenuItem>
            <MenuItem disabled={Boolean(busy) || (!id && isBlank(draft))} onClick={() => { setNoteMenu(null); void removeNote(); }} sx={{ color: "error.main" }}>Delete note</MenuItem>
          </Menu>
        </Box>
        <Box
          sx={{
            px: 2.5,
            py: 1.25,
            borderBottom: `1px solid ${apple.hairline}`,
            bgcolor: apple.hoverFill,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 1.5,
            flexWrap: "wrap",
          }}
        >
          <Box>
            <PillButton variant="text" disabled={assistDisabled} aria-haspopup="menu" aria-expanded={Boolean(assistMenu)} onClick={event => setAssistMenu(event.currentTarget)}>{["structure","summarize","extract"].includes(busy) ? "Working…" : "Writing tools"}</PillButton>
            <Menu anchorEl={assistMenu} open={Boolean(assistMenu)} onClose={() => setAssistMenu(null)}>
              {([["structure", "Organize notes"], ["summarize", "Summarize"], ["extract", "Find action items"]] as const).map(([action, label]) => <MenuItem key={action} onClick={() => { setAssistMenu(null); void runAssist(action); }}>{label}</MenuItem>)}
            </Menu>
          </Box>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, ml: "auto", flexWrap: "wrap" }}>
            <Typography role="status" sx={{ fontSize: 12, color: apple.muted, flexShrink: 0 }}>
              {busy === "save" ? "Saving…" : busy === "delete" ? "Deleting…" : dirty ? error ? "Not saved" : "Unsaved changes" : status || "Autosaves as you write"}
              {openActions ? ` · ${openActions} open` : ""}
            </Typography>
            {dirty && <PillButton variant="gray" type="button" disabled={Boolean(busy) || locked || isBlank(draft)} onClick={() => void save()}>Save now</PillButton>}
          </Box>
        </Box>
        <Box sx={{ flex: 1, minHeight: 0, overflow: "auto", px: { xs: 2, md: 3 }, py: { xs: 2, md: 2.5 } }}>
          {detailLoading ? <Box role="status" aria-label="Opening note"><Skeleton height={60}/><Skeleton height={160}/></Box> : detailFailed ? <EmptyState>Could not open this note. <PillButton variant="text" onClick={() => { const row = rows.find(item => item.id === id); if (row) select(row); else select(); }}>Try again</PillButton></EmptyState> : <Box sx={{ maxWidth: 820, mx: "auto" }}><NotePad draft={draft} busy={locked} onChange={patch} onTicket={(block) => void createTicket(block)} /></Box>}
        </Box>
      </Box>
    </Box>
  );
}
