"use client";
import { useEffect, useRef, useState } from "react";
import Box from "@mui/material/Box";
import TextField from "@mui/material/TextField";
import MenuItem from "@mui/material/MenuItem";
import Typography from "@mui/material/Typography";
import LinearProgress from "@mui/material/LinearProgress";
import { useRefresh } from "@/app/refresh";
import { useCopilot } from "@/app/copilot/context";
import { api, type LibraryDocument } from "@/lib/api";
import { PageBody, FrostCard, ModuleIntro, PillButton, Banner, EmptyState, RemoveButton, SideDrawer, StatusChip } from "@/app/ui";
export default function LMSPage(){
  const {tick} = useRefresh();
  const {open} = useCopilot();
  const [rows,setRows]=useState<LibraryDocument[]>([]),[q,setQ]=useState(""),[total,setTotal]=useState(0),[busy,setBusy]=useState(false),[error,setError]=useState(""),[preview,setPreview]=useState<LibraryDocument|null>(null);
  const [kind,setKind]=useState(""),[filterStatus,setFilterStatus]=useState("");
  const [loading,setLoading]=useState(true),[attempt,setAttempt]=useState(0),[previewId,setPreviewId]=useState<number|null>(null),[previewError,setPreviewError]=useState(""),[previewAttempt,setPreviewAttempt]=useState(0);
  const [updating,setUpdating]=useState<number|null>(null);
  const upload=useRef<HTMLInputElement>(null);
  const load=()=>api.documents(q,0,kind,filterStatus).then(d=>{setRows(d.documents);setTotal(d.total);});
  useEffect(()=>{let active=true;setLoading(true);setError("");const t=setTimeout(()=>api.documents(q,0,kind,filterStatus).then(d=>{if(active){setRows(d.documents);setTotal(d.total);}}).catch(e=>active&&setError(String(e))).finally(()=>active&&setLoading(false)),200);return()=>{active=false;clearTimeout(t);};},[q,tick,kind,filterStatus,attempt]);
  useEffect(()=>{setPreview(null);setPreviewError("");if(previewId==null)return;let active=true;api.document(previewId).then(d=>active&&setPreview(d)).catch(e=>active&&setPreviewError(String(e)));return()=>{active=false;};},[previewId,previewAttempt]);
  async function add(file?:File){if(!file)return;setError("");if(file.size>20*1024*1024){setError("Choose a file up to 20 MB.");return;}setBusy(true);try{await api.uploadDocument(file);await load();}catch(e){setError(String(e));}finally{setBusy(false);}}
  async function progress(row:LibraryDocument,status:string){setUpdating(row.id);try{await api.updateDocument(row.id,{status});await load();}catch(e){setError(String(e));}finally{setUpdating(null);}}
  return <PageBody>
    <ModuleIntro><Box><Typography color="text.secondary">Your learning library. Save documents, track reading, and ask Copilot.</Typography><Typography variant="caption">PDF, DOCX, Markdown, and text · up to 20 MB per file</Typography></Box><><PillButton disabled={busy} onClick={()=>upload.current?.click()}>{busy?"Reading document…":"Upload document"}</PillButton><input ref={upload} hidden type="file" accept=".pdf,.docx,.md,.txt" onChange={e=>{const f=e.target.files?.[0];e.target.value="";add(f);}}/></></ModuleIntro>
    {busy?<LinearProgress aria-label="Uploading and indexing document" sx={{mb:2}}/>:null}{error?<Banner severity="error">{error} <PillButton variant="text" disabled={loading} onClick={()=>setAttempt(n=>n+1)}>Try again</PillButton></Banner>:null}
    <Box sx={{display:"flex",gap:2,flexWrap:"wrap",mb:3}}>
      <TextField label="Search library" size="small" value={q} onChange={e=>setQ(e.target.value)} sx={{flex:1,minWidth:200}}/>
      <TextField select label="Document type" value={kind} onChange={e=>setKind(e.target.value)} sx={{minWidth:170}}>{[["","All documents"],["prd","PRD snapshots"],["pdf","PDF"],["docx","Word"],["md","Markdown"],["txt","Text"]].map(([value,label])=><MenuItem key={value} value={value}>{label}</MenuItem>)}</TextField>
      <TextField select label="Reading status" value={filterStatus} onChange={e=>setFilterStatus(e.target.value)} sx={{minWidth:170}}>{[["","All statuses"],["to_read","To read"],["reading","Reading"],["completed","Completed"]].map(([value,label])=><MenuItem key={value} value={value}>{label}</MenuItem>)}</TextField>
    </Box>
    <Box sx={{display:"flex",alignItems:"center",justifyContent:"space-between",gap:1,mb:2}}><Typography variant="caption" color="text.secondary" role="status">{loading?"Finding documents…":`${total} documents`}</Typography>{(q||kind||filterStatus)&&<PillButton variant="text" onClick={()=>{setQ("");setKind("");setFilterStatus("");}}>Clear filters</PillButton>}</Box>
    {loading&&<LinearProgress aria-label="Loading library" sx={{mb:2}}/>}
    {!loading&&!error&&!rows.length?<EmptyState>{q||kind||filterStatus?"No matching documents.":"Build your library with a guide, specification, or course notes. Uploaded text becomes searchable by Copilot."}</EmptyState>:null}
    <Box sx={{display:"grid",gridTemplateColumns:{xs:"1fr",md:"repeat(2,minmax(0,1fr))",xl:"repeat(3,minmax(0,1fr))"},gap:2}}>{rows.map(row=><FrostCard key={row.id}>
      <Box sx={{display:"flex",justifyContent:"space-between",gap:1,mb:2}}><StatusChip label={row.tags?.includes("prd")?"PRD · PDF":row.filename.split(".").pop()?.toUpperCase()||"DOC"}/><Typography variant="caption">{Math.max(1,Math.round(row.size/1024))} KB</Typography></Box>
      <Typography variant="h6" sx={{mb:1,overflowWrap:"anywhere"}}>{row.title}</Typography><Typography variant="caption">{row.indexed?"Readable by Copilot":"Stored · text unavailable"}{row.pages?` · ${row.pages} page${row.pages===1?"":"s"}`:""}</Typography>
      {row.tags?.includes("prd") && <Typography variant="caption" sx={{mt:1,display:"block"}}>Saved {row.created_at?.replace("T", " ").slice(0,16)} UTC</Typography>}
      {row.extraction_note?<Typography sx={{fontSize:12,mt:1,color:"warning.dark"}}>{row.extraction_note}</Typography>:null}
      <TextField select fullWidth size="small" label="Reading status" disabled={updating===row.id} value={row.status} onChange={e=>progress(row,e.target.value)} sx={{my:2}}><MenuItem value="to_read">To read</MenuItem><MenuItem value="reading">Reading</MenuItem><MenuItem value="completed">Completed</MenuItem></TextField>
      <Box sx={{display:"flex",gap:1,flexWrap:"wrap"}}><PillButton variant="gray" onClick={()=>setPreviewId(row.id)}>Preview</PillButton><PillButton variant="text" onClick={()=>open({document:row.id})} disabled={!row.indexed}>Ask Copilot</PillButton></Box>
    </FrostCard>)}</Box>
    {rows.length<total?<PillButton variant="text" disabled={loading} onClick={()=>api.documents(q,rows.length,kind,filterStatus).then(d=>setRows(r=>[...r,...d.documents])).catch(e=>setError(String(e)))}>Load more</PillButton>:null}
    <SideDrawer open={previewId!==null} onClose={()=>setPreviewId(null)} width={{xs:"100%",md:660}}>{preview?<><Box sx={{display:"flex",justifyContent:"space-between",gap:2}}><Typography variant="h2">{preview.title}</Typography><RemoveButton title="Close preview" onClick={()=>setPreviewId(null)}/></Box><Box sx={{my:2}}><PillButton variant="gray" href={preview.url} target="_blank" rel="noreferrer">Open original</PillButton></Box><Typography variant="caption">Text preview · first 20,000 characters</Typography><Typography sx={{whiteSpace:"pre-wrap",fontSize:14,mt:2}}>{preview.text||preview.extraction_note}</Typography></>:<><Box sx={{display:"flex",justifyContent:"space-between",alignItems:"center",mb:2}}><Typography>Document preview</Typography><RemoveButton title="Close preview" onClick={()=>setPreviewId(null)}/></Box>{previewError?<Banner severity="error">{previewError}<PillButton variant="text" onClick={()=>setPreviewAttempt(n=>n+1)}>Try again</PillButton></Banner>:<LinearProgress aria-label="Loading document preview"/>}</>}</SideDrawer>
  </PageBody>;
}
