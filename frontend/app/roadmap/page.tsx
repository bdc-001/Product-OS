"use client";

import Box from "@mui/material/Box";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@/app/ui/stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useEffect, useMemo, useRef, useState } from "react";
import { api, type Roadmap, type RoadmapAttachment, type RoadmapEpic, type RoadmapTicket } from "@/lib/api";
import { useRefresh } from "@/app/refresh";
import { useCopilot } from "@/app/copilot/context";
import { Banner, EmptyState, PageBody, PageHeader, PagedList, PillButton, RemoveButton, StatusChip, TicketLink } from "@/app/ui";
import { apple } from "@/app/theme";

function cloneRoadmap(row: Roadmap): Roadmap {
  return {
    ...row,
    epics: (row.epics || []).map((epic) => ({
      ...epic,
      tickets: (epic.tickets || []).map((ticket) => ({
        ...ticket,
        attachments: (ticket.attachments || []).map((item) => ({ ...item })),
      })),
    })),
  };
}

function ticketsInMonth(epic: RoadmapEpic, month: string, months: string[], currentMonth: string) {
  const current = currentMonth || months[1] || months[0];
  return (epic.tickets || []).filter((ticket) => {
    if (ticket.month === month) return true;
    if (!ticket.month && month === current) return true;
    if (ticket.month && !months.includes(ticket.month) && month === current) return true;
    return false;
  });
}

function milestoneFor(tickets: RoadmapTicket[]) {
  if (!tickets.length) return "";
  const done = tickets.find((ticket) => /done|released|closed/i.test(ticket.status || ""));
  const active = tickets.find((ticket) => /progress|review|uat/i.test(ticket.status || ""));
  const pick = done || active || tickets[0];
  return pick.summary || pick.key;
}

export default function RoadmapPage() {
  const [roadmap, setRoadmap] = useState<Roadmap | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");
  const [dirty, setDirty] = useState(false);
  const [dragging, setDragging] = useState<{ epic: string; key: string } | null>(null);
  const [compact, setCompact] = useState(true);
  const [monthFilter, setMonthFilter] = useState("all");
  const [epicFilter, setEpicFilter] = useState("all");
  const { tick } = useRefresh();
  const latest = useRef<Roadmap | null>(null);
  const persistSeq = useRef(0);
  const persistAgain = useRef(false);
  const saving = useRef(false);

  async function load() {
    const data = await api.roadmap();
    setRoadmap(data.roadmap);
    latest.current = data.roadmap;
    setDirty(false);
  }

  useEffect(() => {
    if (dirty) return;
    load().catch((err) => setError(String(err)));
  }, [tick]);

  function patch(next: Roadmap, markDirty = true) {
    setRoadmap(next);
    latest.current = next;
    if (markDirty) setDirty(true);
  }

  async function persist(next?: Roadmap) {
    if (next) {
      latest.current = next;
      setRoadmap(next);
      setDirty(true);
    }
    if (saving.current) {
      persistAgain.current = true;
      return;
    }
    saving.current = true;
    const seq = ++persistSeq.current;
    setBusy("save");
    setError("");
    try {
      do {
        persistAgain.current = false;
        const row = latest.current;
        if (!row) {
          persistAgain.current = false;
          return;
        }
        const savedRow = await api.saveRoadmap({ notes: row.notes, epics: row.epics });
        if (seq !== persistSeq.current) return;
        if (persistAgain.current || latest.current !== row) { persistAgain.current = true; continue; }
        setRoadmap(savedRow);
        latest.current = savedRow;
        setDirty(false);
        setSaved("Saved.");
      } while (persistAgain.current);
    } catch (err) {
      if (seq === persistSeq.current) setError(String(err));
    } finally {
      saving.current = false;
      if (seq === persistSeq.current) setBusy("");
      if (persistAgain.current) persist();
    }
  }

  async function generate() {
    setBusy("generate");
    setError("");
    setSaved("");
    try {
      const next = await api.generateRoadmap();
      setRoadmap(next);
      latest.current = next;
      setDirty(false);
      setSaved(next.llm_used ? "Placed from your Sense epics." : "Heuristic placement — LLM was not used.");
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy("");
    }
  }

  function updateEpics(mutate: (epics: RoadmapEpic[]) => RoadmapEpic[], saveNow = false) {
    const row = latest.current;
    if (!row) return;
    const next = cloneRoadmap(row);
    next.epics = mutate(next.epics);
    patch(next);
    if (saveNow) persist(next);
  }

  function moveTicket(epicKey: string, ticketKey: string, month: string) {
    updateEpics(
      (epics) =>
        epics.map((epic) =>
          epic.key !== epicKey
            ? epic
            : { ...epic, tickets: (epic.tickets || []).map((ticket) => (ticket.key === ticketKey ? { ...ticket, month } : ticket)) },
        ),
      true,
    );
  }

  const months = roadmap?.months || [];
  const labels = roadmap?.month_labels || [];
  const currentMonth = roadmap?.current_month || months[1] || months[0] || "";
  const visibleMonths = monthFilter === "all" ? months : months.filter((month) => month === monthFilter);
  const visibleEpics = useMemo(() => {
    const rows = roadmap?.epics || [];
    if (epicFilter === "all") return rows;
    return rows.filter((epic) => epic.key === epicFilter);
  }, [roadmap, epicFilter]);

  return (
    <PageBody wide>
      <div className="roadmap-shell">
        <PageHeader title={roadmap?.label || "Roadmap"} subtitle="Sense · AC · previous · this month · next" />
        {error ? <Banner severity="error">{error}</Banner> : null}

        <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap" alignItems="center" sx={{ mb: 2.5 }}>
          <PillButton variant={compact ? "filled" : "gray"} aria-pressed={compact} onClick={() => setCompact(value => !value)}>{compact ? "Headers only" : "Detailed view"}</PillButton>
          <PillButton onClick={generate} disabled={Boolean(busy)}>
            {busy === "generate" ? "Building from Jira…" : "Generate from my epics"}
          </PillButton>
          <PillButton variant="gray" onClick={() => persist()} disabled={!roadmap || !dirty || Boolean(busy)}>
            {busy === "save" ? "Saving…" : dirty ? "Save edits" : "Saved"}
          </PillButton>
          {saved ? (
            <Typography sx={{ fontSize: 15, color: apple.muted }}>{saved}</Typography>
          ) : (
            <Typography sx={{ fontSize: 15, color: apple.muted }}>
              Sense (AC) only. {labels[0] || "Last month"} behind, {labels[1] || "this month"} highlighted, {labels[2] || "next month"} left blank for you to fill.
            </Typography>
          )}
        </Stack>

        {roadmap ? (
          <>
            <TextField
              label="Window note"
              value={roadmap.notes || ""}
              onChange={(event) => patch({ ...roadmap, notes: event.target.value })}
              onBlur={() => persist()}
              multiline
              minRows={2}
              fullWidth
              sx={{ mb: 2 }}
            />

            <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} useFlexGap flexWrap="wrap" alignItems={{ md: "center" }} sx={{ mb: 2.5 }}>
              <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap" role="tablist">
                <Box
                  component="button"
                  type="button"
                  onClick={() => setMonthFilter("all")}
                  sx={tabSx(monthFilter === "all")}
                >
                  All months
                </Box>
                {months.map((month, index) => {
                  const count = (roadmap.epics || []).reduce((sum, epic) => sum + ticketsInMonth(epic, month, months, currentMonth).length, 0);
                  const isNow = month === currentMonth;
                  return (
                    <Box
                      key={month}
                      component="button"
                      type="button"
                      onClick={() => setMonthFilter(month)}
                      sx={tabSx(monthFilter === month, isNow)}
                    >
                      {labels[index] || month}
                      {isNow ? " · now" : ""} · {count}
                    </Box>
                  );
                })}
              </Stack>
              <TextField select size="small" label="Epic" value={epicFilter} onChange={(event) => setEpicFilter(event.target.value)} sx={{ minWidth: 220 }}>
                <MenuItem value="all">All epics</MenuItem>
                {(roadmap.epics || []).map((epic) => (
                  <MenuItem key={epic.key} value={epic.key}>
                    {epic.key} · {epic.title}
                  </MenuItem>
                ))}
              </TextField>
            </Stack>

            {visibleEpics.map((epic) => (
              <EpicBlock
                key={epic.key}
                epic={epic}
                compact={compact}
                months={months}
                labels={labels}
                visibleMonths={visibleMonths}
                currentMonth={currentMonth}
                monthFilter={monthFilter}
                dragging={dragging}
                setDragging={setDragging}
                onMonthFilter={setMonthFilter}
                onTitle={(title) => updateEpics((epics) => epics.map((row) => (row.key === epic.key ? { ...row, title } : row)))}
                onNote={(note) => updateEpics((epics) => epics.map((row) => (row.key === epic.key ? { ...row, note } : row)))}
                onBlurEpic={() => persist()}
                onMove={moveTicket}
                onPatchTicket={(ticketKey, fields, saveNow) =>
                  updateEpics(
                    (epics) =>
                      epics.map((row) =>
                        row.key !== epic.key
                          ? row
                          : {
                              ...row,
                              tickets: (row.tickets || []).map((ticket) => (ticket.key === ticketKey ? { ...ticket, ...fields } : ticket)),
                            },
                      ),
                    saveNow,
                  )
                }
                onSave={() => persist()}
                onRemove={(ticketKey) =>
                  updateEpics(
                    (epics) =>
                      epics.map((row) => (row.key !== epic.key ? row : { ...row, tickets: (row.tickets || []).filter((ticket) => ticket.key !== ticketKey) })),
                    true,
                  )
                }
              />
            ))}
            {!roadmap.epics.length ? <EmptyState>No Sense epics found for you yet. Generate after Jira is connected.</EmptyState> : null}
            {roadmap.epics.length && !visibleEpics.length ? <EmptyState>No epic matches this filter.</EmptyState> : null}
          </>
        ) : (
          <EmptyState>Generate a rolling roadmap from your Sense epics.</EmptyState>
        )}
      </div>
    </PageBody>
  );
}

function tabSx(on: boolean, now = false) {
  return {
    border: `1px solid ${on ? apple.ink : apple.hairline}`,
    bgcolor: on ? apple.ink : apple.page,
    color: on ? "#fff" : apple.text,
    px: 1.5,
    py: 0.85,
    borderRadius: "999px",
    cursor: "pointer",
    fontSize: 13,
    fontFamily: "inherit",
    fontWeight: 500,
    boxShadow: now && !on ? `0 0 0 2px ${apple.selFill}` : "none",
    transition: `background-color 0.3s ${apple.smooth}, color 0.3s ${apple.smooth}, transform 0.4s ${apple.pop}`,
  };
}

function EpicBlock({
  compact,
  epic,
  months,
  labels,
  visibleMonths,
  currentMonth,
  monthFilter,
  dragging,
  setDragging,
  onMonthFilter,
  onTitle,
  onNote,
  onBlurEpic,
  onMove,
  onPatchTicket,
  onSave,
  onRemove,
}: {
  compact: boolean;
  epic: RoadmapEpic;
  months: string[];
  labels: string[];
  visibleMonths: string[];
  currentMonth: string;
  monthFilter: string;
  dragging: { epic: string; key: string } | null;
  setDragging: (value: { epic: string; key: string } | null) => void;
  onMonthFilter: (month: string) => void;
  onTitle: (title: string) => void;
  onNote: (note: string) => void;
  onBlurEpic: () => void;
  onMove: (epicKey: string, ticketKey: string, month: string) => void;
  onPatchTicket: (ticketKey: string, fields: Partial<RoadmapTicket>, saveNow?: boolean) => void;
  onSave: () => void;
  onRemove: (ticketKey: string) => void;
}) {
  const tickets = epic.tickets || [];
  const titleRef = useRef<HTMLTextAreaElement>(null);
  const { open: openCopilot } = useCopilot();
  const [open, setOpen] = useState(true);
  const [monthOpen, setMonthOpen] = useState<Record<string, boolean>>({});
  const nextMonth = months[months.length - 1] || "";

  useEffect(() => {
    const node = titleRef.current;
    if (!node) return;
    node.style.height = "0px";
    node.style.height = `${node.scrollHeight}px`;
  }, [epic.title]);

  function isMonthOpen(month: string) {
    return monthOpen[month] !== false;
  }

  function toggleMonth(month: string) {
    setMonthOpen((prev) => ({ ...prev, [month]: prev[month] === false }));
  }

  return (
    <article className={`epic-block ${open ? "" : "closed"}`}>
      <div className="epic-intro">
        <div className="epic-head">
          <Typography sx={{ fontSize: 13, color: apple.muted }}>{epic.key}</Typography>
          <PillButton variant="gray" type="button" aria-expanded={open} onClick={() => setOpen((value) => !value)}>
            {open ? "Collapse epic" : "Expand epic"}
          </PillButton>
        </div>
        <textarea
          ref={titleRef}
          className="epic-title"
          rows={1}
          value={epic.title}
          onChange={(event) => onTitle(event.target.value)}
          onBlur={onBlurEpic}
        />
        {open ? (
          <textarea className="epic-note" value={epic.note || ""} placeholder="Epic intent this window" onChange={(event) => onNote(event.target.value)} onBlur={onBlurEpic} />
        ) : null}
        <Typography sx={{ mt: 1, fontSize: 13, color: apple.muted }}>
          {tickets.length === 1 ? "1 ticket" : `${tickets.length} tickets`}
          {epic.status ? ` · ${epic.status}` : ""}
          {!open
            ? ` · ${months
                .map((month, index) => `${labels[index] || month} ${ticketsInMonth(epic, month, months, currentMonth).length}`)
                .join(" · ")}`
            : ""}
        </Typography>
        <Box sx={{ mt: 1 }}>
          <PillButton
            variant="text"
            type="button"
            onClick={() =>
              openCopilot({
                epic: epic.key,
                notes: `File work for ${epic.key} ${epic.title || ""}. ${epic.note || ""}`.trim(),
              })
            }
          >
            File work for this epic
          </PillButton>
        </Box>
      </div>

      {open ? (
        <>
          {!compact ? <div className="mile-track">
            <div className="mile-line">
              <i />
            </div>
            <ol className="mile-nodes" style={{ gridTemplateColumns: `repeat(${Math.max(months.length, 1)}, minmax(0, 1fr))` }}>
              {months.map((month, index) => {
                const bucket = ticketsInMonth(epic, month, months, currentMonth);
                const mark = milestoneFor(bucket);
                const isNow = month === currentMonth;
                return (
                  <li
                    key={month}
                    style={{ animationDelay: `${index * 0.14}s` }}
                    className={`${isNow ? "now" : ""} ${monthFilter === month ? "on" : ""} ${bucket.length ? "" : "empty"}`}
                  >
                    <button type="button" onClick={() => onMonthFilter(monthFilter === month ? "all" : month)}>
                      <span className="mile-node" />
                      <strong>
                        {labels[index] || month}
                        {isNow ? " · now" : ""}
                      </strong>
                      <span>{bucket.length === 1 ? "1 ticket" : `${bucket.length} tickets`}</span>
                      {mark ? <span className="mile-mark">{mark}</span> : <span>{month === nextMonth ? "Yours to fill" : "No milestone"}</span>}
                    </button>
                  </li>
                );
              })}
            </ol>
          </div> : null}

          <div
            className="month-cols"
            style={{
              gridTemplateColumns: visibleMonths.map((month) => (isMonthOpen(month) ? "minmax(0, 1fr)" : "52px")).join(" ") || "1fr",
            }}
          >
            {visibleMonths.map((month) => {
              const index = months.indexOf(month);
              const bucket = ticketsInMonth(epic, month, months, currentMonth);
              const isNow = month === currentMonth;
              const isNext = month === nextMonth;
              const expanded = isMonthOpen(month);
              const label = labels[index] || month;
              return (
                <div
                  className={`month-col ${isNow ? "now" : ""} ${isNext ? "next" : ""} ${expanded ? "" : "closed"} ${dragging?.epic === epic.key ? "droppable" : ""}`}
                  key={`${epic.key}-${month}`}
                  onDragOver={(event) => event.preventDefault()}
                  onDrop={(event) => {
                    event.preventDefault();
                    if (dragging && dragging.epic === epic.key) onMove(epic.key, dragging.key, month);
                    setDragging(null);
                  }}
                >
                  {expanded ? (
                    <>
                      <div className="month-head">
                        <p className="month-label">
                          {label}
                          {isNow ? " · now" : ""}
                          {isNext ? " · add" : ""}
                        </p>
                        <PillButton variant="gray" type="button" aria-expanded={expanded} onClick={() => toggleMonth(month)}>
                          Collapse
                        </PillButton>
                      </div>
                      <PagedList
                        items={bucket}
                        resetKey={`${epic.key}-${month}`}
                        getKey={(ticket) => ticket.key}
                        empty={<p className="month-empty">{isNext ? "Drop tickets here — next month stays yours to fill." : "No tickets this month."}</p>}
                        renderItem={(ticket) => (
                          <TicketCard
                            compact={compact}
                            ticket={ticket}
                            months={months}
                            labels={labels}
                            currentMonth={currentMonth}
                            onDrag={() => setDragging({ epic: epic.key, key: ticket.key })}
                            onMonth={(value) => onMove(epic.key, ticket.key, value)}
                            onPatch={(fields, saveNow) => onPatchTicket(ticket.key, fields, saveNow)}
                            onSave={onSave}
                            onRemove={() => onRemove(ticket.key)}
                          />
                        )}
                      />
                    </>
                  ) : (
                    <button
                      type="button"
                      className="month-rail"
                      aria-expanded={false}
                      aria-label={`Expand ${label}, ${bucket.length} tickets`}
                      onClick={() => toggleMonth(month)}
                    >
                      <span>
                        {label}
                        {bucket.length ? ` · ${bucket.length}` : ""}
                      </span>
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </>
      ) : null}
    </article>
  );
}

function TicketCard({
  compact,
  ticket,
  months,
  labels,
  currentMonth,
  onDrag,
  onMonth,
  onPatch,
  onSave,
  onRemove,
}: {
  compact: boolean;
  ticket: RoadmapTicket;
  months: string[];
  labels: string[];
  currentMonth: string;
  onDrag: () => void;
  onMonth: (month: string) => void;
  onPatch: (fields: Partial<RoadmapTicket>, saveNow?: boolean) => void;
  onSave: () => void;
  onRemove: () => void;
}) {
  const [expanded, setExpanded] = useState(!compact);
  const [uploadError, setUploadError] = useState("");
  const uploadRef = useRef<HTMLInputElement>(null);
  useEffect(() => setExpanded(!compact), [compact]);
  const [sheetName, setSheetName] = useState("");
  const [sheetUrl, setSheetUrl] = useState("");
  const [uploading, setUploading] = useState(false);
  const attachments = ticket.attachments || [];

  async function attachPdf(file: File | undefined) {
    if (!file) return;
    if (file.size > 10 * 1024 * 1024 || !/\.pdf$/i.test(file.name)) { setUploadError("Choose a PDF up to 10 MB."); return; }
    setUploadError("");
    setUploading(true);
    try {
      const uploaded = await api.uploadRoadmapFile(file);
      onPatch({ attachments: [...attachments, uploaded] }, true);
    } catch (err) {
      setUploadError(String(err));
    } finally {
      setUploading(false);
    }
  }

  function addSheet(event: React.FormEvent) {
    event.preventDefault();
    const url = sheetUrl.trim();
    if (!/^https?:\/\//i.test(url)) {
      setUploadError("Sheet link must start with http:// or https://");
      return;
    }
    const item: RoadmapAttachment = {
      kind: "sheet",
      name: sheetName.trim() || "Sheet",
      url,
    };
    onPatch({ attachments: [...attachments, item] }, true);
    setSheetName("");
    setSheetUrl("");
  }

  function removeAttachment(index: number) {
    onPatch(
      { attachments: attachments.filter((_, i) => i !== index) },
      true,
    );
  }

  return (
    <article
      className={`roadmap-card ${expanded ? "" : "compact"}`}
      draggable
      onDragStart={(event) => {
        if ((event.target as HTMLElement).closest("button, select, a, textarea, input, form")) {
          event.preventDefault();
          return;
        }
        event.dataTransfer.setData("text/plain", ticket.key);
        onDrag();
      }}
    >
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <TicketLink issueKey={ticket.key} />
        <PillButton variant="text" sx={{ p: 0, minWidth: 32, fontSize: 12 }} aria-expanded={expanded} onClick={() => setExpanded(value => !value)}>{expanded ? "Less" : "Details"}</PillButton>
      </Stack>
      <Typography sx={{ my: 1, fontSize: 14 }}>{ticket.summary}</Typography>
      <Stack direction="row" spacing={0.75} useFlexGap flexWrap="wrap">
        {ticket.status ? <StatusChip label={ticket.status} /> : null}
        {ticket.assignee ? <StatusChip label={ticket.assignee} /> : null}
      </Stack>
      {expanded ? <>
      <TextField
        select
        size="small"
        fullWidth
        value={ticket.month && months.includes(ticket.month) ? ticket.month : currentMonth || months[0] || ""}
        onChange={(event) => onMonth(event.target.value)}
        sx={{ mt: 1 }}
      >
        {months.map((month, index) => (
          <MenuItem key={month} value={month}>
            {labels[index] || month}
          </MenuItem>
        ))}
      </TextField>
      <textarea
        className="ticket-note"
        value={ticket.note || ""}
        placeholder="Ticket notes"
        onChange={(event) => onPatch({ note: event.target.value })}
        onBlur={onSave}
      />
      {attachments.length ? (
        <ul className="ticket-files">
          {attachments.map((item, index) => (
            <li key={`${item.url}-${index}`}>
              <a href={item.url} target="_blank" rel="noreferrer">
                {item.kind === "pdf" ? "PDF" : "Sheet"} · {item.name}
              </a>
              <RemoveButton onClick={() => removeAttachment(index)} />
            </li>
          ))}
        </ul>
      ) : null}
      <div className="ticket-attach">
        {uploadError ? <Banner severity="error">{uploadError}</Banner> : null}
        <PillButton variant="gray" type="button" disabled={uploading} onClick={() => uploadRef.current?.click()}>{uploading ? "Uploading PDF…" : "Attach PDF"}</PillButton>
        <input ref={uploadRef} hidden type="file" accept="application/pdf,.pdf" disabled={uploading} onChange={(event) => { const file = event.target.files?.[0]; event.target.value = ""; attachPdf(file); }} />
        <Typography variant="caption">PDF up to 10 MB · saved with this ticket</Typography>
        <form className="ticket-sheet" onSubmit={addSheet}>
          <TextField size="small" value={sheetName} onChange={(event) => setSheetName(event.target.value)} placeholder="Sheet name" />
          <TextField size="small" value={sheetUrl} onChange={(event) => setSheetUrl(event.target.value)} placeholder="https://docs.google.com/spreadsheets/…" />
          <PillButton variant="gray" type="submit" disabled={!sheetUrl.trim()}>
            Add sheet
          </PillButton>
        </form>
      </div>
      <RemoveButton onClick={onRemove} title="Remove from this roadmap" />
      </> : null}
    </article>
  );
}
