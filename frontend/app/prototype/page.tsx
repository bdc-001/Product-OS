"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Skeleton, Pagination } from "@mui/material";
import Box from "@mui/material/Box";
import MenuItem from "@mui/material/MenuItem";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { useRefresh } from "@/app/refresh";
import { useCopilot } from "@/app/copilot/context";
import { api, type PrototypeSession } from "@/lib/api";
import { Banner, EmptyState, FrostCard, PageBody, PillButton, StatusChip } from "@/app/ui";
import { apple } from "@/app/ui/tokens";

function formatWhen(iso?: string | null) {
  if (!iso) return "—";
  const value = iso.endsWith("Z") || /[+-]\d{2}:\d{2}$/.test(iso) ? iso : `${iso}Z`;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return iso.replace("T", " ").slice(0, 16);
  return date.toLocaleString("en-IN", { timeZone: "Asia/Kolkata", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

function LastModified({ iso }: { iso?: string | null }) {
  const [text, setText] = useState("—");
  useEffect(() => {
    setText(formatWhen(iso));
  }, [iso]);
  return <>{text}</>;
}

function statusTone(status: string): "ink" | "danger" | "default" {
  if (status === "error") return "danger";
  if (status === "ready") return "ink";
  return "default";
}

export default function PrototypeListPage() {
  const router = useRouter();
  const { tick } = useRefresh();
  const { open } = useCopilot();
  const [rows, setRows] = useState<PrototypeSession[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [sort, setSort] = useState("newest");
  const [page, setPage] = useState(1);
  const [attempt, setAttempt] = useState(0);
  const [progress, setProgress] = useState("");

  useEffect(() => {
    let active = true;
    setLoaded(false); setError("");
    api
      .prototypes()
      .then((data) => { if (active) setRows(data.prototypes || []); })
      .catch((err) => { if (active) setError(String(err)); })
      .finally(() => { if (active) setLoaded(true); });
    return () => { active = false; };
  }, [tick, attempt]);
  useEffect(() => setPage(1), [query, status, sort]);

  async function create() {
    setBusy(true);
    setError("");
    try {
      const row = await api.createPrototype({}, job => setProgress(job.status === "queued" ? "Preparing workspace…" : "Creating your prototype…"));
      if (!row.id) throw new Error("Prototype was not created.");
      router.push(`/prototype/${row.id}`);
    } catch (err) {
      setError(String(err));
      api.prototypes().then(data => setRows(data.prototypes || [])).catch(() => {});
    } finally {
      setBusy(false);
    }
  }

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const filtered = rows.filter((row) => {
      if (status !== "all" && (row.status || "") !== status) return false;
      if (!needle) return true;
      return (row.title || "").toLowerCase().includes(needle) || String(row.id).includes(needle);
    });
    return [...filtered].sort((a, b) => {
      const left = a.updated_at || a.created_at || "";
      const right = b.updated_at || b.created_at || "";
      return sort === "oldest" ? left.localeCompare(right) : right.localeCompare(left);
    });
  }, [rows, query, status, sort]);

  const pages = Math.max(1, Math.ceil(visible.length / 10));
  const currentPage = Math.min(page, pages);
  const pageRows = visible.slice((currentPage - 1) * 10, currentPage * 10);
  const writePrd = (row: PrototypeSession) => open({ prototype: row.id, prompt: `Write a PRD from the prototype "${row.title || row.id}". Ground it in the prototype code and prompt history.` });

  const cell = { fontSize: 13, py: 1.25, px: 1.5, borderColor: apple.hairline };

  return (
    <PageBody>
      <Box sx={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 2, mb: 2.5, flexWrap: "wrap" }}>
        <Box sx={{ minWidth: 0, flex: 1 }}>

          <Typography sx={{ mt: 0.75, fontSize: 14, lineHeight: 1.47, color: apple.muted }}>Create and refine interactive product prototypes.</Typography>
        </Box>
        <PillButton variant="gray" onClick={() => create()} disabled={busy}>{busy ? "Creating…" : "New prototype"}</PillButton>
      </Box>
      <Typography variant="body2" color="text.secondary" sx={{mb:1.5}} role="status">{busy ? progress || "Preparing workspace…" : loaded ? `${visible.length} projects` : "Loading projects…"}</Typography>
      {error ? <Banner severity="error">{error} <PillButton variant="text" onClick={() => setAttempt(n => n + 1)}>Retry list</PillButton></Banner> : null}
      <FrostCard sx={{ p: 0, overflow: "hidden", "&:hover": { borderColor: apple.hairline } }}>
        <Box sx={{ px: 2, py: 1.5, borderBottom: `1px solid ${apple.hairline}`, display: "flex", gap: 1.25, flexWrap: "wrap" }}>
          <TextField size="small" label="Find project" value={query} onChange={(event) => setQuery(event.target.value)} sx={{ minWidth: 180, flex: 1 }} />
          <TextField select size="small" label="Status" value={status} onChange={(event) => setStatus(event.target.value)} sx={{ width: { xs: "100%", sm: 160 } }}>
            <MenuItem value="all">All</MenuItem>
            <MenuItem value="ready">Ready</MenuItem>
            <MenuItem value="generating">Generating</MenuItem>
            <MenuItem value="draft">Draft</MenuItem>
            <MenuItem value="error">Error</MenuItem>
          </TextField>
          <TextField select size="small" label="Last modified" value={sort} onChange={(event) => setSort(event.target.value)} sx={{ width: { xs: "100%", sm: 180 } }}>
            <MenuItem value="newest">Newest first</MenuItem>
            <MenuItem value="oldest">Oldest first</MenuItem>
          </TextField>
        </Box>
        {(query || status !== "all") && <Box sx={{px:2,py:1}}><PillButton variant="text" onClick={() => {setQuery("");setStatus("all");}}>Clear filters</PillButton></Box>}
        {!loaded ? <Box sx={{ p: 2 }}>{[0, 1, 2].map(n => <Skeleton key={n} height={64}/>)}</Box> : !visible.length ? (
          <Box sx={{ p: 2 }}>
            <EmptyState>{rows.length ? "No prototypes match these filters." : "No prototypes yet. Create one to open the studio."}</EmptyState>
          </Box>
        ) : (
          <>
          <Box sx={{ display: { xs: "grid", md: "none" }, gap: 1.5, p: 2 }}>{pageRows.map(row => <Box key={row.id} sx={{ border: 1, borderColor: "divider", borderRadius: 2, p: 2 }}>
            <Typography component="a" href={`/prototype/${row.id}`} sx={{display:"block",fontWeight:600,color:"text.primary",textDecoration:"none",overflowWrap:"anywhere",mb:1}}>{row.title || "Untitled"}</Typography>
            <StatusChip label={row.status || "draft"} tone={statusTone(row.status || "")} />
            <Typography variant="caption" color="text.secondary" sx={{display:"block",mt:1}}>Updated <LastModified iso={row.updated_at || row.created_at} /></Typography>
            <Box sx={{display:"flex",gap:1,mt:1.5}}><PillButton variant="gray" href={`/prototype/${row.id}`}>Open studio</PillButton><PillButton variant="text" onClick={() => writePrd(row)}>Write PRD</PillButton></Box>
          </Box>)}</Box>
          <TableContainer sx={{display:{xs:"none",md:"block"}}}>
            <Table size="small" aria-label="Prototypes">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ ...cell, fontWeight: 600 }}>Project</TableCell>
                  <TableCell sx={{ ...cell, fontWeight: 600, width: 120 }}>Status</TableCell>
                  <TableCell sx={{ ...cell, fontWeight: 600, width: 170 }}>Last modified</TableCell>
                  <TableCell sx={{ ...cell, fontWeight: 600, width: 80 }} align="right">Files</TableCell>
                  <TableCell sx={{ ...cell, fontWeight: 600, width: 220 }} align="right"> </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {pageRows.map((row) => (
                  <TableRow
                    key={row.id}
                    hover
                    onClick={() => router.push(`/prototype/${row.id}`)}
                    sx={{ cursor: "pointer", "& td": { borderColor: apple.hairline } }}
                  >
                    <TableCell sx={cell}>
                      <Typography component="a" href={`/prototype/${row.id}`} sx={{ fontSize: 14, fontWeight: 650, color:"text.primary", textDecoration:"none", overflowWrap:"anywhere" }}>{row.title || "Untitled"}</Typography>
                      <Typography sx={{ fontSize: 12, color: apple.muted }}>#{row.id}</Typography>
                    </TableCell>
                    <TableCell sx={cell}><StatusChip label={row.status || "draft"} tone={statusTone(row.status || "")} /></TableCell>
                    <TableCell sx={{ ...cell, color: apple.muted, whiteSpace: "nowrap" }}><LastModified iso={row.updated_at || row.created_at} /></TableCell>
                    <TableCell sx={cell} align="right">{row.file_count ?? "—"}</TableCell>
                    <TableCell sx={cell} align="right" onClick={(event) => event.stopPropagation()}>
                      <Box sx={{ display: "flex", justifyContent: "flex-end", gap: 1, flexWrap: "wrap" }}>
                        <PillButton
                          variant="gray"
                          type="button"
                          onClick={() =>
                            open({
                              prototype: row.id,
                              prompt: `Write a PRD from the prototype "${row.title || row.id}". Ground it in the prototype code and prompt history.`,
                            })
                          }
                        >
                          Write PRD
                        </PillButton>
                        <PillButton variant="text" href={`/prototype/${row.id}`}>Open</PillButton>
                      </Box>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
          {pages > 1 && <Box sx={{p:2,borderTop:1,borderColor:"divider"}}><Pagination page={currentPage} count={pages} onChange={(_,value) => setPage(value)} aria-label="Prototype pages" /></Box>}
          </>
        )}
      </FrostCard>
    </PageBody>
  );
}
