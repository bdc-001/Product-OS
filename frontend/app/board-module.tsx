"use client";

import MenuItem from "@mui/material/MenuItem";
import Pagination from "@mui/material/Pagination";
import LinearProgress from "@mui/material/LinearProgress";
import Box from "@mui/material/Box";
import Stack from "@/app/ui/stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { api, type Issue, type ReleaseAsks } from "@/lib/api";
import { useRefresh } from "@/app/refresh";
import { Banner, EmptyState, ListRow, ModuleIntro, PageBody, PageHeader, PagedList, PillButton, RemoveButton, Section, Segmented, SideDrawer, StatusChip, TicketLink } from "@/app/ui";
import { apple } from "@/app/theme";

function kindOf(issue: Issue) {
  return (issue.kind || "").toLowerCase() || (issue.issue_type || "").toLowerCase();
}

function requirementLabel(issue: Issue) {
  const fields = (issue.fields || {}) as Record<string, unknown>;
  const product = String(fields.product_requirement_type || "").trim();
  const report = String(fields.report_requirement_type || "").trim();
  if (product && report) return `${product} / ${report}`;
  return product || report || "";
}

function summarize(issue: Issue) {
  const text = (issue.summary || "").replace(/\s+/g, " ").trim();
  if (text.length <= 140) return text || "No summary";
  return `${text.slice(0, 137).trim()}…`;
}

function formatWhen(raw?: string | null) {
  if (!raw) return "";
  const value = new Date(raw);
  if (Number.isNaN(value.getTime())) return raw.slice(0, 16);
  return value.toLocaleString("en-GB", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
}

function IssueRow({
  issue,
  selected,
  onOpen,
}: {
  issue: Issue;
  selected: boolean;
  onOpen: (issue: Issue) => void;
}) {
  return (
    <Box role="button" tabIndex={0} aria-pressed={selected} onClick={()=>onOpen(issue)} onKeyDown={(event)=>{if(event.target===event.currentTarget&&(event.key==="Enter"||event.key===" ")){event.preventDefault();onOpen(issue);}}}
      sx={{display:"grid",gridTemplateColumns:{xs:"90px minmax(0,1fr)",md:"90px minmax(0,1fr) 150px 150px"},alignItems:"center",gap:1.5,p:1.75,border:`1px solid ${selected?apple.ink:apple.hairline}`,borderRadius:"12px",cursor:"pointer",bgcolor:selected?apple.wash:apple.page,transition:"background-color 150ms ease", "&:hover":{bgcolor:apple.hoverFill}}}>
      <TicketLink issueKey={issue.issue_key} onClick={event=>event.stopPropagation()}/>
      <Typography sx={{fontSize:14,fontWeight:500}}>{summarize(issue)}</Typography>
      <Typography sx={{fontSize:12,color:apple.muted,gridColumn:{xs:"2",md:"auto"}}}>{issue.assignee||"Unassigned"}</Typography>
      <Box sx={{display:"flex",justifyContent:{md:"flex-end"},gap:0.5,gridColumn:{xs:"2",md:"auto"}}}><StatusChip label={issue.status}/>{issue.priority?<StatusChip label={issue.priority}/>:null}</Box>
    </Box>
  );
}

function IssueDetail({ issue, onClose, onHide }: { issue: Issue; onClose: () => void; onHide: (issue: Issue) => void }) {
  const checklist = issue.field_checklist || [];
  const missing = issue.missing_fields || [];
  const requirement = requirementLabel(issue);
  return (
    <Stack spacing={1.5}>
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Typography sx={{ fontSize: 13, color: apple.muted }}>{issue.board || issue.issue_key}</Typography>
        <RemoveButton onClick={onClose} title="Close" />
      </Stack>
      <Typography variant="h3">
        <TicketLink issueKey={issue.issue_key} />
      </Typography>
      <Typography>{issue.summary}</Typography>
      <Stack direction="row" spacing={0.75} useFlexGap flexWrap="wrap">
        {issue.status ? <StatusChip label={issue.status} /> : null}
        {issue.priority ? <StatusChip label={issue.priority} /> : null}
        {issue.assignee ? <StatusChip label={issue.assignee} /> : null}
      </Stack>
      {requirement ? <Typography sx={{ fontSize: 13, color: apple.muted }}>{requirement}</Typography> : null}
      {issue.description ? <Typography sx={{ fontSize: 15, color: apple.muted }}>{issue.description}</Typography> : null}
      <Typography sx={{ fontSize: 13, color: apple.muted }}>
        {[issue.reporter ? `Reporter ${issue.reporter}` : "", formatWhen(issue.updated_at) ? `Updated ${formatWhen(issue.updated_at)}` : ""]
          .filter(Boolean)
          .join(" · ")}
      </Typography>
      {missing.length ? <Typography sx={{ fontSize: 13, color: apple.danger }}>Missing: {missing.join(", ")}</Typography> : null}
      {checklist.length ? (
        <Box component="ul" sx={{ m: 0, pl: 2, fontSize: 13 }}>
          {checklist.map((row) => (
            <Box component="li" key={row.label} sx={{ color: row.empty && row.required ? apple.danger : apple.text, mb: 0.5 }}>
              {row.label}: {row.empty ? "—" : row.value}
            </Box>
          ))}
        </Box>
      ) : null}
      <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap" alignItems="center">
        {issue.url ? (
          <PillButton variant="text" href={issue.url} target="_blank" rel="noreferrer">
            Open in Jira
          </PillButton>
        ) : null}
        <PillButton href={`/issues/${issue.issue_key}`}>Full ticket</PillButton>
        <RemoveButton onClick={() => onHide(issue)} title="Remove" />
      </Stack>
    </Stack>
  );
}

function IssueList({
  title,
  issues,
  selectedKey,
  onOpen,
  resetKey,
}: {
  title: string;
  issues: Issue[];
  selectedKey: string;
  onOpen: (issue: Issue) => void;
  resetKey: string;
}) {
  return (
    <Section title={title} count={issues.length}>
      <PagedList
        items={issues}
        resetKey={resetKey}
        getKey={(issue) => issue.issue_key}
        empty={<EmptyState>None on this board.</EmptyState>}
        renderItem={(issue) => <IssueRow issue={issue} selected={selectedKey === issue.issue_key} onOpen={onOpen} />}
      />
    </Section>
  );
}

function ReleaseAskPanel() {
  const [payload, setPayload] = useState<ReleaseAsks | null>(null);
  const [error, setError] = useState("");
  const [busyPm, setBusyPm] = useState("");
  const [busyKey, setBusyKey] = useState("");
  const { tick } = useRefresh();

  function load() {
    return api
      .releaseAsks()
      .then((data) => {
        setPayload(data);
        setError(data.error || "");
      })
      .catch((err) => setError(String(err)));
  }

  useEffect(() => {
    load();
  }, [tick]);

  async function nudge(pm: string) {
    setBusyPm(pm);
    setError("");
    try {
      const result = await api.nudgeReleaseAsks(pm);
      const stamp = result.last_nudged_at || "";
      setPayload((current) => {
        if (!current) return current;
        return {
          ...current,
          last_nudged_at: stamp || current.last_nudged_at,
          groups: current.groups.map((group) => (group.pm === pm ? { ...group, last_nudged_at: stamp || group.last_nudged_at } : group)),
        };
      });
    } catch (err) {
      setError(String(err));
    } finally {
      setBusyPm("");
    }
  }

  async function dismiss(issueKey: string) {
    setBusyKey(issueKey);
    setError("");
    try {
      const result = await api.dismissReleaseAsk(issueKey);
      const skipped = new Set((result.dismissed || []).map((key) => key.toUpperCase()));
      skipped.add(issueKey.toUpperCase());
      setPayload((current) => {
        if (!current) return current;
        const groups = current.groups.map((group) => ({
          ...group,
          tickets: group.tickets.filter((ticket) => !skipped.has(ticket.issue_key.toUpperCase())),
        }));
        return {
          ...current,
          dismissed: [...skipped],
          groups,
          count: groups.reduce((sum, group) => sum + group.tickets.length, 0),
        };
      });
    } catch (err) {
      setError(String(err));
    } finally {
      setBusyKey("");
    }
  }

  const count = payload?.count || 0;
  const groups = payload?.groups || [];
  const since = payload?.after_date || payload?.queue_start || "";
  return (
    <Section title="Released — notes needed" count={count}>
      <Typography sx={{ mb: 1.5, fontSize: 15, color: apple.muted }}>
        AC Task · Released · from {since || "today"} IST
        {payload?.data_branch ? ` · data on ${payload.data_branch}` : ""}. Remove keeps a ticket out of reminder DMs.
      </Typography>
      {error ? <Banner severity="error">{error}</Banner> : null}
      {payload?.cliq === false ? <Banner severity="warning">Cliq is not connected, so the reminder cannot send.</Banner> : null}
      {groups.length ? (
        groups.map((group) => {
          const byDate = new Map<string, typeof group.tickets>();
          for (const ticket of group.tickets) {
            const list = byDate.get(ticket.released_on) || [];
            list.push(ticket);
            byDate.set(ticket.released_on, list);
          }
          const n = group.tickets.length;
          return (
            <Box key={group.pm} sx={{ mb: 2 }}>
              <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1} sx={{ mb: 1 }}>
                <Typography variant="h3">
                  {group.pm} · {n}
                </Typography>
                <PillButton disabled={Boolean(busyPm) || Boolean(busyKey) || !n || payload?.cliq === false} onClick={() => nudge(group.pm)}>
                  {busyPm === group.pm ? "Sending…" : `Ask ${group.pm} on Cliq`}
                </PillButton>
              </Stack>
              {group.last_nudged_at ? (
                <Typography sx={{ fontSize: 13, color: apple.muted, mb: 1 }}>
                  Last asked {group.last_nudged_at.slice(0, 16).replace("T", " ")} IST
                </Typography>
              ) : null}
              {n ? (
                [...byDate.entries()].map(([day, tickets]) => (
                  <Box key={day} sx={{ mb: 1.5 }}>
                    <Typography sx={{ fontSize: 12, fontWeight: 600, color: apple.muted, mb: 1 }}>
                      Released {tickets[0]?.released_label || day}
                    </Typography>
                    <PagedList
                      items={tickets}
                      resetKey={`${group.pm}-${day}`}
                      getKey={(ticket) => ticket.issue_key}
                      renderItem={(ticket) => (
                        <Stack direction="row" alignItems="center" spacing={1}>
                          <Box
                            sx={{
                              flex: 1,
                              minWidth: 0,
                              border: `1px solid ${apple.hairline}`,
                              borderRadius: "16px",
                              px: 2,
                              py: 1.25,
                              bgcolor: "#fff",
                              overflowWrap: "anywhere",
                            }}
                          >
                            <Stack direction="row" justifyContent="space-between">
                              <TicketLink issueKey={ticket.issue_key} href={ticket.url || `/issues/${ticket.issue_key}`} />
                              <StatusChip label={ticket.released_label} />
                            </Stack>
                            <Typography sx={{ fontSize: 14 }}>{ticket.summary || ticket.issue_key}</Typography>
                          </Box>
                          <RemoveButton
                            disabled={Boolean(busyKey) || Boolean(busyPm)}
                            onClick={() => dismiss(ticket.issue_key)}
                            title="Remove from this queue. Reminders will skip it."
                          />
                        </Stack>
                      )}
                    />
                  </Box>
                ))
              ) : (
                <EmptyState>No Released tasks in this window.</EmptyState>
              )}
            </Box>
          );
        })
      ) : (
        <EmptyState>{payload?.connected === false ? "Connect Jira to load Released tasks." : "None in this window."}</EmptyState>
      )}
    </Section>
  );
}

export function BoardModule({board}: {board: "AC" | "PS"}) {
  const router = useRouter();
  const [issues,setIssues] = useState<Issue[]>([]);
  const [total,setTotal] = useState(0);
  const [filter,setFilter] = useState("");
  const [kind,setKind] = useState("all");
  const [state,setState] = useState("open");
  const [page,setPage] = useState(1);
  const [error,setError] = useState("");
  const [loading,setLoading] = useState(false);
  const [selected,setSelected] = useState<Issue|null>(null);
  const [detailKey,setDetailKey] = useState("");
  const [detailLoading,setDetailLoading] = useState(false);
  const [releases,setReleases] = useState(false);
  const [reload,setReload] = useState(0);
  const {tick} = useRefresh();
  useEffect(()=>{let active=true;setLoading(true);const timer=setTimeout(()=>api.issuesPage(board,filter,kind,state,(page-1)*20).then(data=>{if(active){setIssues(data.issues);setTotal(data.total);setError(data.connected?"":"Jira is not configured.");}}).catch(e=>active&&setError(String(e))).finally(()=>active&&setLoading(false)),200);return()=>{active=false;clearTimeout(timer);};},[board,filter,kind,state,page,tick,reload]);
  useEffect(()=>{if(!detailKey)return;let active=true;setSelected(null);setDetailLoading(true);api.issue(detailKey).then(d=>active&&setSelected(d.issue as Issue)).catch(e=>active&&setError(String(e))).finally(()=>active&&setDetailLoading(false));return()=>{active=false;};},[detailKey]);
  async function hide(issue:Issue){try{await api.hideCard({issue_key:issue.issue_key,title:issue.summary});setDetailKey("");setReload(r=>r+1);}catch(e){setError(String(e));}}
  return <PageBody>
    <ModuleIntro><Box sx={{width:{xs:"100%",sm:"min(100%, 320px)"},minWidth:0,flex:{xs:"1 1 100%",md:"0 1 320px"}}}><Segmented value={board} onChange={id=>{setPage(1);setDetailKey("");router.push(`/jira?board=${id}`);}} options={[{id:"AC",label:"Sense · AC"},{id:"PS",label:"Support · PS"}]}/></Box><Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap><PillButton variant="gray" onClick={()=>setReload(r=>r+1)} disabled={loading}>Reload list</PillButton>{board==="AC"?<PillButton variant={releases?"filled":"gray"} onClick={()=>setReleases(v=>!v)}>Release follow-ups</PillButton>:null}</Stack></ModuleIntro>
    {error?<Banner severity="error">{error}</Banner>:null}
    {releases&&board==="AC"?<ReleaseAskPanel/>:<>
      <Stack direction={{xs:"column",md:"row"}} spacing={1.5} sx={{mb:3}}>
        <TextField label="Search tickets or owners" size="small" value={filter} onChange={e=>{setFilter(e.target.value);setPage(1);}} sx={{flex:1}}/>
        <TextField select label="Type" size="small" value={kind} onChange={e=>{setKind(e.target.value);setPage(1);}} sx={{minWidth:160}}><MenuItem value="all">All types</MenuItem><MenuItem value="task">Tasks</MenuItem><MenuItem value="bug">Bugs</MenuItem><MenuItem value="report">Reports</MenuItem></TextField>
        <TextField select label="Status" size="small" value={state} onChange={e=>{setState(e.target.value);setPage(1);}} sx={{minWidth:150}}><MenuItem value="open">Open work</MenuItem><MenuItem value="done">Completed</MenuItem><MenuItem value="all">All statuses</MenuItem></TextField>
      </Stack>
      <Typography sx={{fontSize:12,color:apple.muted,mb:2}}>{total} matching tickets · most recently updated first</Typography>
      {loading?<LinearProgress aria-label="Loading Jira tickets" sx={{mb:2}}/>:null}
      <Stack spacing={1}>{issues.map(issue=><IssueRow key={issue.issue_key} issue={issue} selected={detailKey===issue.issue_key} onOpen={row=>setDetailKey(row.issue_key)}/>)}</Stack>
      {!loading&&!issues.length?<EmptyState>No matching tickets. Adjust the search or filters.</EmptyState>:null}
      {total>20?<Pagination count={Math.ceil(total/20)} page={page} onChange={(_,value)=>setPage(value)} sx={{mt:3}}/>:null}
    </>}
    <SideDrawer open={Boolean(detailKey)} onClose={()=>setDetailKey("")} width={{xs:"100%",sm:480}}>
      {detailLoading?<LinearProgress aria-label="Loading ticket details"/>:null}
      {selected?<IssueDetail issue={selected} onClose={()=>setDetailKey("")} onHide={hide}/>:!detailLoading?<><RemoveButton title="Close" onClick={()=>setDetailKey("")}/><EmptyState>Could not load this ticket.</EmptyState></>:null}
    </SideDrawer>
  </PageBody>;
}
