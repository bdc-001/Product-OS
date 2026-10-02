import {evolvePath} from '@remotion/paths';
import React from 'react';
import {Easing, interpolate} from 'remotion';
export type DemonstrationExample={label:string;before_label?:string;after_label?:string;before:string;after:string;context:string;cue?:string};
const progress=(f:number,t:number,d=12)=>interpolate(f,[t,t+d],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp',easing:Easing.bezier(.16,1,.3,1)});
/** Reusable, data-driven demonstrations. Landscape compares; portrait preserves reading order. */
export function ExamplePanels({examples,frames,frame,portrait=false,compact=false}:{examples:DemonstrationExample[];frames?:number[];frame:number;portrait?:boolean;compact?:boolean}) {
 return <div style={{display:'grid',gridTemplateColumns:portrait?'1fr':`repeat(${examples.length},minmax(0,1fr))`,gap:portrait?24:32,width:'100%'}}>
 {examples.map((ex,i)=>{
  // The panel is wiped open, then a scanner crosses the value and the swap happens under the band.
  const start=frames?.[i]??30;const reveal=progress(frame,i*6,13);const scan=progress(frame,start,18);const transformed=scan>=.5;const pop=progress(frame,start+9,11);
  return <div key={`${i}-${ex.label}`} style={{border:'2px solid #D7E5FF',borderRadius:25,background:'linear-gradient(165deg,#F7FAFF 0%,#EEF4FF 52%,#D7E5FF 100%)',padding:compact?28:40,boxShadow:'0 18px 48px #0A2E7A22, 0 0 24px #1A62F214',minWidth:0,transform:`translateY(${(1-reveal)*8}px)`,clipPath:reveal>=1?undefined:`inset(${(1-reveal)*100}% 0 0 0 round 25px)`}}>
   <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:18,marginBottom:compact?24:35}}><div data-film-text="example-label" style={{fontSize:compact?24:29,fontWeight:600,color:'#0A2E7A'}}>{ex.label}</div><div style={{fontSize:16,letterSpacing:1.5,color:'#8290A6'}}>ILLUSTRATIVE</div></div>
   <div style={{position:'relative',height:26,marginBottom:13,fontSize:20,color:'#718198'}}><span style={{position:'absolute',left:0,opacity:1-pop,transform:`translateY(${-8*pop}px)`}}>{ex.before_label||'Before'}</span><span style={{position:'absolute',left:0,opacity:pop,transform:`translateY(${8*(1-pop)}px)`}}>{ex.after_label||'After'}</span></div>
   <div style={{position:'relative',background:transformed?'#EEF4FF':'#F6F8FC',borderRadius:12,padding:compact?'19px 20px':'24px 24px',overflow:'hidden',minHeight:compact?86:110,display:'flex',alignItems:'center',boxShadow:transformed?'inset 0 0 0 2px #1A62F2':'none'}}>
    <div data-film-text="example-value" style={{fontSize:compact?31:40,fontWeight:550,letterSpacing:-.7,color:'#283C5E',overflowWrap:'anywhere',opacity:1-scan,filter:`blur(${scan*1.4}px)`}}>{ex.before}</div>
    <div data-film-text="example-value" style={{position:'absolute',left:compact?20:24,right:compact?20:24,fontSize:compact?31:40,fontWeight:600,letterSpacing:-.7,color:'#1A62F2',overflowWrap:'anywhere',clipPath:`inset(0 ${Math.max(0,100-scan*100)}% 0 0)`}}>{ex.after}</div>
    {scan>0&&scan<1&&<div style={{position:'absolute',top:0,bottom:0,width:8,left:`${scan*100}%`,background:'#1A62F2',boxShadow:'0 0 18px #1A62F2'}}/>}
    {pop>0&&(()=>{const check='M6.5 12.4l3.6 3.6L17.5 8.6';const drawn=evolvePath(progress(frame,start+12,9),check);return <svg width="26" height="26" viewBox="0 0 24 24" style={{position:'absolute',right:14,top:14}}><circle cx="12" cy="12" r="11" fill="#1A62F2" opacity={pop}/><path d={check} fill="none" stroke="white" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" strokeDasharray={drawn.strokeDasharray} strokeDashoffset={drawn.strokeDashoffset}/></svg>;})()}
   </div>
   <div style={{borderTop:'1px solid #E6EDFA',marginTop:compact?22:32,paddingTop:compact?18:26}}><div style={{fontSize:18,color:'#738298',marginBottom:9}}>Context</div><div data-film-text="example-context" style={{fontSize:compact?24:29,lineHeight:1.4,color:'#151515'}}>{ex.context}</div></div>
  </div>
 })}
 </div>
}
