"use client";
import { useEffect, useState } from "react";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import LinearProgress from "@mui/material/LinearProgress";
import { api, type SourceIndex } from "@/lib/api";
import { Banner, FrostCard, PillButton } from "@/app/ui";
import { useRefresh } from "@/app/refresh";
export function SourcePanel({branch}:{branch:string}){
  const [data,setData]=useState<SourceIndex|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState("");
  const {tick}=useRefresh();
  useEffect(()=>{let active=true;setData(null);if(branch)api.sourceIndex(branch).then(d=>active&&setData(d)).catch(e=>active&&setError(String(e)));return()=>{active=false;};},[branch,tick]);
  async function build(){setBusy(true);setError("");try{setData(await api.prepareSources(branch));}catch(e){setError(String(e));}finally{setBusy(false);}}
  return <FrostCard sx={{mb:3}}><Box sx={{display:"flex",justifyContent:"space-between",gap:2,alignItems:"center",flexWrap:"wrap"}}><Box><Typography variant="h3">Source search index</Typography><Typography sx={{mt:1,fontSize:13,color:"text.secondary"}}>{data?.ready?`${data.file_count?.toLocaleString()} files · ${data.chunk_count?.toLocaleString()} excerpts · ${data.sha.slice(0,12)}`:"Prepare the selected branch for source-level questions."}</Typography></Box><PillButton disabled={!branch||busy} onClick={build}>{busy?"Indexing source files…":data?.ready?"Update source index":"Prepare source index"}</PillButton></Box>{busy?<LinearProgress aria-label="Building source index" sx={{mt:2}}/>:null}{error?<Banner severity="error">{error}</Banner>:null}<Typography variant="caption" sx={{display:"block",mt:2}}>Indexes tracked source and documentation without checkout. Unchanged files are reused. Binary files, dependencies, secret paths, and files over 1 MB are excluded.</Typography>{data?.modules?<Box component="details" sx={{mt:2,fontSize:13}}><summary>Coverage by service · {data.skipped_files?.toLocaleString()} files excluded</summary><Box sx={{display:"flex",gap:2,flexWrap:"wrap",mt:1}}>{data.modules.map(m=><span key={m.name}>{m.name}: {m.files}</span>)}</Box></Box>:null}</FrostCard>;
}
