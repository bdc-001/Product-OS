"use client";

import Box from "@mui/material/Box";
import MenuItem from "@mui/material/MenuItem";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useRefresh } from "@/app/refresh";
import { useCopilot } from "@/app/copilot/context";
import { api, type DailyNote, type NoteBlock } from "@/lib/api";
import { Banner, EmptyState, FrostCard, PageBody, PageHeader, PillButton, Segmented, StatusChip } from "@/app/ui";
import { apple, radius } from "@/app/ui/tokens";
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
  chips,
  title,
  preview,
}: {
  selected: boolean;
  disabled?: boolean;
  onClick: () => void;
  chips: ReactNode;
  title: string;
  preview: string;
}) {
  return (
    <Box
      component="button"
      type="button"
      disabled={disabled}
      onClick={onClick}
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
        py: 1.25,
        mb: 1,
        cursor: disabled ? "not-allowed" : "pointer",
        font: "inherit",
        color: "inherit",
        boxSizing: "border-box",
        transition: `border-color 0.2s ${apple.smooth}, background-color 0.2s ${apple.smooth}`,
        "&:hover": { bgcolor: selected ? apple.selFill : apple.hoverFill },
        "&:disabled": { opacity: 0.55 },
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
  const [total, setTotal] = useState(0);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const saveGen = useRef(0);
  const draftRef = useRef(draft);
  const idRef = useRef(id);
  draftRef.current = draft;
  idRef.current = id;

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
    const timer = setTimeout(() => {
      api.notes(q, 0, kindParam(), dayFilter).then((data) => {
        if (!active) return;
        setRows(data.notes);
        setTotal(data.total);
      }).catch((err) => active && setError(String(err)));
    }, 200);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [q, kind, dayFilter, tick]);

  useEffect(() => {
    const wanted = Number(new URLSearchParams(window.location.search).get("note"));
    if (!wanted) return;
    api.note(wanted).then((row) => {
      setId(row.id);
      setDraft(draftFromNote(row));
    }).catch((err) => setError(String(err)));
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
  }

  function select(row?: DailyNote) {
    if (dirty && !window.confirm("Discard unsaved changes to this note?")) return;
    setId(row?.id);
    setDraft(row ? draftFromNote(row) : emptyDraft(kind === "all" || kind === "actionable" ? "meeting" : kind));
    setDirty(false);
    setStatus("");
    setError("");
  }

  async function save(current = draftRef.current, currentId = idRef.current) {
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
      return currentId;
    } finally {
      if (gen === saveGen.current) setBusy("");
    }
  }

  useEffect(() => {
    if (!dirty) return;
    if (isBlank(draft)) return;
    const timer = window.setTimeout(() => {
      void save();
    }, 900);
    return () => window.clearTimeout(timer);
  }, [draft, dirty]);

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
    open({
      note: noteId,
      prompt: "Create a Jira ticket from this actionable onto an existing AC epic. Nothing is written until I Approve.",
      notes: block.text.trim(),
    });
  }

  async function removeNote() {
    if (!id) {
      select();
      return;
    }
    if (!window.confirm("Delete this note? This cannot be undone.")) return;
    saveGen.current += 1;
    setBusy("delete");
    setError("");
    try {
      await api.deleteNote(id);
      setId(undefined);
      setDraft(emptyDraft(kind === "all" || kind === "actionable" ? "meeting" : kind));
      setDirty(false);
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
  const locked = Boolean(busy) && busy !== "save";
  const assistDisabled = locked || draft.blocks.every((item) => !item.text.trim());
  const paneSx = {
    p: 0,
    overflow: "hidden",
    display: "flex",
    flexDirection: "column",
    minHeight: { md: "calc(100dvh - 196px)" },
    maxHeight: { md: "calc(100dvh - 196px)" },
    height: { md: "calc(100dvh - 196px)" },
    "&:hover": { borderColor: apple.hairline },
  } as const;

  return (
    <PageBody wide>
      <PageHeader title="Notes" subtitle="Meetings, follow-ups, and decisions. File a ticket from an actionable when you are ready." />
      {error ? <Banner severity="error">{error}</Banner> : null}
      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "1fr", md: "320px minmax(0,1fr)" },
          gap: 2,
          alignItems: "stretch",
        }}
      >
        <FrostCard sx={paneSx}>
          <Box sx={{ px: 2, pt: 2, pb: 1.5, borderBottom: `1px solid ${apple.hairline}` }}>
            <PillButton fullWidth onClick={() => select()} disabled={Boolean(busy)}>
              New note
            </PillButton>
          </Box>
          <Box sx={{ px: 2, py: 1.5, borderBottom: `1px solid ${apple.hairline}`, display: "flex", flexDirection: "column", gap: 1.25 }}>
            <TextField size="small" fullWidth label="Search" value={q} onChange={(event) => setQ(event.target.value)} />
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
            <TextField
              size="small"
              fullWidth
              type="date"
              label="On date"
              value={dayFilter}
              onChange={(event) => setDayFilter(event.target.value)}
              slotProps={{ inputLabel: { shrink: true } }}
              helperText={dayFilter ? "Showing that day only." : "Leave blank for all dates."}
            />
            {dayFilter ? (
              <PillButton variant="text" type="button" onClick={() => setDayFilter("")}>
                All dates
              </PillButton>
            ) : null}
          </Box>
          <Box sx={{ flex: 1, minHeight: 0, overflow: "auto", px: 1.5, py: 1.5 }}>
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
                            disabled={locked}
                            onClick={() => select(row)}
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
                        disabled={locked}
                        onClick={() => select(row)}
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
            {!rows.length ? <EmptyState>{q || kind !== "all" || dayFilter ? "No notes in this filter." : "Start a meeting note, or dump the day and Structure it."}</EmptyState> : null}
            {rows.length < total ? (
              <Box sx={{ pt: 0.5 }}>
                <PillButton variant="gray" fullWidth onClick={() => api.notes(q, rows.length, kindParam(), dayFilter).then((data) => setRows((current) => [...current, ...data.notes])).catch((err) => setError(String(err)))}>
                  Load more
                </PillButton>
              </Box>
            ) : null}
          </Box>
        </FrostCard>

        <FrostCard sx={paneSx}>
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
            <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
              <PillButton variant="gray" type="button" disabled={assistDisabled} onClick={() => runAssist("structure")}>
                {busy === "structure" ? "Structuring…" : "Structure"}
              </PillButton>
              <PillButton variant="gray" type="button" disabled={assistDisabled} onClick={() => runAssist("summarize")}>
                {busy === "summarize" ? "Summarising…" : "Summarise"}
              </PillButton>
              <PillButton variant="gray" type="button" disabled={assistDisabled} onClick={() => runAssist("extract")}>
                {busy === "extract" ? "Extracting…" : "Extract"}
              </PillButton>
            </Box>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, ml: "auto" }}>
              <Typography role="status" sx={{ fontSize: 12, color: apple.muted, flexShrink: 0 }}>
                {busy === "save" ? "Saving…" : busy === "delete" ? "Deleting…" : dirty ? "Editing" : status || "Autosaves as you write"}
                {openActions ? ` · ${openActions} open` : ""}
              </Typography>
              <PillButton variant="gray" type="button" disabled={Boolean(busy)} onClick={() => void removeNote()}>
                Delete
              </PillButton>
            </Box>
          </Box>
          <Box sx={{ flex: 1, minHeight: 0, overflow: "auto", px: { xs: 2, md: 3 }, py: { xs: 2, md: 2.5 } }}>
            <NotePad draft={draft} busy={locked} onChange={patch} onTicket={(block) => void createTicket(block)} />
          </Box>
        </FrostCard>
      </Box>
    </PageBody>
  );
}
