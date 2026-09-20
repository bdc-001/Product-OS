"use client";
import { useEffect, useState } from "react";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import TextField from "@mui/material/TextField";
import MenuItem from "@mui/material/MenuItem";
import Checkbox from "@mui/material/Checkbox";
import FormControlLabel from "@mui/material/FormControlLabel";
import Drawer from "@mui/material/Drawer";
import Skeleton from "@mui/material/Skeleton";
import Pagination from "@mui/material/Pagination";
import Link from "@mui/material/Link";
import ArrowOutwardRounded from "@mui/icons-material/ArrowOutwardRounded";
import { api, type Competitor, type CompetitorSignal } from "@/lib/api";
import { useCopilot } from "@/app/copilot/context";
import { Banner, EmptyState, FrostCard, PillButton, RemoveButton, StatusChip } from "@/app/ui";
import { apple } from "@/app/theme";

type Signal = CompetitorSignal & { focus: string[]; news_tag: string; ai_area?: string; maturity?: string; release_status: string; is_snapshot: boolean; sense_relevance: string; excerpt: string };
const observed = (value?: string | null) => value ? new Date(value).toLocaleDateString("en-IN", {day:"numeric",month:"short",year:"numeric"}) : "Date unavailable";
export default function SignalFeed({view, rivals, tick}:{view:"news"|"ai";rivals:Competitor[];tick:number}) {
  const {open} = useCopilot();
  const [creating,setCreating]=useState<number|null>(null),[tag,setTag]=useState("all");
  async function createTask(row:Signal){setCreating(row.id);setError("");try{const plan=await api.createNewsTask(row.id);open({plan:plan.id});}catch(e){setError(String(e));}finally{setCreating(null);}}
  const [q,setQ]=useState(""),[rival,setRival]=useState(0),[focus,setFocus]=useState("all"),[page,setPage]=useState(1);
  const [snapshots,setSnapshots]=useState(false);
  const [rows,setRows]=useState<Signal[]>([]),[total,setTotal]=useState(0),[loading,setLoading]=useState(true),[error,setError]=useState(""),[selected,setSelected]=useState<Signal|null>(null);
  useEffect(()=>{let active=true;setLoading(true);setError("");const timer=setTimeout(()=>api.competitorSignals({view,q,rival,focus,tag,snapshots,offset:(page-1)*12,limit:12}).then(data=>{if(active){setRows(data.signals);setTotal(data.total);}}).catch(e=>{if(active)setError(String(e));}).finally(()=>{if(active)setLoading(false);}),200);return()=>{active=false;clearTimeout(timer);};},[view,q,rival,focus,tag,snapshots,page,tick]);
  return <Box>
    <Box sx={{display:"flex",justifyContent:"space-between",gap:2,alignItems:"start",mb:3,flexWrap:"wrap"}}>
      <Box><Typography component="h2" sx={{fontSize:26,fontWeight:650,letterSpacing:"-.035em"}}>{view==="ai"?"AI worth exploring":"All your market news"}</Typography><Typography sx={{color:apple.muted,fontSize:14,mt:.75,maxWidth:700,lineHeight:1.7}}>{view==="ai"?"New models, viral GitHub repos, agent stacks (Hermes, OpenClaw, and friends), and how builders are shipping with AI — so you know what to spike this week.":"Competitor releases, pricing changes, industry news, and integrations in one feed. Turn an update into an actionable Sense task."}</Typography></Box>
      <StatusChip label="Convin Sense" tone="ink"/>
    </Box>
    <Box sx={{display:"grid",gridTemplateColumns:{xs:"1fr",md:"minmax(220px,1fr) 190px 230px"},gap:1.5,mb:2}}>
      <TextField label={view==="ai"?"Search AI to explore":"Search all news"} size="small" value={q} onChange={e=>{setQ(e.target.value);setPage(1);}}/>
      {view!=="ai"?<TextField select label="Competitor" size="small" value={rival} onChange={e=>{setRival(Number(e.target.value));setPage(1);}}><MenuItem value={0}>All competitors</MenuItem>{rivals.filter(r=>r.active!==false).map(r=><MenuItem key={r.id} value={r.id}>{r.name}</MenuItem>)}</TextField>:null}
      <TextField select label={view==="ai"?"Sense angle":"Sense capability"} size="small" value={focus} onChange={e=>{setFocus(e.target.value);setPage(1);}}><MenuItem value="all">All</MenuItem><MenuItem value="Voicebots">Voicebots</MenuItem><MenuItem value="Omnichannel orchestration">Omnichannel</MenuItem><MenuItem value="Platform">Platform / models</MenuItem></TextField>
    </Box>
    {view==="news"?<Box sx={{display:"flex",gap:1,flexWrap:"wrap",mb:2}}>{["all","Price Change","Feature Release","Feature Signal","Industry News","Compliance","Integration","Pricing"].map(label=><PillButton key={label} variant={tag===label?"filled":"gray"} onClick={()=>{setTag(label);setPage(1);}} aria-pressed={tag===label}>{label==="all"?"All updates":label}</PillButton>)}</Box>:null}
    {view==="ai"?<Box sx={{display:"flex",gap:1,flexWrap:"wrap",mb:2}}>{["all","New model","Viral repo","Agent setup","Builder pattern","Tooling","Research"].map(label=><PillButton key={label} variant={tag===label?"filled":"gray"} onClick={()=>{setTag(label);setPage(1);}} aria-pressed={tag===label}>{label==="all"?"All signals":label}</PillButton>)}</Box>:null}
    <Typography sx={{fontSize:12,color:apple.muted,mb:1}}>{view==="ai"?"Create task drafts a Sense spike in Copilot (explore / evaluate — not a ship promise). Approve there to open Jira.":"Create task automatically prepares the article, source, and acceptance criteria in Copilot. Approve there to create it in Jira."}</Typography>
    {view==="news"?<FormControlLabel control={<Checkbox size="small" checked={snapshots} onChange={e=>{setSnapshots(e.target.checked);setPage(1);}}/>} label={<Typography sx={{fontSize:12}}>Include unverified website snapshots</Typography>} sx={{mb:1}}/>:null}
    <Typography role="status" sx={{fontSize:12,color:apple.muted,mb:2}}>{loading?"Loading updates…":`${total} matching updates · articles first · newest observations first`}</Typography>
    {error?<Banner severity="error">{error}</Banner>:null}
    {loading?<Box sx={{display:"grid",gap:2}}>{[1,2,3].map(n=><Skeleton key={n} variant="rounded" height={190}/>)}</Box>:!rows.length?<EmptyState>No matching updates. Try another filter or use Refresh news to check the configured public sources.</EmptyState>:<Box sx={{display:"grid",gridTemplateColumns:{xs:"1fr",xl:"repeat(2,minmax(0,1fr))"},gap:2}}>{rows.map(row=><FrostCard key={row.id}>
      <Box component="article" sx={{display:"flex",flexDirection:"column",height:"100%",minWidth:0}}>
        <Box sx={{display:"flex",alignItems:"center",gap:1,flexWrap:"wrap",mb:1.5}}><Typography sx={{fontSize:13,fontWeight:700}}>{row.competitor_name}</Typography><Typography sx={{fontSize:12,color:apple.muted}}>Observed {observed(row.seen_at)}</Typography></Box>
        <Typography component="h3" sx={{fontSize:20,lineHeight:1.4,fontWeight:650,letterSpacing:"-.02em",overflowWrap:"anywhere",mb:1.5}}>{row.url?<Link href={row.url} target="_blank" rel="noopener noreferrer" underline="hover" color="inherit">{row.title}</Link>:row.title}</Typography>
        <Box sx={{display:"flex",gap:.75,flexWrap:"wrap",mb:1.5}}><StatusChip label={row.news_tag} tone={row.release_status==="Release announcement"&&!row.is_snapshot?"ink":"default"}/>{row.ai_area?<StatusChip label={row.ai_area}/>:row.focus.map(f=><StatusChip key={f} label={f}/>)}{row.maturity?<StatusChip label={row.maturity}/>:null}</Box>
        <Typography sx={{fontSize:15,lineHeight:1.8,color:apple.text,whiteSpace:"pre-line",overflowWrap:"anywhere",mb:2}}>{row.summary||"Open the original source to read this update."}</Typography>
        {view==="ai"?<Box sx={{p:1.5,bgcolor:"#f5f6f8",borderRadius:2,mb:2}}><Typography sx={{fontSize:11,fontWeight:700,letterSpacing:1,textTransform:"uppercase",mb:.5}}>Why explore</Typography><Typography sx={{fontSize:13,lineHeight:1.65}}>{row.sense_relevance}</Typography></Box>:null}
        <Box sx={{display:"flex",alignItems:"center",justifyContent:"space-between",gap:1,flexWrap:"wrap",mt:"auto",pt:1.5,borderTop:`1px solid ${apple.hairline}`}}><Box sx={{display:"flex",gap:1,flexWrap:"wrap"}}><PillButton variant="text" onClick={()=>setSelected(row)}>Read details</PillButton><PillButton variant="gray" disabled={creating!==null} onClick={()=>createTask(row)}>{creating===row.id?"Preparing task…":"Create task"}</PillButton></Box>{row.url?<Link href={row.url} target="_blank" rel="noopener noreferrer" sx={{display:"flex",alignItems:"center",gap:.5,fontSize:13,fontWeight:600}}>Original {row.source}<ArrowOutwardRounded sx={{fontSize:15}}/></Link>:null}</Box>
      </Box>
    </FrostCard>)}</Box>}
    {!loading&&total>12?<Pagination aria-label="Updates pages" count={Math.ceil(total/12)} page={page} onChange={(_,p)=>{setPage(p);window.scrollTo({top:0,behavior:"smooth"});}} sx={{mt:3}}/>:null}
    <Drawer anchor="right" open={Boolean(selected)} onClose={()=>setSelected(null)} slotProps={{paper:{sx:{width:{xs:"100%",md:660},p:{xs:2,md:4}}}}}>{selected?<><Box sx={{display:"flex",justifyContent:"space-between",alignItems:"center",mb:3}}><Typography sx={{fontSize:13,fontWeight:700}}>{selected.competitor_name}</Typography><RemoveButton title="Close details" onClick={()=>setSelected(null)}/></Box><Typography component="h2" sx={{fontSize:27,fontWeight:650,lineHeight:1.3,mb:2}}>{selected.title}</Typography><Typography sx={{fontSize:12,color:apple.muted,mb:3}}>Observed {observed(selected.seen_at)} · {selected.is_snapshot?"Page snapshot; publication date and release status unverified":selected.release_status}</Typography><Typography sx={{whiteSpace:"pre-wrap",fontSize:15,lineHeight:1.9,overflowWrap:"anywhere"}}>{selected.excerpt||selected.summary}</Typography><Typography sx={{fontSize:12,color:apple.muted,mt:2}}>Saved source excerpt. The observation date is when the radar found it, not the release date.</Typography>{selected.url?<Link href={selected.url} target="_blank" rel="noopener noreferrer" sx={{mt:3}}>Read the complete original source ↗</Link>:null}</>:null}</Drawer>
  </Box>;
}
