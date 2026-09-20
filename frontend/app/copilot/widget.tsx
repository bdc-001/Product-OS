"use client";

import Dialog from "@mui/material/Dialog";
import DialogTitle from "@mui/material/DialogTitle";
import DialogContent from "@mui/material/DialogContent";
import Button from "@mui/material/Button";
import LinearProgress from "@mui/material/LinearProgress";
import Box from "@mui/material/Box";
import Checkbox from "@mui/material/Checkbox";
import FormControlLabel from "@mui/material/FormControlLabel";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@/app/ui/stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import AutoAwesomeOutlinedIcon from "@mui/icons-material/AutoAwesomeOutlined";
import { useEffect, useMemo, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { createPortal } from "react-dom";
import { useRefresh } from "@/app/refresh";
import { useCopilot, type CopilotLaunch } from "./context";
import {
  api,
  type DailyNote,
  type LibraryDocument,
  type PrototypeSession,
  type SourceIndex,
  type CopilotAction,
  type CopilotFile,
  type CopilotMention,
  type CopilotPlan,
} from "@/lib/api";
import { Banner, EmptyState, PagedList, PillButton, RemoveButton, StatusChip, TicketLink } from "@/app/ui";
import { apple } from "@/app/theme";

const TICKET_RE = /\b([A-Z][A-Z0-9]+-\d+)\b/gi;
const LABEL_KEYS: Record<string, string> = {
  "Product Area": "product_area",
  "PRD / Prototype Link": "prd_link",
  "Request Type": "request_type",
  "Steps to Reproduce": "steps_to_reproduce",
  Customer: "customer",
  "Priority / Priority Level": "priority",
  Description: "description",
  Summary: "summary",
};

type Chip = { kind: "ticket" | "person" | "branch"; key: string; label: string; summary?: string };
type Picker = "branch" | "ticket" | "person" | "notes" | null;

function mentionToken(text: string) {
  const at = text.lastIndexOf("@");
  if (at < 0) return "";
  if (at > 0 && !/\s/.test(text[at - 1] || " ")) return "";
  const token = text.slice(at + 1);
  if (token.includes(" ") || token.includes("\n")) return "";
  return token;
}

function fieldKey(label: string) {
  return LABEL_KEYS[label] || label.toLowerCase().replace(/[^a-z0-9]+/g, "_");
}

function actionDiff(action: CopilotAction) {
  if (action.kind === "create") {
    return `will create ${action.issue_type || "Task"} on ${action.project || "AC"}${action.parent_epic ? ` under ${action.parent_epic}` : ""}: ${action.summary || ""}`;
  }
  if (action.kind === "comment") return `will comment on ${action.issue_key}`;
  if (action.kind === "assign") return `will assign ${action.issue_key} → ${action.assignee}`;
  if (action.kind === "set_fields" || action.kind === "update_fields") {
    const fields = Object.keys(action.fields || {}).join(", ");
    return `will fill ${fields || "fields"} on ${action.issue_key}`;
  }
  if (action.kind === "transition") {
    const from = action.from_status ? `${action.from_status} → ` : "";
    return `will transition ${action.issue_key} ${from}${action.transition || action.to_status || ""}`.trim();
  }
  if (action.kind === "set_parent") return `will place ${action.issue_key} under ${action.parent_epic}`;
  if (action.kind === "attach") return `will attach image(s) to ${action.issue_key}`;
  return action.preview || action.kind;
}

function conversationTitle(row: CopilotPlan) {
  const text = (row.prompt || row.notes || "").replace(/\s+/g, " ").trim();
  return text || "Untitled chat";
}

function chipsFromPlan(row: CopilotPlan): Chip[] {
  const out: Chip[] = [];
  if (row.branch) out.push({ kind: "branch", key: row.branch, label: row.branch });
  for (const key of row.ticket_keys || []) out.push({ kind: "ticket", key, label: key });
  for (const key of row.people || []) out.push({ kind: "person", key, label: key });
  return out;
}

function CopilotChat({ onClose }: { onClose: () => void }) {
  const { launch, opened } = useCopilot();
  const path = usePathname() || "/";
  const studioId = Number((path.match(/^\/prototype\/(\d+)/) || [])[1] || 0);
  const { tick } = useRefresh();
  const fileRef = useRef<HTMLInputElement>(null);
  const streamRef = useRef<HTMLDivElement>(null);
  const composeRef = useRef<HTMLTextAreaElement>(null);
  const [activePlanId, setActivePlanId] = useState(0);
  const [prompt, setPrompt] = useState("");
  const [notes, setNotes] = useState("");
  const [chips, setChips] = useState<Chip[]>([]);
  const [images, setImages] = useState<CopilotFile[]>([]);
  const [mentions, setMentions] = useState<{ tickets: CopilotMention[]; people: CopilotMention[]; branches: CopilotMention[]; prototypes: CopilotMention[] }>({
    tickets: [],
    people: [],
    branches: [],
    prototypes: [],
  });
  const [plan, setPlan] = useState<CopilotPlan | null>(null);
  const [plans, setPlans] = useState<CopilotPlan[]>([]);
  const [turns, setTurns] = useState<{ role?: string; text?: string; plan_id?: number }[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [overrides, setOverrides] = useState<Record<string, Record<string, unknown>>>({});
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [picker, setPicker] = useState<Picker>(null);
  const [pickerQuery, setPickerQuery] = useState("");
  const [convQuery, setConvQuery] = useState("");
  const [railOpen, setRailOpen] = useState(false);
  const [contextOpen, setContextOpen] = useState(false);
  const [documents, setDocuments] = useState<LibraryDocument[]>([]);
  const [dailyNotes, setDailyNotes] = useState<DailyNote[]>([]);
  const [documentIds, setDocumentIds] = useState<number[]>([]);
  const [noteIds, setNoteIds] = useState<number[]>([]);
  const [prototypeIds, setPrototypeIds] = useState<number[]>([]);
  const [prototypes, setPrototypes] = useState<PrototypeSession[]>([]);
  const [codeScope, setCodeScope] = useState("");
  const [source, setSource] = useState<SourceIndex | null>(null);
  const [contextQuery, setContextQuery] = useState("");
  const [defaultBranch, setDefaultBranch] = useState("");
  useEffect(() => { api.workspaceSummary().then(d => { if(d.data_branch) setDefaultBranch(d.data_branch); else api.codebaseStatus().then(s => setDefaultBranch(s.indexed_branch || s.branch)).catch(() => null); }).catch(() => null); }, []);
  const sourceBranch = chips.find(item => item.kind === "branch")?.key || defaultBranch;
  useEffect(() => { let active = true; if(sourceBranch) api.sourceIndex(sourceBranch).then(s=>active&&setSource(s)).catch(()=>active&&setSource(null)); return()=>{active=false;}; }, [sourceBranch]);
  useEffect(() => { if(!contextOpen)return; let active=true; const timer=setTimeout(()=>{ api.documents(contextQuery).then(d=>active&&setDocuments(d.documents)).catch(e=>active&&setError(String(e))); api.notes(contextQuery).then(d=>active&&setDailyNotes(d.notes)).catch(e=>active&&setError(String(e))); api.prototypes().then(d=>active&&setPrototypes(d.prototypes||[])).catch(e=>active&&setError(String(e))); },200); return()=>{active=false;clearTimeout(timer);}; },[contextOpen, contextQuery]);

  const atQuery = mentionToken(prompt);
  const mentionNeedle = picker === "branch" || picker === "ticket" || picker === "person" ? pickerQuery : atQuery;

  function applyLaunch(next: CopilotLaunch) {
    if (next.plan) setActivePlanId(next.plan);
    else if (next.prototype || next.prompt) setActivePlanId(0);
    if (next.document) setDocumentIds([next.document]);
    if (next.note) setNoteIds([next.note]);
    if (next.prototype) setPrototypeIds([next.prototype]);
    const epic = (next.epic || "").trim().toUpperCase();
    if (epic) {
      setChips((current) => (current.some((row) => row.kind === "ticket" && row.key === epic) ? current : [...current, { kind: "ticket", key: epic, label: epic }]));
    }
    if (next.prompt) setPrompt(next.prompt);
    if (next.notes) {
      setNotes(next.notes);
      setPicker("notes");
    }
  }

  useEffect(() => {
    if (!launch) return;
    applyLaunch(launch);
  }, [launch]);

  useEffect(() => {
    if (!opened) return;
    api.prototypes().then((data) => setPrototypes(data.prototypes || [])).catch(() => null);
  }, [opened]);

  useEffect(() => {
    if (!opened || !studioId) return;
    setPrototypeIds((current) => (current.includes(studioId) ? current : [...current, studioId]));
  }, [opened, studioId]);

  useEffect(() => {
    api
      .copilotThread()
      .then((data) => {
        setTurns(data.turns || []);
        setPlans(data.plans || []);
      })
      .catch(() => null);
  }, [tick, activePlanId]);

  useEffect(() => {
    if (!activePlanId) {
      setPlan(null);
      setSelected([]);
      setOverrides({});
      return;
    }
    api
      .copilotPlanGet(activePlanId)
      .then((row) => {
        setPlan(row);
        setSelected((row.actions || []).map((item) => item.id));
        setOverrides({});
        setChips(chipsFromPlan(row));
        setDocumentIds(row.context?.document_ids || []);
        setNoteIds(row.context?.note_ids || []);
        setPrototypeIds(row.context?.prototype_ids || []);
        setCodeScope(row.context?.code_scope || "");
      })
      .catch((err) => setError(String(err)));
  }, [activePlanId]);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      api.copilotMentions(mentionNeedle).then(setMentions).catch(() => null);
    }, 160);
    return () => window.clearTimeout(handle);
  }, [mentionNeedle]);

  useEffect(() => {
    streamRef.current?.scrollTo({ top: streamRef.current.scrollHeight });
  }, [plan, turns, busy]);

  const atMenu = useMemo(() => {
    if (!prompt.includes("@") || picker) return [];
    return [...mentions.tickets, ...mentions.people, ...mentions.branches, ...(mentions.prototypes || [])].slice(0, 18);
  }, [prompt, mentions, picker]);

  const pickerItems = useMemo(() => {
    if (picker === "branch") return mentions.branches;
    if (picker === "ticket") return mentions.tickets;
    if (picker === "person") return mentions.people;
    return [];
  }, [picker, mentions]);

  const visiblePlans = useMemo(() => {
    const needle = convQuery.trim().toLowerCase();
    const parents = new Set(plans.map(row=>row.parent_plan_id).filter(Boolean));
    const threads = plans.filter(row=>!parents.has(row.id));
    if (!needle) return threads;
    return threads.filter((row) => conversationTitle(row).toLowerCase().includes(needle));
  }, [plans, convQuery]);

  function addChip(item: CopilotMention) {
    if (item.kind === "prototype") {
      const id = Number(item.key);
      if (id) setPrototypeIds((current) => (current.includes(id) ? current : [...current, id]));
      const at = prompt.lastIndexOf("@");
      if (at >= 0 && mentionToken(prompt)) setPrompt(prompt.slice(0, at).trimEnd() + (prompt.slice(0, at).trimEnd() ? " " : ""));
      setPicker(null);
      setPickerQuery("");
      return;
    }
    const kind = item.kind === "person" || item.kind === "branch" || item.kind === "ticket" ? item.kind : "ticket";
    setChips((current) => {
      const next = kind === "branch" ? current.filter((row) => row.kind !== "branch") : current;
      if (next.some((row) => row.kind === kind && row.key === item.key)) return next;
      return [...next, { kind, key: item.key, label: item.label, summary: item.summary }];
    });
    const at = prompt.lastIndexOf("@");
    if (at >= 0 && mentionToken(prompt)) setPrompt(prompt.slice(0, at).trimEnd() + (prompt.slice(0, at).trimEnd() ? " " : ""));
    setPicker(null);
    setPickerQuery("");
  }

  function pullKeysFromText() {
    const found = `${prompt}\n${notes}`.match(TICKET_RE) || [];
    for (const raw of found) {
      const key = raw.toUpperCase();
      setChips((current) => (current.some((row) => row.kind === "ticket" && row.key === key) ? current : [...current, { kind: "ticket", key, label: key }]));
    }
  }

  async function addFiles(list: FileList | File[]) {
    const files = Array.from(list).slice(0, 4 - images.length);
    for (const file of files) {
      const uploaded = await api.uploadCopilotFile(file);
      setImages((current) => (current.length >= 4 ? current : [...current, uploaded]));
    }
  }

  function openPicker(next: Picker) {
    setPicker((current) => (current === next ? null : next));
    setPickerQuery("");
  }

  function setChat(id: number) {
    if (busy) return;
    setActivePlanId(id);
    setError("");
    setPicker(null);
    setRailOpen(false);
  }

  function resetComposer() {
    setPrompt("");
    setNotes("");
    setChips([]);
    setImages([]);
    setDocumentIds([]);setNoteIds([]);setPrototypeIds([]);setCodeScope("");
    setPicker(null);
    setError("");
    setRailOpen(false);
  }

  function newChat() {
    resetComposer();
    setSelected([]);
    setOverrides({});
    setPlan(null);
    setChat(0);
  }

  useEffect(() => {
    if (!opened) {
      setContextOpen(false);
      setPicker(null);
      setRailOpen(false);
      return;
    }
    const timer = window.setTimeout(() => composeRef.current?.focus(), 40);
    return () => window.clearTimeout(timer);
  }, [opened]);

  useEffect(() => {
    if (!opened) return;
    function onKey(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      if (contextOpen) return;
      if (picker) {
        event.preventDefault();
        setPicker(null);
        return;
      }
      onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [opened, contextOpen, picker, onClose]);

  async function send(event?: React.FormEvent) {
    event?.preventDefault();
    pullKeysFromText();
    if (!prompt.trim() && !notes.trim() && !images.length) return;
    setBusy("plan");
    setError("");
    try {
      const branches = chips.filter((item) => item.kind === "branch");
      const row = await api.copilotPlan({
        prompt: prompt.trim(),
        notes: notes.trim(),
        branch: branches.at(-1)?.key || defaultBranch,
        document_ids: documentIds, note_ids: noteIds, prototype_ids: prototypeIds, code_scope: codeScope, parent_plan_id: activePlanId,
        ticket_keys: chips.filter((item) => item.kind === "ticket").map((item) => item.key),
        people: chips.filter((item) => item.kind === "person").map((item) => item.key),
        image_ids: images.map((item) => item.id),
      });
      setPlan(row);
      setPlans((existing) => [row, ...existing.filter((item) => item.id !== row.id)]);
      setSelected((row.actions || []).map((item) => item.id));
      setOverrides({});
      setTurns((current) => [
        ...current,
        { role: "user", text: prompt.trim() || notes.trim().slice(0, 240), plan_id: row.id },
        { role: "assistant", text: row.answer, plan_id: row.id },
      ]);
      setPrompt("");
      setNotes("");
      setImages([]);
      setPicker(null);
      setActivePlanId(row.id);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy("");
    }
  }

  function patchOverride(id: string, patch: Record<string, unknown>) {
    setOverrides((current) => {
      const prev = { ...(current[id] || {}) };
      if (patch.fields && typeof patch.fields === "object") {
        prev.fields = { ...((prev.fields as Record<string, string>) || {}), ...(patch.fields as Record<string, string>) };
        const rest = { ...patch };
        delete rest.fields;
        return { ...current, [id]: { ...prev, ...rest } };
      }
      return { ...current, [id]: { ...prev, ...patch } };
    });
  }

  function actionReady(action: CopilotAction) {
    const extra = overrides[action.id] || {};
    const parent = String(extra.parent_epic || action.parent_epic || "");
    const fields = { ...(action.fields || {}), ...((extra.fields as Record<string, string>) || {}) };
    const missing = (action.missing || []).filter((label) => {
      if (label === "Parent epic") return !parent;
      const key = fieldKey(label);
      return !String(fields[key] || extra[key] || "").trim();
    });
    return missing.length === 0;
  }

  async function approve() {
    if (!plan?.id) return;
    const blocked = selected.filter((id) => {
      const action = (plan.actions || []).find((item) => item.id === id);
      return !action || !actionReady(action);
    });
    if (!selected.length) {
      setError("Select at least one action, then Approve. Nothing is written to Jira until then.");
      return;
    }
    if (blocked.length) {
      setError("Fill the gaps on every selected row, then Approve. Nothing is written to Jira until then.");
      return;
    }
    setBusy("run");
    setError("");
    try {
      const row = await api.copilotRun({
        plan_id: plan.id,
        approved: true,
        action_ids: selected,
        overrides,
      });
      setPlan(row);
      setPlans((existing) => existing.map((item) => (item.id === row.id ? row : item)));
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy("");
    }
  }

  const actions = plan?.actions || [];
  const preview = plan?.status === "preview" && actions.length > 0;
  const ran = plan?.status === "ran";
  const canApprove =
    selected.length > 0 &&
    selected.every((id) => {
      const action = actions.find((item) => item.id === id);
      return Boolean(action && actionReady(action));
    });
  const messages = useMemo(() => {
    if (!plan) return [];
    if (plan.history?.length) return plan.history;
    const related = turns.filter((turn) => turn.plan_id === plan.id);
    if (related.length) return related;
    const rows: { role?: string; text?: string }[] = [];
    if (plan.prompt || plan.notes) rows.push({ role: "user", text: plan.prompt || plan.notes });
    if (plan.answer) rows.push({ role: "assistant", text: plan.answer });
    return rows;
  }, [plan, turns]);

  return (
    <div className="copilot-shell">
      <Dialog open={contextOpen} onClose={()=>setContextOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Knowledge & sources</DialogTitle><DialogContent>
          <Typography sx={{fontSize:13,color:apple.muted,mb:2}}>Copilot searches relevant notes and documents automatically. Select items to narrow that context.</Typography>
          <TextField label="Code folder (optional)" size="small" fullWidth value={codeScope} onChange={e=>setCodeScope(e.target.value)} placeholder="convin-activate/" sx={{mb:2}}/>
          <Typography variant="caption">{source?.ready ? `${source.file_count} files · ${source.chunk_count} searchable excerpts · ${source.sha.slice(0,12)}` : "The source index will prepare when you ask a code question."}</Typography>
          <TextField label="Find documents or notes" size="small" fullWidth value={contextQuery} onChange={e=>setContextQuery(e.target.value)} sx={{my:2}}/>
          <Typography variant="h3">Documents</Typography>{documents.map(d=><FormControlLabel key={d.id} sx={{display:"flex"}} control={<Checkbox disabled={!d.indexed} checked={documentIds.includes(d.id)} onChange={()=>setDocumentIds(ids=>ids.includes(d.id)?ids.filter(id=>id!==d.id):[...ids,d.id])}/>} label={d.title}/>)}
          <Typography variant="h3" sx={{mt:2}}>Notes</Typography>{dailyNotes.map(n=><FormControlLabel key={n.id} sx={{display:"flex"}} control={<Checkbox checked={noteIds.includes(n.id)} onChange={()=>setNoteIds(ids=>ids.includes(n.id)?ids.filter(id=>id!==n.id):[...ids,n.id])}/>} label={`${n.day} · ${n.title}`}/>)}
          <Typography variant="h3" sx={{mt:2}}>Prototypes</Typography>{prototypes.map(row=><FormControlLabel key={row.id} sx={{display:"flex"}} control={<Checkbox checked={prototypeIds.includes(row.id)} onChange={()=>setPrototypeIds(ids=>ids.includes(row.id)?ids.filter(id=>id!==row.id):[...ids,row.id])}/>} label={`${row.title || "Untitled"} · ${row.status}`}/>)}
          <Box sx={{display:"flex",gap:1,mt:2}}><PillButton onClick={()=>setContextOpen(false)}>Use context</PillButton><PillButton variant="text" onClick={()=>{setDocumentIds([]);setNoteIds([]);setPrototypeIds([]);setCodeScope("");}}>Clear selections</PillButton></Box>
        </DialogContent>
      </Dialog>
      <aside className={`copilot-rail ${railOpen ? "open" : ""}`}>
        <div className="copilot-rail-head">
          <PillButton type="button" onClick={newChat} disabled={Boolean(busy)} fullWidth>
            New chat
          </PillButton>
          <TextField
            value={convQuery}
            onChange={(event) => setConvQuery(event.target.value)}
            placeholder="Search conversations"
            aria-label="Search conversations"
            size="small"
            fullWidth
            sx={{ "& .MuiOutlinedInput-root": { borderRadius: "999px" } }}
          />
        </div>
        <div className="copilot-rail-label">Conversations</div>
        <div className="copilot-convs">
          <PagedList
            items={visiblePlans}
            resetKey={convQuery}
            getKey={(row) => row.id}
            empty={<p className="copilot-rail-empty">{plans.length ? "No matching chats." : "Your chats will land here."}</p>}
            renderItem={(row) => (
              <button type="button" disabled={Boolean(busy)} className={activePlanId === row.id ? "on" : ""} onClick={() => setChat(row.id)}>
                <span>{conversationTitle(row)}</span>
                {row.needs_confirm && row.status !== "ran" ? <i>needs Approve</i> : null}
                {row.status === "ran" ? <i>applied</i> : null}
              </button>
            )}
          />
        </div>
      </aside>

      <section className="copilot-chat">
        <header className="copilot-chat-head">
          <PillButton variant="gray" className="copilot-rail-toggle" type="button" onClick={() => setRailOpen((open) => !open)}>
            Chats
          </PillButton>
          <div className="copilot-chat-title">
            <Typography sx={{ fontSize: 11, color: apple.muted }}>{sourceBranch || "Select a branch"}{source?.ready ? ` · ${source.file_count} files` : ""}</Typography>
            <Typography variant="h2" sx={{ fontSize: 16 }}>
              {plan ? conversationTitle(plan) : "Copilot"}
            </Typography>
          </div>
          <PillButton variant="gray" type="button" onClick={newChat} disabled={Boolean(busy)}>
            New
          </PillButton>
          <RemoveButton onClick={onClose} title="Close Copilot" />
        </header>

        <div className="copilot-stream" ref={streamRef}>
          {!plan && !busy ? (
            <div className="copilot-empty">
              <Typography variant="h2" sx={{fontSize:22}}>Ask Copilot</Typography>
              <Typography sx={{ mt: 1, color: apple.muted, fontSize: 14 }}>Code, tickets, notes, and documents — without leaving this page.</Typography>
              <Box sx={{display:"grid",gap:1,mt:2.5}}>{["Explain convin-activate with file references", "Summarize my recent notes", "What do my documents say about onboarding?", "Turn these notes into a ticket plan"].map(text=><Button key={text} variant="outlined" onClick={()=>setPrompt(text)} sx={{textAlign:"left",fontSize:13,borderRadius:"14px",p:1.5}}>{text}</Button>)}</Box>
            </div>
          ) : null}
          {messages.map((turn, index) => (
            <article key={`${plan?.id || 0}-${index}`} className={`copilot-msg ${turn.role === "user" ? "you" : "bot"}`}>
              <b>{turn.role === "user" ? "You" : "Copilot"}</b>
              <p>{turn.text}</p>
            </article>
          ))}
          {plan?.citations?.length ? (
            <Box component="details" className="copilot-sources"><summary>Sources · {plan.citations.length}</summary>{plan.citations.map((item,index)=><Box key={index} sx={{py:1,borderBottom:`1px solid ${apple.hairline}`}}>{item.url?<a href={item.url} target="_blank" rel="noreferrer">{item.path}</a>:<strong>{item.path}</strong>}<Typography sx={{fontSize:12,color:apple.muted,mt:0.5}}>{item.note}</Typography></Box>)}</Box>
          ) : null}
          {plan?.questions?.length ? (
            <ul className="copilot-questions">
              {plan.questions.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : null}
          {preview ? (
            <div className="copilot-approve">
              <Typography variant="h3">Approve before Jira</Typography>
              <Typography sx={{ mt: 0.75, fontSize: 13, color: apple.muted }}>
                {plan?.ready_count || 0} ready · {plan?.blocked_count || 0} need gaps filled. Unchecked rows are skipped.
              </Typography>
              <div className="copilot-actions">
                {actions.map((action) => {
                  const extra = overrides[action.id] || {};
                  const checked = selected.includes(action.id);
                  const ready = actionReady(action);
                  return (
                    <article key={action.id} className={`copilot-action ${ready ? "ready" : "blocked"}`}>
                      <FormControlLabel
                        className="copilot-check"
                        control={
                          <Checkbox
                            checked={checked}
                            onChange={() =>
                              setSelected((current) => (current.includes(action.id) ? current.filter((id) => id !== action.id) : [...current, action.id]))
                            }
                          />
                        }
                        label={
                          <span>
                            <b>{action.kind}</b> {actionDiff(action)}
                          </span>
                        }
                      />
                      {action.from_status && action.kind === "transition" ? (
                        <p className="copilot-diff">
                          <span className="from">{action.from_status}</span>
                          <span> → </span>
                          <span className="to">{action.transition || action.to_status}</span>
                        </p>
                      ) : null}
                      {!ready ? <p className="copilot-gap-error">{action.blocked || "Fill the red fields to include this row."}</p> : null}
                      {action.kind === "create" ? (
                        <div className="copilot-gaps">
                          {(action.needs_epic || (action.missing || []).includes("Parent epic")) && (
                            <TextField
                              select
                              size="small"
                              fullWidth
                              label="Epic"
                              error={!String(extra.parent_epic || action.parent_epic || "")}
                              value={String(extra.parent_epic || action.parent_epic || "")}
                              onChange={(event) => patchOverride(action.id, { parent_epic: event.target.value })}
                              sx={{ mb: 1 }}
                            >
                              <MenuItem value="">Pick an existing AC epic</MenuItem>
                              {(plan?.epics || []).map((epic) => (
                                <MenuItem key={epic.key} value={epic.key}>
                                  {epic.key} · {epic.title}
                                </MenuItem>
                              ))}
                            </TextField>
                          )}
                          {(action.missing || [])
                            .filter((label) => label !== "Parent epic")
                            .map((label) => {
                              const key = fieldKey(label);
                              const fields = { ...(action.fields || {}), ...((extra.fields as Record<string, string>) || {}) };
                              return (
                                <TextField
                                  key={label}
                                  size="small"
                                  fullWidth
                                  label={label}
                                  error={!String(fields[key] || "").trim()}
                                  value={String(fields[key] || "")}
                                  onChange={(event) => patchOverride(action.id, { fields: { [key]: event.target.value } })}
                                  placeholder={label}
                                  sx={{ mb: 1 }}
                                />
                              );
                            })}
                        </div>
                      ) : null}
                    </article>
                  );
                })}
              </div>
              <PillButton type="button" onClick={approve} disabled={busy === "run" || !canApprove}>
                {busy === "run" ? "Writing to Jira…" : canApprove ? `Approve & apply ${selected.length} to Jira` : "Fill gaps, then Approve"}
              </PillButton>
            </div>
          ) : null}
          {ran ? (
            <>
              <ul className="copilot-results">
                {(plan?.results || []).map((item, index) => (
                  <li key={`${item.id || index}`} className={item.ok ? "ok" : "bad"}>
                    {item.ok ? (
                      item.issue_key ? (
                        <TicketLink issueKey={item.issue_key}>
                          {item.kind} · {item.issue_key}
                          {item.from_status ? ` (${item.from_status} → ${item.to_status || ""})` : ""}
                        </TicketLink>
                      ) : (
                        `${item.kind} done`
                      )
                    ) : (
                      <span>
                        {item.kind} failed: {item.error}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
              {(plan?.results || []).some((item) => item.ok && item.kind === "transition" && item.from_status) ? (
                <PillButton
                  variant="gray"
                  type="button"
                  disabled={busy === "undo"}
                  onClick={async () => {
                    if (!plan?.id) return;
                    setBusy("undo");
                    setError("");
                    try {
                      const row = await api.copilotUndo(plan.id);
                      setPlan(row);
                      setPlans((existing) => [row, ...existing.filter((item) => item.id !== row.id)]);
                      setSelected((row.actions || []).map((item) => item.id));
                      setActivePlanId(row.id);
                    } catch (err) {
                      setError(String(err));
                    } finally {
                      setBusy("");
                    }
                  }}
                >
                  {busy === "undo" ? "Building undo…" : "Undo last transition (still needs Approve)"}
                </PillButton>
              ) : null}
            </>
          ) : null}
          {busy === "plan" ? (
            <article className="copilot-msg bot">
              <b>Copilot</b>
              <p>Searching source files, notes, and documents…</p><LinearProgress aria-label="Copilot is reading context" />
            </article>
          ) : null}
        </div>

        <form className="copilot-compose" onSubmit={send}>
          {error ? <Banner severity="error">{error}</Banner> : null}
          {chips.length || prototypeIds.length ? (
            <Stack direction="row" spacing={0.75} useFlexGap flexWrap="wrap" sx={{ mb: 1 }}>
              {chips.map((chip) => (
                <Box
                  key={`${chip.kind}-${chip.key}`}
                  component="button"
                  type="button"
                  onClick={() => setChips((current) => current.filter((item) => !(item.kind === chip.kind && item.key === chip.key)))}
                  sx={{ border: 0, p: 0, bgcolor: "transparent", cursor: "pointer" }}
                >
                  <StatusChip label={`${chip.kind === "branch" ? "branch" : chip.kind === "person" ? "dev" : "ticket"} ${chip.label} ×`} />
                </Box>
              ))}
              {prototypeIds.map((id) => (
                <Box
                  key={`prototype-${id}`}
                  component="button"
                  type="button"
                  onClick={() => setPrototypeIds((current) => current.filter((item) => item !== id))}
                  sx={{ border: 0, p: 0, bgcolor: "transparent", cursor: "pointer" }}
                >
                  <StatusChip label={`prototype ${prototypes.find((row) => row.id === id)?.title || id} ×`} />
                </Box>
              ))}
            </Stack>
          ) : null}
          {picker === "notes" ? (
            <TextField
              label="Notes (source of truth for new tickets)"
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              placeholder="Paste the work items. Copilot files only what is in these notes, onto existing AC epics."
              multiline
              minRows={3}
              fullWidth
              sx={{ mb: 1 }}
            />
          ) : null}
          {images.length ? (
            <div className="copilot-thumbs">
              {images.map((file) => (
                <button type="button" key={file.id} onClick={() => setImages((current) => current.filter((item) => item.id !== file.id))} title="Remove">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={file.url} alt={file.name} />
                </button>
              ))}
            </div>
          ) : null}
          <Typography sx={{fontSize:11,color:apple.muted,mb:1}}>Context: {sourceBranch || "branch not selected"}{codeScope ? ` / ${codeScope}` : " · entire repository"} · {documentIds.length ? `${documentIds.length} selected documents` : "search library"} · {noteIds.length ? `${noteIds.length} selected notes` : "search notes"} · {prototypeIds.length ? `${prototypeIds.length} selected prototypes` : "no prototype"}</Typography>
          <div className="copilot-connect">
            <PillButton variant="gray" type="button" onClick={()=>setContextOpen(true)}>Knowledge & sources</PillButton>
            <PillButton variant={picker === "branch" ? "filled" : "gray"} type="button" onClick={() => openPicker("branch")}>
              Branch
            </PillButton>
            <PillButton variant={picker === "ticket" ? "filled" : "gray"} type="button" onClick={() => openPicker("ticket")}>
              Tickets
            </PillButton>
            <PillButton variant={picker === "person" ? "filled" : "gray"} type="button" onClick={() => openPicker("person")}>
              People
            </PillButton>
            <PillButton variant={picker === "notes" || notes ? "filled" : "gray"} type="button" onClick={() => openPicker("notes")}>
              Notes
            </PillButton>
            <PillButton variant="gray" type="button" onClick={() => fileRef.current?.click()} disabled={images.length >= 4}>
              Image
            </PillButton>
            <input
              ref={fileRef}
              type="file"
              accept="image/png,image/jpeg,image/gif,image/webp"
              multiple
              hidden
              onChange={(event) => {
                if (event.target.files?.length) addFiles(event.target.files).catch((err) => setError(String(err)));
                event.target.value = "";
              }}
            />
          </div>
          {picker === "branch" || picker === "ticket" || picker === "person" ? (
            <div className="copilot-picker">
              <TextField
                autoFocus
                value={pickerQuery}
                onChange={(event) => setPickerQuery(event.target.value)}
                placeholder={picker === "branch" ? "Search branches" : picker === "ticket" ? "Search tickets" : "Search people"}
                size="small"
                fullWidth
              />
              {pickerItems.length ? (
                <ul>
                  {pickerItems.map((item) => (
                    <li key={`${item.kind}-${item.key}`}>
                      <button type="button" onClick={() => addChip(item)}>
                        {item.label}
                        {item.summary ? ` · ${item.summary}` : ""}
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <EmptyState>Nothing matches.</EmptyState>
              )}
            </div>
          ) : null}
          {atMenu.length ? (
            <ul className="copilot-picker" style={{ listStyle: "none", margin: "8px 0", padding: 0 }}>
              {atMenu.map((item) => (
                <li key={`${item.kind}-${item.key}`}>
                  <button type="button" onClick={() => addChip(item)}>
                    {item.kind} · {item.label}
                    {item.summary ? ` · ${item.summary}` : ""}
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
          <div className="copilot-input">
            <textarea
              ref={composeRef}
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  send();
                }
              }}
              onPaste={(event) => {
                const files = Array.from(event.clipboardData.files || []).filter((file) => file.type.startsWith("image/"));
                if (files.length) {
                  event.preventDefault();
                  addFiles(files).catch((err) => setError(String(err)));
                }
              }}
              placeholder="Message Copilot. Type @ to tag a branch, ticket, or person."
              rows={2}
            />
            <PillButton type="submit" disabled={Boolean(busy)}>
              {busy === "plan" ? "…" : "Send"}
            </PillButton>
          </div>
        </form>
      </section>
    </div>
  );
}

export function CopilotWidget() {
  const { opened, open, close } = useCopilot();
  const [booted, setBooted] = useState(false);
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  useEffect(() => {
    if (opened) setBooted(true);
  }, [opened]);
  if (!mounted) return null;
  return createPortal(
    <div className="copilot-dock">
      {booted ? (
        <div className="copilot-panel" hidden={!opened} aria-hidden={!opened} inert={!opened}>
          <CopilotChat onClose={close} />
        </div>
      ) : null}
      {opened ? null : (
        <button type="button" className="copilot-fab" onClick={() => open()} aria-label="Open Copilot" aria-expanded={false} title="Copilot">
          <AutoAwesomeOutlinedIcon sx={{ fontSize: 26 }} />
        </button>
      )}
    </div>,
    document.body,
  );
}
