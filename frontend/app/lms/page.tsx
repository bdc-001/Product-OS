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
  const upload=useRef<HTMLInputElement>(null);
  const load=()=>api.documents(q).then(d=>{setRows(d.documents);setTotal(d.total);});
  useEffect(()=>{let active=true;const t=setTimeout(()=>api.documents(q).then(d=>{if(active){setRows(d.documents);setTotal(d.total);}}).catch(e=>active&&setError(String(e))),200);return()=>{active=false;clearTimeout(t);};},[q,tick]);
  async function add(file?:File){if(!file)return;setError("");if(file.size>20*1024*1024){setError("Choose a file up to 20 MB.");return;}setBusy(true);try{await api.uploadDocument(file);await load();}catch(e){setError(String(e));}finally{setBusy(false);}}
  async function progress(row:LibraryDocument,status:string){try{const next=await api.updateDocument(row.id,{status});setRows(r=>r.map(d=>d.id===next.id?next:d));}catch(e){setError(String(e));}}
  return <PageBody>
    <ModuleIntro><Box><Typography color="text.secondary">Your learning library. Save documents, track reading, and ask Copilot.</Typography><Typography variant="caption">PDF, DOCX, Markdown, and text · up to 20 MB per file</Typography></Box><><PillButton disabled={busy} onClick={()=>upload.current?.click()}>{busy?"Reading document…":"Upload document"}</PillButton><input ref={upload} hidden type="file" accept=".pdf,.docx,.md,.txt" onChange={e=>{const f=e.target.files?.[0];e.target.value="";add(f);}}/></></ModuleIntro>
    {busy?<LinearProgress aria-label="Uploading and indexing document" sx={{mb:2}}/>:null}{error?<Banner severity="error">{error}</Banner>:null}
    <TextField label="Search library" size="small" value={q} onChange={e=>setQ(e.target.value)} sx={{mb:3,width:{xs:"100%",md:420}}}/>
    {!rows.length?<EmptyState>{q?"No matching documents.":"Build your library with a guide, specification, or course notes. Uploaded text becomes searchable by Copilot."}</EmptyState>:null}
    <Box sx={{display:"grid",gridTemplateColumns:{xs:"1fr",md:"repeat(2,minmax(0,1fr))",xl:"repeat(3,minmax(0,1fr))"},gap:2}}>{rows.map(row=><FrostCard key={row.id}>
      <Box sx={{display:"flex",justifyContent:"space-between",gap:1,mb:2}}><StatusChip label={row.filename.split(".").pop()?.toUpperCase()||"DOC"}/><Typography variant="caption">{Math.max(1,Math.round(row.size/1024))} KB</Typography></Box>
      <Typography variant="h3" sx={{mb:1}}>{row.title}</Typography><Typography variant="caption">{row.indexed?"Readable by Copilot":"Stored · text unavailable"}{row.pages?` · ${row.pages} page${row.pages===1?"":"s"}`:""}</Typography>
      {row.extraction_note?<Typography sx={{fontSize:12,mt:1,color:"warning.dark"}}>{row.extraction_note}</Typography>:null}
      <TextField select fullWidth size="small" label="Learning progress" value={row.status} onChange={e=>progress(row,e.target.value)} sx={{my:2}}><MenuItem value="to_read">To read</MenuItem><MenuItem value="reading">Reading</MenuItem><MenuItem value="completed">Completed</MenuItem></TextField>
      <Box sx={{display:"flex",gap:1,flexWrap:"wrap"}}><PillButton variant="gray" onClick={()=>api.document(row.id).then(setPreview).catch(e=>setError(String(e)))}>Preview</PillButton><PillButton variant="text" onClick={()=>open({document:row.id})} disabled={!row.indexed}>Ask Copilot</PillButton></Box>
    </FrostCard>)}</Box>
    {rows.length<total?<PillButton variant="text" onClick={()=>api.documents(q,rows.length).then(d=>setRows(r=>[...r,...d.documents])).catch(e=>setError(String(e)))}>Load more</PillButton>:null}
    <SideDrawer open={Boolean(preview)} onClose={()=>setPreview(null)} width={{xs:"100%",md:660}}>{preview?<><Box sx={{display:"flex",justifyContent:"space-between",gap:2}}><Typography variant="h2">{preview.title}</Typography><RemoveButton title="Close preview" onClick={()=>setPreview(null)}/></Box><Box sx={{my:2}}><PillButton variant="gray" href={preview.url} target="_blank" rel="noreferrer">Open original</PillButton></Box><Typography variant="caption">Text preview · first 20,000 characters</Typography><Typography sx={{whiteSpace:"pre-wrap",fontSize:14,mt:2}}>{preview.text||preview.extraction_note}</Typography></>:null}</SideDrawer>
  </PageBody>;
}
