"use client";
import { useEffect, useState } from "react";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import Drawer from "@mui/material/Drawer";
import TextField from "@mui/material/TextField";
import { api, type Competitor } from "@/lib/api";
import { useRefresh } from "@/app/refresh";
import { PageBody, PillButton, Segmented, Banner, RemoveButton, EmptyState } from "@/app/ui";
import SignalFeed from "./signal-feed";

export default function CompetitorsPage() {
  const {tick}=useRefresh();
  const [tab,setTab]=useState("news"),[rivals,setRivals]=useState<Competitor[]>([]),[refreshTick,setRefreshTick]=useState(0),[busy,setBusy]=useState(false),[error,setError]=useState(""),[status,setStatus]=useState(""),[manage,setManage]=useState(false);
  const [draft,setDraft]=useState({name:"",website:"",blog_url:"",changelog_url:""});
  const load=()=>api.competitors().then(data=>setRivals(data.competitors));
  useEffect(()=>{load().catch(e=>setError(String(e)));},[tick]);
  async function refresh(){setBusy(true);setError("");setStatus("Checking sources…");try{if(tab==="ai"){const result=await api.refreshAINews();setRefreshTick(t=>t+1);await load();setStatus(result.error||`Sources refreshed${result.created!=null?` · ${result.created} new items`:""}.`);}else{await api.refreshCompetitors();setRefreshTick(t=>t+1);await load();setStatus("Sources refreshed.");}}catch(e){setError(String(e));setStatus("");}finally{setBusy(false);}}
  return <PageBody>
    <Box sx={{display:"flex",justifyContent:"space-between",gap:2,flexWrap:"wrap",alignItems:"center",mb:3}}>
      <Segmented value={tab} onChange={setTab} options={[{id:"news",label:"All News"},{id:"ai",label:"AI to explore"}]}/>
      <Box sx={{display:"flex",gap:1,alignItems:"center",flexWrap:"wrap"}}><Typography role="status" sx={{fontSize:12,color:"text.secondary"}}>{status}</Typography><PillButton variant="text" onClick={()=>setManage(true)}>Manage sources</PillButton><PillButton disabled={busy} onClick={refresh}>{busy?"Refreshing…":tab==="ai"?"Refresh AI":"Refresh news"}</PillButton></Box>
    </Box>
    {error?<Banner severity="error">{error}</Banner>:null}
    <SignalFeed key={tab} view={tab as "news"|"ai"} rivals={rivals} tick={tick+refreshTick}/>
    <Drawer anchor="right" open={manage} onClose={()=>setManage(false)} slotProps={{paper:{sx:{width:{xs:"100%",md:540},p:3}}}}>
      <Box sx={{display:"flex",alignItems:"center",justifyContent:"space-between",mb:2}}><Typography variant="h2">News sources</Typography><RemoveButton title="Close sources" onClick={()=>setManage(false)}/></Box>
      <Typography sx={{fontSize:14,mb:2}}>AI to explore pulls model launches, viral repos, agent stacks, and builder patterns (OpenAI, Anthropic, Hugging Face, HN, Latent Space, and curated Google News queries). Competitor sources are managed below.</Typography>
      <Box component="form" onSubmit={async e=>{e.preventDefault();setBusy(true);try{await api.saveCompetitor(draft);setDraft({name:"",website:"",blog_url:"",changelog_url:""});await load();}catch(e){setError(String(e));}finally{setBusy(false);}}} sx={{display:"grid",gap:2,mb:3}}>
        {([['name','Competitor name'],['website','Website'],['blog_url','Blog / RSS URL'],['changelog_url','Changelog URL']] as const).map(([key,label])=><TextField key={key} required={key==="name"} label={label} size="small" value={draft[key]} onChange={e=>setDraft(d=>({...d,[key]:e.target.value}))}/>)}<PillButton type="submit" disabled={busy||!draft.name.trim()}>Add source</PillButton>
      </Box>
      {rivals.filter(r=>r.active!==false).map(r=><Box key={r.id} sx={{py:2,borderTop:"1px solid #eee"}}><Typography sx={{fontWeight:600}}>{r.name}</Typography><Typography sx={{fontSize:12,overflowWrap:"anywhere",color:"text.secondary"}}>{r.changelog_url||r.blog_url||r.website}</Typography></Box>)}
      {!rivals.filter(r=>r.active!==false).length ? <EmptyState>No sources yet. Add a competitor website, blog, or changelog above.</EmptyState> : null}
    </Drawer>
  </PageBody>;
}
