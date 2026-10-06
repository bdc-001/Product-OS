import React from 'react';
import { moduleName, productName } from "./brand";
import {Check, FileText, Headphones, Monitor, ShieldCheck, SlidersHorizontal, PhoneCall} from 'lucide-react';
import {ExamplePanels} from './ExamplePanels';
import {Motif, SignalTrail, WriteOnPath} from './Motifs';
import {AbsoluteFill, Easing, Img, interpolate, Sequence, staticFile, useCurrentFrame} from 'remotion';
import {FilmRoot, SceneLayer, useSceneCraft, CROSS_FRAMES} from './World';
import {IPhone, IPHONE_OUTER, IOSCallButton, SCREEN, IdentityCard, PaymentCard, lockupFile, headerInk} from './kit';
import type {FilmProps, Scene} from './Film';
const B='#1A62F2', N='#0A2E7A', P='#EEF4FF', D='#151515';
type Shot=Scene & {audioEnvelope?:number[];treatment:string; words:{word:string;from:number;to:number}[]; cues:Record<string,number>; callStyle?:string; subline?:string; exampleText?:string; riskExample?:string; conversationTurn?:number; exampleData?:string; endsCall?:boolean; transitionFrom?:string};
const p=(f:number,start=0,d=24)=>interpolate(f,[start,start+d],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp',easing:Easing.bezier(.16,1,.3,1)});
// Give each idea a measured entrance and a readable hold before the next thought.
const enter=(f:number,t=0,d=24):React.CSSProperties=>({opacity:p(f,t,d),transform:`translateY(${(1-p(f,t,d))*18}px)`});
function PhoneIcon({color='white',size=42}:{color?:string;size?:number}){return <svg width={size} height={size} viewBox="0 0 32 32"><path d="M7 4l5 6-3 4c3 5 5 7 9 8l4-3 6 5c-1 5-5 6-9 4C11 24 5 18 3 10 2 7 4 4 7 4" fill={color}/></svg>}
function Lock({size=55,color=B}:{size?:number;color?:string}){return <svg width={size} height={size} viewBox="0 0 48 48"><path d="M14 21v-7a10 10 0 0 1 20 0v7M10 21h28v22H10z" stroke={color} fill="none" strokeWidth="3"/><circle cx="24" cy="31" r="3" fill={color}/></svg>}
function Words({text,f,start=0,size=100,color}:{text:string;f:number;start?:number;size?:number;color?:string}){return <div style={{fontSize:size,fontWeight:650,lineHeight:1.08,letterSpacing:-size*.045,color:color??'inherit'}}>{text.split(' ').map((w,i)=><span key={i} style={{display:'inline-block',marginRight:size*.23,...enter(f,start+i*3)}}>{w}</span>)}</div>}
// Articulated characters: eyes, mouth and phone hand animate on the call's actual word intervals.
function Person({agent=false,f,talking=false,raise=1}:{agent?:boolean;f:number;talking?:boolean;raise?:number}) {
 const blink=f%117>112; const mouth=talking?4+Math.abs(Math.sin(f*.67))*9:2;
 return <svg viewBox="0 0 600 600" width="100%" height="100%">
  <defs><linearGradient id={agent?'top-a':'top-c'} x2="1" y2="1"><stop stopColor={agent?'#92B9FF':'#1964EF'}/><stop offset="1" stopColor={agent?'#1A62F2':'#0844BD'}/></linearGradient></defs>
  <ellipse cx="290" cy="564" rx="230" ry="23" fill="#0A2E7A" opacity=".08"/>
  <path d="M128 553v-79q0-107 100-139h130q110 35 112 139v79" fill={agent?'#F4F7FB':'#D9E7FE'}/>
  <g transform={`translate(0 ${Math.sin(f*.04)*2})`}>
   <path d="M203 240q-39-134 83-149 141-1 98 157l11 127-193-1z" fill="#211D27"/>
   <path d="M162 551l15-133q15-80 87-85h77q75 15 90 83l20 135" fill={`url(#${agent?'top-a':'top-c'})`}/>
   <path d="M268 296v47q30 38 60 0v-54" fill="#BA7856"/>
   <ellipse cx="223" cy="240" rx="13" ry="22" fill="#C9916B"/><ellipse cx="365" cy="240" rx="13" ry="22" fill="#C9916B"/>
   <path d="M225 190q0-57 69-57t67 59v62q-6 65-66 69-58-9-70-69z" fill="#D69A72"/>
   <path d="M219 206q-10-105 86-96 80 0 65 113-25-10-40-65-44 44-111 48" fill="#28202A"/>
   <path d="M242 220q13-8 24-1M316 219q14-7 25 1" stroke="#39242A" strokeWidth="5" fill="none" strokeLinecap="round"/>
   <ellipse cx="255" cy="239" rx="5" ry={blink?1:6} fill="#292333"/><ellipse cx="329" cy="239" rx="5" ry={blink?1:6} fill="#292333"/>
   <path d="M292 239l-5 22 9 2" stroke="#AB694E" strokeWidth="3" fill="none" strokeLinecap="round"/>
   <ellipse cx="294" cy="283" rx="14" ry={mouth} fill={talking?'#622D35':'#AE5761'}/>
   {!agent&&<><circle cx="292" cy="217" r="3" fill="#912C40"/><circle cx="222" cy="266" r="7" fill="none" stroke="#DCA743" strokeWidth="3"/><circle cx="365" cy="266" r="7" fill="none" stroke="#DCA743" strokeWidth="3"/><path d="M218 345q24 122 94 206h65q-85-126-94-207" fill="#B4D3FF" opacity=".9"/></>}
   {agent?<><path d="M212 235v-44a83 83 0 0 1 166 0v53" fill="none" stroke="#172B53" strokeWidth="9"/><rect x="205" y="222" width="19" height="45" rx="9" fill="#172B53"/><rect x="362" y="222" width="19" height="45" rx="9" fill="#172B53"/><path d="M375 255q0 47-60 45" fill="none" stroke="#172B53" strokeWidth="5"/><rect x="303" y="294" width="24" height="10" rx="5" fill="#172B53"/></>:<g transform={`rotate(${(1-raise)*52} 405 465)`}><path d="M406 465q38-64 1-171" fill="none" stroke="#D69A72" strokeWidth="33" strokeLinecap="round"/><rect x="365" y="218" width="45" height="103" rx="9" fill="#172B53" transform="rotate(-10 390 270)"/><rect x="371" y="226" width="31" height="72" rx="4" fill="#476894" transform="rotate(-10 390 270)"/><path d="M405 306l-7-24" stroke="#D69A72" strokeWidth="19" strokeLinecap="round"/></g>}
  </g>
  {agent&&<><path d="M70 526h455v27H70z" fill="#9BB6DC"/><path d="M124 421h193l26 105H149z" fill="#D1DEF0" stroke="#91AACE" strokeWidth="3"/><circle cx="231" cy="474" r="12" fill="white"/></>}
 </svg>
}
function Environment({agent=false}:{agent?:boolean}){return <svg width="100%" height="100%" viewBox="0 0 800 650" preserveAspectRatio="none" style={{position:'absolute',inset:0}}><defs><linearGradient id={agent?'room-a':'room-c'} x2="1" y2="1"><stop stopColor={agent?'#E8F0FF':'#F7F3EA'}/><stop offset="1" stopColor={agent?'#D4E4FF':'#EFE6D6'}/></linearGradient></defs><rect width="800" height="650" fill={`url(#${agent?'room-a':'room-c'})`}/><rect x="55" y="65" width="220" height="260" rx="8" fill={agent?'#D8E6FE':'#D6E9F4'}/><path d="M165 65v260M55 195h220" stroke="white" strokeWidth="9"/>{agent?<><rect x="580" y="150" width="140" height="90" rx="5" fill="url(#room-a)"/><path d="M600 214l28-25 25 11 48-35" stroke={B} strokeWidth="6" fill="none"/></>:<><path d="M600 527v-96q-95-75-48-114 60 37 52 97 14-105 67-102 27 56-66 125" fill="#669988"/><path d="M571 475h64l-10 90h-44z" fill="#D2B591"/></>}<path d="M0 577h800" stroke={agent?'#D3E0F4':'#E7DDCF'} strokeWidth="3"/></svg>}
function Phone({f}:{f:number}) {const answered=f>=51;return <div style={{width:355,height:674,borderRadius:52,border:'7px solid #172B53',background:'linear-gradient(155deg,#15397C,#081936)',boxShadow:'0 35px 90px #0A2E7A33',color:'white',display:'flex',alignItems:'center',flexDirection:'column',transform:`rotate(${answered?0:Math.sin(f*1.8)*1.1}deg)`}}><div style={{width:105,height:23,borderRadius:'0 0 20px 20px',background:'#101A2E'}}/><div style={{fontSize:20,marginTop:28}}>9:41</div><div style={{fontSize:17,color:'#AFCAFB',marginTop:38,letterSpacing:2}}>{answered?'CONNECTED':'INCOMING CALL'}</div><div style={{marginTop:20,fontSize:36,fontWeight:600}}>Customer care</div><div style={{fontSize:20,opacity:.65,marginTop:10}}>{answered?'00:00':'Mobile'}</div><div style={{marginTop:55,width:108,height:108,borderRadius:100,background:'#ffffff18',display:'grid',placeItems:'center'}}><PhoneIcon size={48}/></div><div style={{marginTop:'auto',marginBottom:52,width:79,height:79,borderRadius:90,background:answered?'#E55766':'#3BC28C',display:'grid',placeItems:'center',boxShadow:answered?'none':`0 0 0 ${8+(f%28)}px #3BC28C18`}}><PhoneIcon size={35}/></div></div>}
function Call({s,f,portrait}:{s:Shot;f:number;portrait:boolean}){
 const first=s.treatment==='call-agent', intro=first&&f<72, pull=first?p(f,53,22):1;
 const talking=s.words.some(w=>f>=w.from&&f<=w.to);
 const caption=s.captions.find(c=>f>=c.from&&f<c.to);
 return <AbsoluteFill style={{background:'transparent'}}>
 <div style={{position:'absolute',inset:portrait?'180px 30px 350px':'130px 85px 240px',display:'flex',flexDirection:portrait?'column':'row',gap:portrait?22:38,opacity:pull,transform:`scale(${.9+.1*pull})`}}>
 {[false,true].map(agent=><div key={String(agent)} style={{position:'relative',flex:1,borderRadius:28,overflow:'hidden',border:`1px solid ${P}`,boxShadow:'0 16px 55px #0A2E7A0D'}}><Environment agent={agent}/><div style={{position:'absolute',inset:portrait?'0 20%':'8px 12% 0'}}><Person agent={agent} f={f+(agent?11:0)} talking={talking&&(first===agent)} raise={first?p(f,48,25):1}/></div><div style={{position:'absolute',left:28,bottom:20,fontSize:24,fontWeight:600,color:N}}>{agent?'Sales Agent':'Customer · India'}</div></div>)}
 </div>
 <div style={{position:'absolute',left:'50%',top:portrait?'50%':'43%',transform:'translate(-50%,-50%)',opacity:pull,width:74,height:74,borderRadius:50,background:B,display:'grid',placeItems:'center',border:'8px solid white'}}><PhoneIcon size={30}/></div>
 {intro&&<div style={{position:'absolute',inset:0,display:'grid',placeItems:'center',opacity:1-p(f,60,12),transform:`scale(${1-pull*.08})`}}><Phone f={f}/></div>}
 <div style={{position:'absolute',left:portrait?80:240,right:portrait?80:240,bottom:portrait?180:100,textAlign:'center',minHeight:80,fontSize:portrait?39:43,lineHeight:1.3,color:D}}>{caption?.text}</div>
 <div style={{position:'absolute',top:50,left:60,fontSize:18,letterSpacing:2,color:'#657388'}}>ILLUSTRATIVE CUSTOMER CALL</div>
 </AbsoluteFill>
}
function spokenLine(words:{word:string}[]){return words.map(w=>w.word).join(' ')}
function Line({words,on,dark=false}:{words:{word:string}[];on:boolean;dark?:boolean}) {
 return <span style={{color:dark?'#F1F1F1':D,opacity:on?1:.22}}>{spokenLine(words)}</span>;
}
// Three fixed bars: they stand up for the spoken interval and sit down between words. No per-frame noise.
function VoiceBars({talking,level}:{talking:boolean;level?:number}) {
 const frame=useCurrentFrame();
 const strength=level??(talking?.45:0);
 return <div style={{display:'flex',alignItems:'center',gap:3,height:24}}>{[.55,1,.75,.95,.45].map((h,i)=><div key={i} style={{width:3,borderRadius:2,background:'currentColor',height:3+strength*h*(15+5*Math.sin(frame*.25+i)),opacity:.45+strength*.55}}/>)}</div>;
}
// Expanding rings ride the Marimba beat. Each ring is a one-shot fade, not a shimmer.
function IncomingRings({f,from}:{f:number;from:number}) {
 const t=f-from;
 return <svg viewBox="0 0 700 420" style={{position:'absolute',top:280,left:'50%',transform:'translateX(-50%)',width:700,height:420,overflow:'visible',pointerEvents:'none'}}>
  {[0,1,2].map(i=>{if(t<i*12) return null; const local=((t-i*12)%72)/72;
   return <circle key={i} cx="350" cy="150" r={90+local*100} fill="none" stroke="#5A90FF" strokeWidth={3.5} opacity={.18*(1-local)}/>})}
 </svg>;
}
// The handset is one iPhone drawn once in phone pixels. Portrait shows it full frame; landscape
// scales the identical screen into the same device body, so neither aspect is a crop of the other.
const SCREEN_W=SCREEN.width, SCREEN_H=SCREEN.height;
type Turn={speaker:string;language?:string;words:{word:string;from:number;to:number}[];start:number;end:number;detail?:string};
function callTurns(scenes:Shot[]):Turn[] {
 return scenes.filter(x=>x.treatment.startsWith('call-')&&x.words&&x.words.length).map(x=>({
  speaker:x.voice==='agent'?'Sales Agent':'Customer', language:x.language,
  words:x.words.map(w=>({word:w.word,from:w.from+x.from,to:w.to+x.from})),
  start:x.from+x.words[0].from, end:x.from+x.words[x.words.length-1].to, detail:x.exampleData}));
}
const CALL_HEADER=88;
function callPhase(global:number, firstSpeech:number) {
 const connectAt=Math.max(84, firstSpeech-18), lockEnd=32, answerFor=20, slideFrom=connectAt-answerFor;
 const incoming=global>=lockEnd&&global<connectAt;
 return {connectAt, lockEnd, lock:global<lockEnd, incoming, connected:global>=connectAt, slide:p(global,slideFrom,answerFor), ringing:incoming, beat:incoming?Math.max(0,Math.sin((global-lockEnd)*Math.PI/24)):0};
}
function callLayout(portrait:boolean) {
 const scale=portrait?1.70:0.94;
 const left=portrait?Math.round((1080-IPHONE_OUTER.width*scale)/2):48;
 const top=portrait?CALL_HEADER+24:CALL_HEADER+Math.round((1080-CALL_HEADER-40-IPHONE_OUTER.height*scale)/2);
 return {scale, left, top};
}
function PhoneScreen({s,f,global,hanging,talking,overlay,firstSpeech,showTranscript=false}:{s:Shot;f:number;global:number;hanging:boolean;talking:boolean;overlay?:React.ReactNode;firstSpeech:number;showTranscript?:boolean}) {
 const {connectAt, lockEnd, lock, incoming, connected, slide, beat}=callPhase(global, firstSpeech);
 const seconds=Math.max(0,Math.floor((global-connectAt)/30));
 const speaker=s.voice==='agent'?'Sales Agent':'Customer';
 const lineOn=!hanging&&f>=(s.words[0]?.from??0);
 const field=lock?'linear-gradient(180deg,#F7FAFF 0%,#EEF4FF 48%,#E4EEFF 100%)':'radial-gradient(ellipse at 35% 12%,#506173 0%,#28333F 46%,#121920 100%)';
 return <div style={{position:'relative',width:SCREEN_W,height:SCREEN_H,background:field,color:lock?'#050505':'#F1F1F1',overflow:'hidden'}}>
  {lock&&<><div style={{textAlign:'center',marginTop:520,fontSize:168,fontWeight:200,letterSpacing:-8}}>9:41</div><div style={{textAlign:'center',fontSize:42,color:'#3A3A3C'}}>Sunday, September 20</div><div style={{margin:'32px auto',background:'#111',borderRadius:40,width:120,height:58,color:'#39C265',display:'grid',placeItems:'center',fontSize:32}}>☾</div>{global>=8&&<div style={{position:'absolute',top:120,left:70,right:70,padding:'28px 34px',borderRadius:28,background:'white',boxShadow:'0 18px 50px #00000024',...enter(global,8,12)}}><div style={{fontSize:22,color:'#718098',letterSpacing:1.5}}>INCOMING CALL</div><div style={{fontSize:42,fontWeight:600,marginTop:8,color:'#050505'}}>Sales Agent</div><div style={{fontSize:26,color:'#8A93A3',marginTop:6}}>mobile</div></div>}</>}
  {incoming&&<><IncomingRings f={global} from={lockEnd}/><div style={{position:'absolute',top:380,width:'100%',textAlign:'center',...enter(global,lockEnd)}}><div style={{fontSize:44,letterSpacing:3,color:'#8E8E93',marginBottom:48}}>Voice Call</div><div style={{width:220,height:220,borderRadius:110,background:'#1C1C1E',margin:'0 auto 48px',display:'grid',placeItems:'center',boxShadow:`0 0 0 ${18+beat*26}px #1A62F233`,transform:`scale(${1+beat*.03})`}}><PhoneIcon color="#D7E4FF" size={88}/></div><div style={{fontSize:108,fontWeight:500}}>Sales Agent</div><div style={{fontSize:44,marginTop:18,color:'#8E8E93'}}>mobile</div></div><div style={{position:'absolute',bottom:520,left:210,right:210,display:'flex',justifyContent:'space-between',alignItems:'flex-start'}}><div style={{textAlign:'center',width:200}}><IOSCallButton kind="End" danger size={168}/><div style={{fontSize:32,marginTop:20,color:'#EBEBF0'}}>Decline</div></div><div style={{textAlign:'center',width:200,transform:`scale(${1+slide*.06})`}}><div style={{width:168,height:168,borderRadius:84,background:'#34C759',display:'grid',placeItems:'center',margin:'0 auto',boxShadow:`0 0 0 ${12+beat*18}px #34C75944`}}><PhoneIcon size={72}/></div><div style={{fontSize:32,marginTop:20,color:'#EBEBF0'}}>Accept</div></div></div></>}
  {connected&&<><div style={{position:'absolute',inset:0,pointerEvents:'none',background:'#5C7188',opacity:(1-p(global,connectAt,24))*.3}}/><div style={{position:'absolute',top:260,width:'100%',textAlign:'center'}}><div style={{fontSize:92,fontWeight:500}}>Sales Agent</div><div style={{fontSize:40,fontWeight:600,marginTop:18,color:'#8E8E93'}}>{hanging?'Call Ended':`0:${String(seconds).padStart(2,'0')}`}</div></div><div style={{position:'absolute',top:560,left:'50%',transform:'translateX(-50%)',width:780,opacity:hanging?.22:1,display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:'56px 48px'}}>{['Mute','Keypad','Speaker','Add call','FaceTime','Contacts'].map(label=><div key={label} style={{textAlign:'center'}}><div style={{margin:'0 auto',width:192,display:'grid',placeItems:'center'}}><IOSCallButton kind={label} active={label==='Speaker'}/></div><div style={{fontSize:36,marginTop:16,whiteSpace:'nowrap',color:'#EBEBF0'}}>{label}</div></div>)}</div><div style={{position:'absolute',bottom:780,left:'50%',opacity:hanging?.22:1,transform:`translateX(-50%) rotate(135deg) scale(${hanging?0.92:1})`}}><IOSCallButton kind="End" danger size={176}/></div><div style={{position:'absolute',bottom:280,left:80,right:80,textAlign:'center'}}>{!hanging&&<div style={{color:'#AFCAFB',fontSize:32,letterSpacing:1,marginBottom:20,display:'inline-flex',alignItems:'center',justifyContent:'center',gap:14,padding:'12px 24px',borderRadius:999,background:talking?'#1A62F233':'transparent'}}><VoiceBars talking={talking} level={s.audioEnvelope?.[Math.max(0,Math.floor(f))]}/><span>{speaker}</span></div>}<div style={{fontFamily:"'KohinoorFilm','Kohinoor Devanagari',sans-serif",fontSize:64,minHeight:170,lineHeight:1.4,fontWeight:hanging?600:undefined}}>{hanging?'Call ended':showTranscript?<Line words={s.words} on={lineOn} dark/>:null}</div></div>{!hanging&&overlay}</>}
 </div>;
}
function CallTranscript({turns,global,hanging,left,top}:{turns:Turn[];global:number;hanging:boolean;left:number;top:number}) {
 const shown=turns.filter(t=>global>=t.start-8);
 const active=turns.filter(t=>global>=t.start).slice(-1)[0];
 return <div style={{position:'absolute',left,right:48,top,bottom:108,background:'white',borderRadius:30,border:'1px solid #E1E9F6',boxShadow:'0 30px 90px #0A2E7A14',padding:'36px 42px',overflow:'hidden'}}>
  <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',borderBottom:'1px solid #EDF2FB',paddingBottom:22,marginBottom:28}}>
   <div style={{display:'flex',alignItems:'center',gap:16}}><div style={{width:38,height:38,overflow:'hidden',flexShrink:0}}><Motif visual="call" size={38}/></div><div><div style={{fontSize:19,letterSpacing:2.5,color:'#7A8AA3'}}>LIVE TRANSCRIPT</div><div style={{fontSize:27,color:N,marginTop:8}}>Credit card application</div></div></div>
   <div style={{textAlign:'right'}}><Img src={staticFile('brand-logo-light.svg')} style={{width:132,display:'block',marginLeft:'auto'}}/><div style={{display:'flex',alignItems:'center',justifyContent:'flex-end',gap:9,color:hanging?'#9AA7BC':B,fontSize:18,marginTop:9}}><span style={{width:9,height:9,borderRadius:6,background:hanging?'#9AA7BC':B}}/>{hanging?'Call ended':'Call in progress'}</div></div>
  </div>
  <div style={{display:'flex',gap:32,alignItems:'center',marginBottom:24,padding:'16px 20px',background:'#F7F9FD',borderRadius:14,color:'#66758A',fontSize:18}}><PhoneCall size={22}/><span>Outbound call</span><span>English → हिन्दी</span><span style={{marginLeft:'auto',color:B}}>Conversation transcript</span></div>
  {shown.length===0&&<div style={{padding:'70px 30px',textAlign:'center',color:'#7A8AA3'}}><Headphones size={42} strokeWidth={1.4}/><div style={{fontSize:28,marginTop:20}}>Waiting for the call to connect</div><div style={{fontSize:20,marginTop:12}}>The conversation will appear here.</div></div>}
  {shown.map((t,i)=>{
   const live=t===active&&!hanging, past=!live;
   const speaking=live&&t.words.some(w=>global>=w.from&&global<=w.to+3);
   return <Reveal key={i} f={global} t={t.start-8} d={22} r={16} style={{marginBottom:16,opacity:past?.8:1,background:live?'#F0F5FF':'#FAFBFE',borderLeft:live?`5px solid ${B}`:'5px solid transparent',padding:'14px 18px 14px 20px',borderRadius:16}}>
    <div style={{display:'flex',alignItems:'center',gap:12,marginBottom:9}}>
     {live&&<VoiceBars talking={speaking}/>}
     <span style={{fontSize:19,fontWeight:650,color:t.speaker==='Sales Agent'?B:'#5A6B85'}}>{t.speaker}</span>
     <span style={{fontSize:17,padding:'3px 11px',borderRadius:999,background:P,color:'#5E7290'}}>{t.language==='hi'?'हिन्दी':'English'}</span>
    </div>
    <div style={{fontFamily:"'KohinoorFilm','Kohinoor Devanagari',sans-serif",fontSize:34,lineHeight:1.4,color:D}}>{spokenLine(t.words)}</div>
    {t.detail&&global>=t.start+(t.end-t.start)*.5&&<div style={{display:'inline-flex',alignItems:'center',gap:12,marginTop:14,padding:'11px 20px',borderRadius:999,background:'#FDF1E7',border:'1px solid #EFCBAC',...enter(global,t.start+(t.end-t.start)*.5,12)}}>
     <span style={{width:11,height:11,borderRadius:6,background:'#C4703F'}}/><span style={{fontSize:23,color:'#8A4F27'}}>Demo identifier · {t.detail}</span>
    </div>}
   </Reveal>;
  })}
 </div>;
}
function ReferenceCall({s,f,portrait,scenes}:{s:Shot;f:number;portrait:boolean;scenes:Shot[]}) {
 const global=f+s.from;
 const turns=callTurns(scenes);
 const firstSpeech=turns[0]?.start??90;
 const {ringing, beat, connected}=callPhase(global, firstSpeech);
 const last=s.words[s.words.length-1];
 const hangFrom=s.endsCall&&last?Math.min(last.to+4,Math.max(0,s.frames-12)):s.frames+1;
 const hanging=Boolean(s.endsCall)&&f>=hangFrom;
 const fadeOut=1;
 const talking=!hanging&&s.words.some(w=>f>=w.from&&f<=w.to);
 const detailAt=s.words.length?s.words[Math.floor(s.words.length*.5)].from:0;
 const overlay=portrait?<div style={{position:'absolute',top:1180,left:70,right:70,display:'flex',flexDirection:'column',alignItems:'center',gap:30}}>
  <div style={{display:'inline-flex',alignItems:'center',gap:18,padding:'17px 34px',borderRadius:999,background:connected?'#1C1C1E':P,fontSize:40}}>
   {s.languageFrom&&<><span style={{color:connected?'#8E8E93':'#6A7890'}}>{s.languageFrom==='en'?'English':'हिन्दी'}</span><span style={{color:B}}>→</span></>}
   <span style={{color:B,fontWeight:650}}>{s.language==='hi'?'हिन्दी':'English'}</span>
  </div>
  {s.exampleData&&f>=detailAt&&<div style={{textAlign:'center',padding:'26px 34px',borderRadius:26,background:'#FDF1E7',border:'1px solid #EFCBAC',...enter(f,detailAt,12)}}>
   <div style={{fontSize:35,color:'#8A4F27'}}>Personal detail in the conversation</div>
   <div style={{fontSize:45,color:'#7A4420',fontWeight:600,marginTop:12}}>{s.exampleData}</div>
  </div>}
 </div>:null;
 const screen=<PhoneScreen s={s} f={f} global={global} hanging={hanging} talking={talking} overlay={overlay} firstSpeech={firstSpeech} showTranscript={portrait}/>;
 const note=<div style={{position:'absolute',bottom:16,left:portrait?72:48,color:'#8790A1',fontSize:13,letterSpacing:1.5}}>ILLUSTRATIVE SALES CALL · DEMO DATA</div>;
 const font="'Helvetica Neue','KohinoorFilm',Arial,sans-serif";
 const {luma}=useSceneCraft();
 const brand=<><Img src={staticFile(lockupFile(luma))} style={{position:'absolute',width:148,top:28,left:portrait?72:48,zIndex:8}}/><div style={{position:'absolute',top:36,right:portrait?72:48,fontSize:16,letterSpacing:2.2,color:headerInk(luma),zIndex:8}}>PII MASKING</div></>;
 const {scale,left,top}=callLayout(portrait);
 const phone=<IPhone scale={scale} ringing={ringing} beat={beat} appearance={connected||ringing?'dark':'light'} style={{position:'absolute',left,top}}>{screen}</IPhone>;
 const panelLeft=left+Math.round(IPHONE_OUTER.width*scale)+32;
 if(portrait) return <AbsoluteFill style={{background:'transparent',fontFamily:font,opacity:fadeOut}}>{brand}{phone}{note}</AbsoluteFill>;
 return <AbsoluteFill style={{background:'transparent',fontFamily:font,opacity:fadeOut}}>
  {brand}
  {phone}
  <CallTranscript turns={turns} global={global} hanging={hanging} left={panelLeft} top={top}/>
  {note}
 </AbsoluteFill>;
}
// The product mark for the reveal: a lock whose shackle is drawn shut on the cue.
function LockSeal({f,t=0,size=130,color=B}:{f:number;t?:number;size?:number;color?:string}) {
 const shut=p(f,t,17);
 return <svg width={size} height={size} viewBox="0 0 120 120">
  <g transform={`translate(0 ${(1-shut)*-9})`} strokeLinecap="round"><WriteOnPath d="M36 56V38a24 24 0 0 1 48 0v18" progress={shut} color={color} width={9}/></g>
  <g opacity={p(f,t+5,12)}><rect x="25" y="55" width="70" height="53" rx="13" fill={color}/><circle cx="60" cy="76" r="6.5" fill="white"/><rect x="56.5" y="78" width="7" height="15" rx="3.5" fill="white"/></g>
 </svg>;
}
function BenefitIcon({kind,f,t}:{kind:number;f:number;t:number}) {
 const on=p(f,t,14);
 return <svg width="78" height="78" viewBox="0 0 64 64" strokeLinecap="round" strokeLinejoin="round">
  {kind===0?<><WriteOnPath d="M8 14h48v32H34L20 58V46H8z" progress={on} color={B} width={5}/>{[24,34,44].map(cx=><circle key={cx} cx={cx} cy="30" r="3.2" fill={B} opacity={p(f,t+8,10)}/>)}</>
   :kind===1?<><WriteOnPath d="M8 54h48" progress={on} color={B} width={5}/>{[0,1,2].map(i=><rect key={i} x={14+i*15} y={46-(14+i*12)*on} width="11" height={(14+i*12)*on} rx="3" fill={B}/>)}<g opacity=".45"><WriteOnPath d="M16 26l12-10 10 7 12-14" progress={on} color={B} width={5}/></g></>
   :<><WriteOnPath d="M32 12a22 22 0 1 1-.1 0" progress={on} color={B} width={5}/><WriteOnPath d="M32 34l13-10" progress={p(f,t+8,10)} color={B} width={5}/><circle cx="32" cy="34" r="4" fill={B} opacity={on}/></>}
 </svg>;
}
// A surface is wiped open rather than flown in, so it reads as placed instead of floating.
function Reveal({f,t=0,d=24,dir='up',r=20,style,children}:{f:number;t?:number;d?:number;dir?:'up'|'down'|'left'|'right';r?:number;style?:React.CSSProperties;children:React.ReactNode}) {
 const x=p(f,t,d), hide=(1-x)*100;
 const inset=dir==='up'?`${hide}% 0 0 0`:dir==='down'?`0 0 ${hide}% 0`:dir==='left'?`0 ${hide}% 0 0`:`0 0 0 ${hide}%`;
 return <div style={{...style,clipPath:x>=1?undefined:`inset(${inset} round ${r}px)`,transform:`translateY(${(1-x)*8}px)`}}>{children}</div>;
}
// Connections are drawn along their real geometry and carry a motion-blurred signal.
function Signal({f,t=0,vertical=false,length=90}:{f:number;t?:number;vertical?:boolean;length?:number}) {
 const W=vertical?26:length, H=vertical?length:26, mid=13;
 const d=vertical?`M${mid},2 L${mid},${length-2}`:`M2,${mid} L${length-2},${mid}`;
 return <div style={{position:'relative',flexShrink:0,width:W,height:H}}>
  <svg viewBox={`0 0 ${W} ${H}`} style={{position:'absolute',inset:0,width:'100%',height:'100%',overflow:'visible'}}>
   <path d={d} fill="none" stroke="#CBDDFB" strokeWidth="4" strokeLinecap="round"/>
   <WriteOnPath d={d} progress={p(f,t,13)} color={B} width={4}/>
  </svg>
  {f>t+9&&<SignalTrail d={d} start={t+9} viewW={W} viewH={H} color={B} size={13}/>}
 </div>;
}
const lin=(f:number,a:number,b:number)=>interpolate(f,[a,b],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
// Each destination is drawn and lit on the word that names it, and the value keeps travelling to it.
function SpreadMap({f,portrait,value,starts}:{f:number;portrait:boolean;value:string;starts:number[]}) {
 const W=portrait?920:1640, H=portrait?760:520;
 const ox=portrait?W/2:450, oy=portrait?106:H/2;
 const cardX=portrait?170:920, cardW=portrait?700:720, cardH=portrait?112:104;
 const firstY=portrait?250:0, step=portrait?122:(H-cardH)/3;
 // Portrait routes every line down a left gutter so the cards never sit on top of the connectors.
 const sx=ox, sy=portrait?oy+76:oy;
 const routes=['Recordings','Transcripts','Screens','Reports'].map((name,i)=>{
  const y=firstY+i*step, cy=y+cardH/2;
  const c1x=portrait?260:670, c1y=portrait?sy+14:oy, c2x=portrait?70:790, c2y=portrait?cy-70:cy;
  const ex=portrait?70:cardX;
  return {name,y,cy,d:`M${sx},${sy} C${c1x},${c1y} ${c2x},${c2y} ${ex},${cy}${portrait?` L${cardX},${cy}`:''}`,t0:Math.max(0,starts[i]-10)};
 });
 return <div style={{position:'relative',width:'100%',paddingBottom:`${H/W*100}%`}}>
  <svg viewBox={`0 0 ${W} ${H}`} style={{position:'absolute',inset:0,width:'100%',height:'100%'}}>
   <g opacity={p(f,0,10)}>
    <rect x={portrait?(W-540)/2:0} y={oy-76} width={portrait?540:450} height="152" rx="26" fill="white"/>
    <text x={portrait?W/2:44} y={oy-20} textAnchor={portrait?'middle':'start'} fontSize="22" letterSpacing="2" fill="#7A8AA3">SHARED ON THE CALL</text>
    <text x={portrait?W/2:44} y={oy+34} textAnchor={portrait?'middle':'start'} fontSize="36" fontWeight="600" fill={N}>{value}</text>
   </g>
   {routes.map(({name,y,cy,d,t0})=><g key={name}>
    <g opacity=".5"><WriteOnPath d={d} progress={p(f,t0,14)} color="#FFFFFF" width={3.5}/></g>
    <g opacity={p(f,t0+6,11)}>
     <rect x={cardX} y={y} width={cardW} height={cardH} rx="24" fill="white"/>
     <text x={cardX+38} y={cy+2} fontSize="34" fontWeight="600" fill={N} dominantBaseline="middle">{name}</text>
     <g opacity={p(f,t0+16,9)}><text x={cardX+cardW-38} y={cy+2} fontSize="27" textAnchor="end" fill="#B86648" dominantBaseline="middle">{value}</text></g>
    </g>
   </g>)}
  </svg>
  {routes.map(({name,d,t0})=>p(f,t0,14)>.2?<SignalTrail key={name} d={d} start={t0+4} viewW={W} viewH={H} color="#FFFFFF" size={18}/>:null)}
 </div>;
}
// Physical ID-1 artefacts. They sit on the desk; they do not hinge in 3D.
function DetailCard({f,t=0,kind,label,value,w=430}:{f:number;t?:number;kind:'pan'|'card';label:string;value:string;w?:number}) {
 const enter=p(f,t,16);
 return <div style={{width:w}}>{kind==='card'
  ?<PaymentCard label={label} value={value} enter={enter}/>
  :<IdentityCard label={label} value={value} enter={enter}/>}</div>;
}
function ProtectFlow({f, portrait, pick, place}:{f:number; portrait:boolean; pick:number; place:number}) {
 const groups=[{title:'Sensitive identifiers',subtitle:'Choose which values to protect',items:['PAN number','Credit card number'],icons:[ShieldCheck,ShieldCheck],at:pick},
  {title:'Protection surfaces',subtitle:'Choose where masking applies',items:['Transcripts','Recordings','Screens'],icons:[FileText,Headphones,Monitor],at:place}];
 const applied=p(f,place+32,24);
 return <div style={{background:'#FFFFFF',color:N,borderRadius:26,border:'1px solid #DBE5F6',overflow:'hidden',boxShadow:'0 28px 80px #061D4830'}}>
  <div style={{display:'flex',alignItems:'center',gap:18,padding:portrait?'24px 28px':'24px 36px',borderBottom:'1px solid #E7EDF7',background:'#F8FAFE'}}><SlidersHorizontal color={B} size={26}/><div style={{fontSize:25,fontWeight:600}}>PII Masking</div><span style={{fontSize:17,color:'#64748B',marginLeft:'auto'}}>Configuration example</span></div>
  <div style={{display:'grid',gridTemplateColumns:portrait?'1fr':'1fr 1fr',gap:portrait?24:40,padding:portrait?28:36}}>
   {groups.map(group=><div key={group.title}><div style={{fontSize:27,fontWeight:600}}>{group.title}</div><div style={{fontSize:20,color:'#748198',marginTop:8,marginBottom:20}}>{group.subtitle}</div>
    {group.items.map((label,i)=>{const Icon=group.icons[i],checked=p(f,group.at+i*12,24);return <div key={label} style={{display:'flex',alignItems:'center',gap:18,padding:'18px 20px',marginTop:12,borderRadius:14,border:`1px solid ${checked>.5?'#B7D0FF':'#E3EAF5'}`,background:checked>.5?'#F3F7FF':'#FFFFFF'}}><Icon size={26} color={B} strokeWidth={1.7}/><span style={{fontSize:24}}>{label}</span><div style={{marginLeft:'auto',width:28,height:28,borderRadius:7,border:`1.5px solid ${checked>.5?B:'#CAD5E6'}`,background:checked>.5?B:'white',display:'grid',placeItems:'center'}}><Check size={20} color='white' style={{opacity:checked}}/></div></div>})}
   </div>)}
  </div>
  <div style={{display:'flex',alignItems:'center',gap:14,padding:'20px 36px',borderTop:'1px solid #E7EDF7',background:'#F8FAFE',fontSize:21}}><ShieldCheck color={B} size={26}/><span>2 identifiers · 3 surfaces</span><span style={{marginLeft:'auto',color:B,opacity:applied}}>Protection configured <Check size={19} style={{verticalAlign:'middle'}}/></span></div>
 </div>;
}
// The playhead finds the sensitive band, the band warns, then it collapses on the spoken cue.
function Wave({f,maskAt,frames,height=170}:{f:number;maskAt:number;frames:number;height?:number}) {
 const collapse=p(f,maskAt,12), head=lin(f,4,frames-14), scale=height/170, warn=head>=.38&&head<=.62&&collapse<.15, flash=1-p(f,maskAt,8);
 return <div style={{display:'flex',height,width:'100%',alignItems:'center',gap:5,position:'relative'}}>
  {Array.from({length:68},(_,i)=>{const mid=i>=28&&i<39, lift=Math.max(0,1-Math.abs(i/67-head)*11);
   const full=(20+Math.abs(Math.sin(i*7.13))*92)*(1+.2*lift)*scale;
   return <div key={i} style={{flex:1,minWidth:0,borderRadius:6,height:mid?full+(10*scale-full)*collapse:full,background:mid?(collapse>.35?N:warn?'#E07A3A':'#D79067'):'#7DABFF'}}/>;})}
  <div style={{position:'absolute',top:0,bottom:0,left:`${head*100}%`,width:3,borderRadius:2,background:B,opacity:.7}}/>
  {warn&&<div style={{position:'absolute',left:'41%',right:'41%',top:-8,bottom:-8,border:`2px solid #E07A3A`,borderRadius:10,opacity:.7}}/>}
  {collapse>0&&<div style={{position:'absolute',left:'38%',top:-4,display:'flex',alignItems:'center',gap:10,padding:'8px 16px 8px 10px',borderRadius:999,background:N,color:'white',fontSize:20,letterSpacing:1,opacity:collapse,transform:`translateY(${(1-collapse)*18}px) scale(${.86+.14*collapse})`}}><div style={{width:28,height:28,overflow:'hidden'}}><Motif visual="mask" dark size={28}/></div>beep</div>}
  {flash>0&&collapse>0&&<div style={{position:'absolute',left:'41%',width:'18%',top:0,bottom:0,background:`rgba(255,255,255,${.55*flash})`,borderRadius:8}}/>}
 </div>;
}
function Content({s,f,portrait}:{s:Shot;f:number;portrait:boolean}) {
 const k=s.treatment, big=portrait?82:100, cue=(key:string,fallback=0)=>s.cues[key]??fallback;
 const fadeIn=1;
 const blue=['reveal','spread'].includes(k), endcard=k==='cta';
 const {luma}=useSceneCraft();
 const darkField=luma==='dark'||blue||endcard;
 const field=endcard?'linear-gradient(140deg,#0A2E7A 0%,#1552D8 55%,#1A62F2 100%)':blue?'linear-gradient(140deg,#1A62F2 0%,#0A2E7A 58%,#151515 100%)':'transparent';
 const ink=blue||endcard?'white':(darkField?'#F1F1F1':D);
 const note=darkField?'#F1F1F1':B;
 const card:React.CSSProperties={background:'white',border:'2px solid #E1E9F6',borderRadius:24,boxShadow:'0 20px 60px #0A2E7A0B',padding:32};
 let body:React.ReactNode;
 if(k==='shared'&&s.riskExample)body=<><Words text="Some details carry more risk." f={f} size={portrait?66:92}/><div style={{display:'flex',flexDirection:portrait?'column':'row',gap:portrait?28:48,marginTop:portrait?40:52,justifyContent:'center',alignItems:'flex-end'}}><DetailCard f={f} t={cue('PAN',8)} kind="pan" label="IDENTITY · PAN NUMBER" value="ABCDE1234F" w={portrait?820:560}/><DetailCard f={f} t={cue('credit',20)} kind="card" label="PAYMENT · CARD NUMBER" value="4242 4242 4242 4242" w={portrait?820:560}/></div><div style={{fontSize:portrait?30:30,color:note,marginTop:34,...enter(f,cue('details',34))}}>Useful in the conversation. Sensitive beyond it.</div></>;
 else if(k==='shared')body=<><Words text="One personal detail." f={f} size={big}/><div style={{marginTop:30,fontSize:36,color:note}}>{s.subline}</div></>;
 else if(k==='question')body=<div style={{maxWidth:1300,margin:'auto',textAlign:'center'}}><div style={{fontSize:32,color:'#66758A',marginBottom:36,...enter(f)}}>But after the call...</div><Words text="Where do those details go?" f={f} start={cue('where')} size={portrait?96:134}/><div style={{height:8,background:B,width:210,margin:'46px auto 0',borderRadius:4,transform:`scaleX(${p(f,cue('details'))})`}}/></div>;
 else if(k==='spread')body=<div style={{display:'flex',flexDirection:'column'}}><Words text="One detail. Many places." f={f} size={portrait?70:92} color="white"/><div style={{marginTop:portrait?44:32}}><SpreadMap f={f} portrait={portrait} value={s.riskExample?'PAN · ABCDE1234F':'•••• ••4321'} starts={[cue('recordings',18),cue('transcripts',26),cue('screens',34),cue('reports',42)]}/></div><div style={{marginTop:portrait?40:28,fontSize:portrait?28:26,color:'#D6E4FF',...enter(f,cue('reports',42)+10)}}>The conversation travels. So can personal information.</div></div>;
 else if(k==='reveal')body=<div style={{textAlign:'center',margin:'auto',width:'100%'}}><div style={{fontSize:portrait?51:64,lineHeight:1.25,opacity:1-p(f,cue('Meet'),12),transform:`translateY(${-30*p(f,cue('Meet'))}px)`}}>Keep the insight.<br/><span style={{color:'#BED6FF',...enter(f,cue('Protect'))}}>Protect what's personal.</span></div><div style={{marginTop:-36,overflow:'hidden',maxHeight:p(f,Math.max(0,cue('Meet')-8),16)*640,...enter(f,cue('Meet'),18)}}><div style={{width:portrait?210:244,height:portrait?210:244,borderRadius:'50%',background:'white',display:'grid',placeItems:'center',margin:'0 auto 30px',transform:`scale(${.8+.2*p(f,cue('Meet'),16)})`,boxShadow:'0 26px 64px #0A2E7A33'}}><LockSeal f={f} t={cue('Meet')+6} size={portrait?118:136}/></div><div style={{fontSize:25,letterSpacing:4,color:'#C5DBFF',marginBottom:20}}>INTRODUCING</div><Words text="PII Masking" f={f} start={cue('PII')} size={portrait?108:144} color="white"/><div style={{marginTop:26,fontSize:32,...enter(f,cue('Masking'))}}>by {productName()}</div></div></div>;
 else if(k==='select')body=<><Words text="Your rules. Your protection." f={f} size={big}/><div style={{marginTop:portrait?32:40}}><ProtectFlow f={f} portrait={portrait} pick={cue('sensitive',0)} place={cue('where',20)}/></div><div style={{fontSize:19,color:darkField?'#BED6FF':'#738197',marginTop:34,textAlign:'center'}}>Illustrative configuration</div></>;
 else if(k==='transcript'&&s.examples?.length)body=<><Words text="The value disappears." f={f} size={big}/><div style={{marginTop:48}}><ExamplePanels examples={s.examples} frames={s.exampleFrames} frame={f} portrait={portrait}/></div><div style={{display:'flex',justifyContent:'space-between',gap:30,marginTop:32,...enter(f,cue('Stays'))}}><div style={{fontSize:portrait?48:56,fontWeight:600,color:B}}>The meaning stays.</div><div style={{fontSize:26,lineHeight:1.4,color:'#6E7C90',maxWidth:570}}>Keep intent and coaching context<br/>without repeating sensitive values.</div></div></>;
 else if(k==='transcript')body=<><Words text="The value disappears." f={f} size={big}/></>;
 else if(k==='audio'){const mask=f>=cue('replaced'),swap=p(f,cue('replaced'),10);body=<><Words text="Hear the conversation." f={f} size={big}/><Reveal f={f} t={6} d={15} r={24} style={{...card,marginTop:55,padding:portrait?38:50,overflow:'hidden'}}><div style={{fontSize:23,color:'#718098'}}>CALL RECORDING</div><Wave f={f} maskAt={cue('replaced')} frames={s.frames} height={portrait?250:170}/><div style={{position:'relative',height:36,textAlign:'center',fontSize:26}}><div style={{position:'absolute',inset:0,color:'#B86648',opacity:1-swap,transform:`translateY(${-10*swap}px)`}}>Sensitive segment detected</div><div style={{position:'absolute',inset:0,color:B,opacity:swap,transform:`translateY(${10*(1-swap)}px)`}}>Sensitive segment masked</div></div><div style={{height:5,background:P,marginTop:26}}><div style={{height:5,background:B,width:`${lin(f,4,s.frames-14)*100}%`}}/></div></Reveal><div style={{marginTop:42,fontSize:portrait?49:65,fontWeight:600,color:note,...enter(f,cue('beep'))}}>Protect the private detail.</div></>}
 else if(k==='benefit')body=<><Words text="Improve the conversation." f={f} size={big}/><div style={{display:'flex',flexDirection:portrait?'column':'row',gap:portrait?24:32,marginTop:portrait?44:52}}>{['Customer intent','Coaching opportunities','Conversation quality'].map((t,i)=><Reveal key={t} f={f} t={cue('improve',8)+i*10} d={14} r={24} style={{...card,flex:1,padding:portrait?'38px 38px':'52px 42px',display:'flex',flexDirection:portrait?'row':'column',alignItems:portrait?'center':'flex-start',gap:portrait?26:38}}><BenefitIcon kind={i} f={f} t={cue('improve',8)+6+i*10}/><div style={{fontSize:portrait?34:40,fontWeight:600,color:N,lineHeight:1.2}}>{t}</div></Reveal>)}</div><div style={{fontSize:portrait?30:34,color:note,marginTop:38,...enter(f,cue('without'))}}>Without repeating private details.</div></>;
 else body=<div style={{textAlign:'center',margin:'auto'}}><Img src={staticFile('brand-logo-dark.svg')} style={{width:portrait?300:352,marginBottom:22,...enter(f)}}/><div style={{fontSize:26,letterSpacing:9,color:'#9FC2FF',fontWeight:650,...enter(f,6)}}>{moduleName().toUpperCase()}</div><div style={{height:3,width:p(f,12,20)*(portrait?300:430),background:'#5A90FF',borderRadius:2,margin:'46px auto'}}/><Words text="Better conversations." f={f} size={portrait?82:122} color="white"/><div style={{marginTop:14}}><Words text="Less exposure." f={f} start={cue('Less')} size={portrait?82:122} color="#8FB6FA"/></div><div style={{marginTop:58,display:'inline-flex',alignItems:'center',gap:18,padding:'18px 36px',borderRadius:999,border:'2px solid #5A90FF',...enter(f,cue('PII'))}}><LockSeal f={f} t={cue('PII')} size={42} color="white"/><span style={{fontSize:34,color:'white',letterSpacing:.5}}>PII Masking</span></div></div>;
 return <AbsoluteFill style={{background:field,color:ink,padding:portrait?'190px 80px 200px':'145px 140px 165px',display:'flex',flexDirection:'column',justifyContent:'center',opacity:fadeIn}}>{k!=='cta'&&<Img src={staticFile(lockupFile(darkField?'dark':'light'))} style={{position:'absolute',width:155,top:48,left:portrait?80:140}}/>}{k!=='cta'&&<div style={{position:'absolute',top:55,right:portrait?80:140,fontSize:18,letterSpacing:2,color:headerInk(darkField?'dark':'light')}}>PII MASKING</div>}{body}</AbsoluteFill>
}
const ShotView:React.FC<{s:Shot;portrait:boolean;scenes:Shot[]}>=({s,portrait,scenes})=>{const f=useCurrentFrame();return <AbsoluteFill>{s.treatment.startsWith('call-')?s.callStyle==='reference-phone'?<ReferenceCall s={s} f={f} portrait={portrait} scenes={scenes}/>:<Call s={s} f={f} portrait={portrait}/>:<Content s={s} f={f} portrait={portrait}/>}</AbsoluteFill>};
function PersistentCall({shots,portrait,all}:{shots:Shot[];portrait:boolean;all:Shot[]}) {
 const frame=useCurrentFrame();
 const origin=shots[0].from;
 const span=shots[shots.length-1].from+shots[shots.length-1].frames-origin;
 const global=frame+origin;
 const active=shots.find(s=>global>=s.from&&global<s.from+s.frames)??shots[shots.length-1];
 const fadeOut=interpolate(frame,[span,span+CROSS_FRAMES],[1,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
 return <AbsoluteFill style={{opacity:fadeOut}}><ReferenceCall s={active} f={global-active.from} portrait={portrait} scenes={all}/></AbsoluteFill>;
}
export const PiiCallFirst:React.FC<FilmProps>=({scenes,audio,audioFrom=3,portrait,craft,title,durationInFrames,preview})=>{
 const shots=scenes as Shot[];
 const call=shots.filter(s=>s.treatment.startsWith('call-'));
 const callFrom=call[0]?.from??0;
 const callDur=call.length?call[call.length-1].from+call[call.length-1].frames-callFrom:0;
 return <FilmRoot scenes={scenes} audio={audio} audioFrom={audioFrom} portrait={portrait} craft={craft} title={title||'PII Masking'} durationInFrames={durationInFrames} preview={preview} chrome={false}>
  <style>{`@font-face{font-family:KohinoorFilm;src:url(${staticFile('Kohinoor.ttf')}) format('truetype');font-weight:100 900;font-display:block;}`}</style>
  {call.length>0&&<Sequence from={callFrom} durationInFrames={callDur+CROSS_FRAMES}><PersistentCall shots={call} portrait={portrait} all={shots}/></Sequence>}
  {shots.map((s,i)=>s.treatment.startsWith('call-')?null:<SceneLayer key={i} index={i} scene={s} total={scenes.length}><ShotView s={s} portrait={portrait} scenes={shots}/></SceneLayer>)}
 </FilmRoot>;
};
