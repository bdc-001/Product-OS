import { ExamplePanels, type DemonstrationExample } from "./ExamplePanels";
import { productName } from "./brand";
import { BrandArrow, Motif, SignalTrail, WriteOnPath } from "./Motifs";
import { C, Elevated, FilmRoot, SceneLayer, buildSpan, overlapStagger, progress, useSceneCraft } from "./World";
import { IPhone, IPHONE_OUTER } from "./kit";
import React, { useLayoutEffect, useRef } from "react";
import { AbsoluteFill, Audio, Img, Sequence, staticFile, useCurrentFrame } from "remotion";
import type { SceneCraft } from "./World";

export type Scene = {
  examples?: DemonstrationExample[]; exampleFrames?: number[]; language?: "en" | "hi"; languageFrom?: string | null;
  kind: string; headline: string; body: string; narration: string;
  visual?: "statement" | "contrast" | "steps" | "spotlight" | "conversation" | "stack" | "orchestration" | "call" | "detect" | "collect" | "spread" | "flow" | "mask" | "split";
  labels?: string[]; emphasis?: string; visual_reason?: string; voice?: "narrator" | "example" | "agent" | "customer";
  from: number; frames: number; audio?: string; audioFrom?: number; labelFrames?: number[];
  captions: { text: string; from: number; to: number }[];
  wordTimings?: { word: string; start: number; end: number }[];
};
export type FilmProps = { title: string; scenes: Scene[]; durationInFrames: number; portrait: boolean; preview?: boolean; audio?: string; audioFrom?: number; filmKind?: string; craft?: SceneCraft[]; product?: string; module?: string };
const display = "'Helvetica Neue', Helvetica, Arial, sans-serif";
const enter = (p: number): React.CSSProperties => ({ opacity: p, transform: `translateY(${(1 - p) * 36}px) scale(${0.96 + p * 0.04})`, filter: `blur(${(1 - p) * 5}px)` });
const breathe = (frame: number, amount = 0.01) => 1 + Math.sin(frame / 42) * amount;

function Highlight({ text, emphasis, dark, frame, span }: { text: string; emphasis?: string; dark: boolean; frame: number; span: number }) {
  const words = text.split(" ");
  const emphasisStart = emphasis ? text.indexOf(emphasis) : -1;
  let offset = 0;
  return <>{words.map((word, i) => {
    const highlighted = emphasisStart >= 0 && offset >= emphasisStart && offset < emphasisStart + (emphasis?.length || 0);
    offset += word.length + 1;
    const start = 0, duration = 16;
    const p = progress(frame, start, duration);
    return <React.Fragment key={i}><span style={{ display: "inline-block", overflow: "hidden", verticalAlign: "bottom", paddingBottom: 5 }}><span style={{ display: "inline-block", position: "relative", color: highlighted ? (dark ? C.line : C.blue) : undefined, transform: `translateY(${(1 - p) * 110}%) rotate(${(1 - p) * 5}deg)`, opacity: 1 }}>
      {word}{highlighted && <span style={{ position: "absolute", height: 3, bottom: 0, left: 0, right: 0, background: dark ? C.line : C.blue, transformOrigin: "left", transform: `scaleX(${progress(frame, start + duration * 0.4, duration)})`, opacity: 0.6, boxShadow: `0 0 12px ${C.blue}` }} />}
    </span></span>{i < words.length - 1 ? " " : ""}</React.Fragment>;
  })}</>;
}
const focus = (frame: number, start: number, next?: number) => progress(frame, start, 10) * (1 - (next === undefined ? 0 : progress(frame, next, 10)));
const Arrow = ({ vertical = false, opacity = 1, dark = false }: { vertical?: boolean; opacity?: number; dark?: boolean }) => <BrandArrow direction={vertical ? "down" : "right"} opacity={opacity} dark={dark} length={vertical ? 40 : 56} />;

function PhoneCall({ scene, frame, portrait }: { scene: Scene; frame: number; portrait: boolean }) {
  const labels = scene.labels?.length ? scene.labels : [scene.body];
  const span = buildSpan(scene);
  const reveal = (i: number) => {
    const timed = scene.labelFrames?.[i];
    if (timed !== undefined) return progress(frame, timed, Math.max(1, Math.min(14, scene.frames - timed - 6)));
    const { start, duration } = overlapStagger(i, labels.length, span);
    return progress(frame, start, duration);
  };
  const connected = progress(frame, 10, 8);
  const seconds = Math.floor(frame / 30);
  const timer = `00:${String(seconds).padStart(2, "0")}`;
  const width = portrait ? 300 : 304;
  const scale = width / IPHONE_OUTER.width;
  return <div style={{ flexShrink: 0, filter: "drop-shadow(0 28px 50px rgba(10,46,122,0.35))" }}>
    <IPhone scale={scale} ringing={connected < 0.5} appearance={connected > 0.5 ? "dark" : "light"}>
      <div style={{ width: 1179, height: 2556, padding: "220px 90px 160px", display: "flex", flexDirection: "column", alignItems: "center", background: connected > 0.5 ? "linear-gradient(180deg,#2C2C2E,#000)" : "linear-gradient(180deg,#F7FAFF,#E4EEFF)", color: connected > 0.5 ? C.inverse : C.ink }}>
        <div style={{ color: connected > 0.5 ? C.line : C.blue, fontSize: 54, letterSpacing: 1.4 }}>ILLUSTRATIVE CALL</div>
        <div style={{ fontSize: 72, marginTop: 20, fontWeight: 500 }}>{connected > 0.5 ? timer : "Connecting"}</div>
        <div style={{ width: 240, height: 240, borderRadius: "50%", background: `linear-gradient(145deg, ${C.pale}, ${C.line})`, color: C.navy, display: "grid", placeItems: "center", fontFamily: display, fontWeight: 700, fontSize: 86, marginTop: 60 }}>AI</div>
        <div style={{ fontFamily: display, fontWeight: 700, fontSize: 84, marginTop: 32 }}>{scene.voice === "agent" ? "Agent" : scene.voice === "customer" ? "Customer" : "Call scenario"}</div>
        {scene.language && <div style={{ color: connected > 0.5 ? C.line : C.navy, fontSize: 36, marginTop: 14 }}>{scene.languageFrom ? `${scene.languageFrom === "en" ? "English" : "हिन्दी"} → ` : ""}{scene.language === "hi" ? "हिन्दी" : "English"}</div>}
        <div style={{ width: "100%", flex: 1, display: "flex", flexDirection: "column", gap: 50, justifyContent: "center", paddingBottom: 70 }}>
          <div data-film-text="call-context" style={{fontSize:90,lineHeight:1.35,color:C.inverse,padding:"50px 42px",borderRadius:38,background:"#1A62F240",border:"3px solid #4A84F5"}}>{scene.body}</div>
          {labels.map((label, i) => <div data-film-text="label" key={i} style={{ alignSelf: i % 2 ? "flex-end" : "flex-start", maxWidth: "100%", padding: "28px 32px", borderRadius: 24, borderBottomLeftRadius: 6, background: `linear-gradient(165deg, ${C.pale}, #D7E6FF)`, color: C.ink, fontSize: 80, lineHeight: 1.3, opacity: reveal(i), transform: `translateY(${(1 - reveal(i)) * 16}px)` }}>{label}</div>)}
        </div>
      </div>
    </IPhone>
  </div>;
}

function Diagram({ scene, frame, portrait, dark }: { scene: Scene; frame: number; portrait: boolean; dark: boolean }) {
  const labels = scene.labels?.length ? scene.labels : [scene.body];
  const visual = scene.visual || "spotlight";
  const span = buildSpan(scene);
  const reveal = (i: number) => {
    const timed = scene.labelFrames?.[i];
    // Establish the relationship early; emphasize each label on its spoken cue.
    if (timed !== undefined) return 1;
    const { start, duration } = overlapStagger(i, labels.length, span);
    return progress(frame, start, duration);
  };
  const active = (i: number) => focus(frame, scene.labelFrames?.[i] ?? overlapStagger(i, labels.length, span).start, scene.labelFrames?.[i + 1]);
  const text = dark ? C.inverse : C.ink;
  const border = dark ? "#4A84F5" : C.line;
  const panel: React.CSSProperties = { borderRadius: 20, border: `1.5px solid ${border}`, color: text };
  const live = (i: number) => `translateY(${Math.sin((frame + i * 18) / 36) * 4}px) scale(${breathe(frame + i * 7, 0.006)})`;
  if (visual === "conversation") return <div style={{ width: "100%" }}>
    <div style={{ color: dark ? C.line : C.blue, fontSize: 24, marginBottom: 32, letterSpacing: 1 }}>ILLUSTRATIVE SCENARIO</div>
    {labels.map((label, i) => <div key={i} style={{ display: "flex", justifyContent: i % 2 ? "flex-end" : "flex-start", marginBottom: 24, opacity: reveal(i), transform: `translateX(${(1 - reveal(i)) * (i % 2 ? 130 : -130)}px) scale(${0.94 + reveal(i) * 0.06}) ${live(i)}` }}><Elevated z={1 + active(i)} dark={i % 2 === 1} radius={20} style={{ width: "88%", padding: "26px 32px", color: i % 2 ? C.inverse : C.ink }}><div data-film-text="label" style={{ fontSize: portrait ? 39 : 36, lineHeight: 1.35 }}>{label}</div></Elevated></div>)}
  </div>;
  if (visual === "stack") return <div style={{ width: "100%", height: portrait ? 510 : 510, position: "relative" }}>
    {labels.map((label, i) => <Elevated key={i} z={i + 1} dark={dark} style={{ ...panel, position: "absolute", left: i * (portrait ? 36 : 42), top: i * 158, width: "82%", minHeight: 180, padding: "26px 28px", transform: `translateX(${(1 - reveal(i)) * 180}px) ${live(i)} rotate(${(i - 1) * 2 + (1 - reveal(i)) * 8}deg)`, opacity: reveal(i), borderColor: active(i) > 0.5 ? C.line : border }}>
      <div style={{ position: "absolute", top: 22, left: 20 }}><Motif visual="stack" dark={dark} size={28} /></div><div data-film-text="label" style={{ fontFamily: display, fontSize: portrait ? 36 : 34, fontWeight: 700, lineHeight: 1.2, paddingLeft: 48 }}>{label}</div>
    </Elevated>)}
  </div>;
  if (visual === "orchestration") return <div style={{ width: "100%", height: portrait ? 600 : 510, position: "relative" }}>
    <svg viewBox="0 0 760 540" style={{ position: "absolute", inset: 0, width: "100%", height: "100%", overflow: "visible" }}>
      {labels.map((_, i) => {
        const y = 90 + i * (360 / Math.max(1, labels.length - 1));
        const d = `M320 270 C380 270 380 ${y} 450 ${y}`;
        return <g key={i} opacity={reveal(i)}><WriteOnPath d={d} progress={reveal(i)} color={dark ? C.line : C.blue} /><circle cx={450} cy={y} r={5 + active(i) * 3} fill={dark ? C.line : C.blue} /></g>;
      })}
      <circle cx="180" cy="270" r="121" stroke={dark ? "#4A84F5" : C.line} fill="none" strokeWidth="1" />
      <circle cx="180" cy="270" r="101" stroke={dark ? C.line : C.blue} fill="none" strokeWidth="1.5" strokeDasharray="2 13" transform={`rotate(${frame * 0.65} 180 270)`} />
    </svg>
    {labels.map((_, i) => {
      const y = 90 + i * (360 / Math.max(1, labels.length - 1));
      return reveal(i) > 0.15 ? <SignalTrail key={`signal-${i}`} d={`M320 270 C380 270 380 ${y} 450 ${y}`} start={scene.labelFrames?.[i] ?? overlapStagger(i, labels.length, span).start} viewW={760} viewH={540} color={C.blue} /> : null;
    })}
    <div style={{ position: "absolute", left: "10%", top: "35%", width: "27%", height: "30%", display: "flex", alignItems: "center", justifyContent: "center", ...enter(progress(frame, 12)), borderRadius: "50%", background: `radial-gradient(circle, ${dark ? C.inverse : C.pale} 0%, ${C.line} 100%)`, boxShadow: `0 0 ${40 + Math.sin(frame / 24) * 20}px #1A62F280`, transform: `scale(${breathe(frame, 0.02)})` }}><Img src={staticFile("brand-mark.svg")} style={{ width: "64%" }} /></div>
    {labels.map((label, i) => <Elevated data-film-text="label" key={i} z={1} dark={dark} style={{ ...panel, ...enter(reveal(i)), position: "absolute", left: "60%", width: "40%", top: `${5 + i * (66 / Math.max(1, labels.length - 1))}%`, minHeight: 100, padding: "24px 20px", fontFamily: display, fontWeight: 700, fontSize: portrait ? 33 : 31, lineHeight: 1.22, transform: live(i) }}>{label}</Elevated>)}
  </div>;
  if (visual === "steps" || visual === "flow") return <div style={{ width: "100%", display: "flex", flexDirection: "column", alignItems: "flex-start" }}>
    {labels.map((label, i) => <React.Fragment key={i}>{i > 0 && <div style={{ marginLeft: 24 }}><Arrow vertical opacity={reveal(i)} dark={dark} /></div>}<div style={{ display: "flex", alignItems: "center", gap: 30, ...enter(reveal(i)), transform: live(i) }}><div style={{ flexShrink: 0, width: 84, height: 84, border: `1.5px solid ${border}`, borderRadius: "50%", display: "grid", placeItems: "center", fontSize: 26, background: active(i) > 0.5 ? `linear-gradient(145deg, ${C.blue}, ${C.navy})` : "transparent", color: active(i) > 0.5 ? C.inverse : dark ? C.line : C.blue, transform: `scale(${1 + active(i) * 0.06})`, boxShadow: active(i) > 0.5 ? `0 0 24px ${C.blue}` : undefined }}>{String(i + 1).padStart(2, "0")}</div><div data-film-text="label" style={{ color: text, fontFamily: display, fontSize: portrait ? 46 : 44, fontWeight: 700, lineHeight: 1.2 }}>{label}</div></div></React.Fragment>)}
  </div>;
  if (visual === "spotlight" && labels.length === 2) return <div style={{width:"100%",height:450,position:"relative",display:"flex",alignItems:"flex-end",gap:24}}>
    <svg viewBox="0 0 760 450" style={{position:"absolute",inset:0,width:"100%",height:"100%"}} fill="none" stroke={dark ? C.line : C.blue} strokeWidth="3">
      <rect x="325" y="15" width="110" height="130" rx="14"/><path d="M350 53h60M350 78h60M350 103h38M380 145v70M190 270v-55h380v55"/>
    </svg>
    {labels.map((label,i)=><div key={i} data-film-text="label" style={{width:"50%",minHeight:145,padding:"34px 24px",borderRadius:20,border:`2px solid ${i ? border : "#5FE6EB"}`,background:i ? (dark ? "#102342" : "#EEF4FF") : "#1658E1",color:i ? text : C.inverse,fontFamily:display,fontSize:42,fontWeight:700,textAlign:"center",transform:live(i)}}>{label}</div>)}
  </div>;
  if (visual === "contrast") return <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24, width: "100%" }}>
    {labels.map((label, i) => <Elevated data-film-text="label" key={i} z={i + 1} dark={false} style={{ transform: live(i), padding: "44px 28px", background:i ? "#EEF4FF" : "#1658E1",color:i ? C.navy : C.inverse,fontSize:portrait ? 39 : 38,lineHeight:1.25,fontFamily:display,fontWeight:700,minHeight:340,display:"flex",flexDirection:"column",justifyContent:"center",gap:40 }}><svg viewBox="0 0 80 80" width="82" height="82" fill="none" stroke="currentColor" strokeWidth="2.5"><circle cx="40" cy="40" r="33"/>{i ? <path d="m32 23 24 17-24 17Z"/> : <path d="M40 20v23l16 10"/>}</svg>{label}</Elevated>)}
  </div>;
  return <Elevated z={2} dark={dark} style={{ width: "100%", padding: portrait ? 48 : 52, position: "relative", transform: `scale(${(1.06 - progress(frame, 0, span) * 0.06) * breathe(frame)})`, borderTop: `5px solid ${C.blue}` }}>
    <div style={{ position: "absolute", top: 20, right: 20 }}><Motif visual={visual} dark={dark} size={52} /></div>
    {labels.map((label, i) => <div data-film-text="label" key={i} style={{ ...enter(reveal(i)), fontFamily: display, fontSize: portrait ? 49 : 46, lineHeight: 1.25, fontWeight: 700, padding: i ? "24px 0 0" : 0, paddingRight: 64, marginTop: i ? 24 : 0, borderTop: i ? `1px solid ${border}` : undefined }}>{label}</div>)}
  </Elevated>;
}

function Shot({ scene, index, portrait, title, preview }: { scene: Scene; index: number; portrait: boolean; title: string; preview?: boolean }) {
  const frame = useCurrentFrame();
  const craft = useSceneCraft();
  const root = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    if (!root.current || frame < Math.min(scene.frames - 2, Math.max(35, ...(scene.labelFrames || [0])) + 25)) return;
    const bounds = root.current.getBoundingClientRect();
    if (bounds.width < 8 || bounds.height < 8 || bounds.top < -100) return;
    const boxes = Array.from(root.current.querySelectorAll<HTMLElement>("[data-film-text]")).map(el => ({ el, rect: el.getBoundingClientRect(), text: el.textContent?.slice(0, 70) }));
    for (const box of boxes) {
      const r = box.rect;
      if (r.left < bounds.left - 1 || r.right > bounds.right + 1 || r.top < bounds.top - 1 || r.bottom > bounds.bottom + 1) {
        throw new Error(`Shot ${index + 1} text exceeds the frame: ${box.text}`);
      }
    }
    for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
      if (boxes[i].el.dataset.filmText === "example-value" && boxes[j].el.dataset.filmText === "example-value" && boxes[i].el.parentElement === boxes[j].el.parentElement) continue;
      const a = boxes[i].rect, b = boxes[j].rect;
      if (Math.min(a.right, b.right) - Math.max(a.left, b.left) > 2 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 2) {
        throw new Error(`Shot ${index + 1} has overlapping text: ${boxes[i].text} / ${boxes[j].text}`);
      }
    }
  }, [frame, scene, index]);
  const examples = !!scene.examples?.length;
  const hero = scene.visual === "statement" || !scene.visual;
  const call = scene.visual === "call";
  const dark = craft.luma === "dark";
  const text = dark ? C.inverse : C.ink;
  const span = buildSpan(scene);
  const p = progress(frame, 0, Math.max(12, span * 0.22));
  const caption = scene.captions.find(c => frame >= c.from && frame < c.to);
  const treatment = craft.treatment;
  const centre = treatment.startsWith("centre") || treatment === "emphasis-dark" || (call && portrait) || hero && treatment !== "left-light";
  const left = treatment === "left-light";
  const headlineSize = examples ? (portrait ? 78 : 76) : call ? (portrait ? 70 : 96) : portrait ? (hero ? 101 : 84) : hero ? 116 : 83;
  const headline = <div data-film-text="headline" style={{ fontFamily: display, fontSize: headlineSize, lineHeight: 1.16, letterSpacing: -2, fontWeight: 700, color: text, overflowWrap: "break-word" }}><Highlight text={scene.headline} emphasis={scene.emphasis} dark={dark} frame={frame} span={span} /></div>;
  return <AbsoluteFill ref={root} style={{ background: "transparent", color: text, overflow: "hidden" }}>
    {scene.audio && <Sequence from={scene.audioFrom ?? 9}><Audio src={staticFile(scene.audio)} /></Sequence>}
    <div data-film-region="content" style={{ position: "absolute", top: portrait ? 300 : call ? 168 : 228, left: portrait ? 88 : 100, right: portrait ? 130 : 100, bottom: portrait ? 410 : call ? 180 : 210, display: "flex", flexDirection: portrait || hero || examples ? "column" : "row", gap: examples ? 28 : portrait ? 36 : call ? 120 : 90, alignItems: call || (centre && !left) ? "center" : "stretch", justifyContent: "center" }}>
      <div style={{ width: hero || examples ? "100%" : portrait ? "100%" : "49%", flexShrink: 0, display: "flex", flexDirection: "column", justifyContent: "center", textAlign: left ? "left" : centre ? "center" : "left", opacity: p, transform: `translateX(${(1 - p) * (index % 2 ? 60 : -60)}px) translateY(${Math.sin(frame / 48) * 3}px) scale(${hero ? 1.025 - progress(frame, 0, span) * 0.025 : 1})` }}>
        {hero && scene.kind === "cta" && <div style={{ fontSize: 25, letterSpacing: 2, color: C.line, marginBottom: 36 }}>{title.length > 50 ? productName().toUpperCase() : title}</div>}
        {headline}
        {!call && <div data-film-text="body" style={{ fontSize: examples ? (portrait ? 29 : 28) : portrait ? 37 : 34, lineHeight: 1.5, marginTop: examples ? 18 : 32, color: dark ? C.line : "#2C4A7A", maxWidth: hero || examples ? 1600 : 750, alignSelf: left ? "flex-start" : centre ? "center" : "flex-start", opacity: progress(frame, 8, 14), transform: `translateY(${(1 - progress(frame, 8, 14)) * 24}px)` }}>{scene.body}</div>}
        {hero && !call && <div style={{ width: 96, height: 4, background: `linear-gradient(90deg, ${C.blue}, ${C.line})`, marginTop: 45, alignSelf: left ? "flex-start" : "center", transform: `scaleX(${progress(frame, Math.max(12, span * 0.2), Math.max(12, span * 0.25))})`, boxShadow: `0 0 ${12 + Math.sin(frame / 20) * 6}px ${C.blue}`, transformOrigin: left ? "left" : "center" }} />}
      </div>
      {call && <PhoneCall scene={scene} frame={frame} portrait={portrait} />}
      {examples && <ExamplePanels examples={scene.examples!} frames={scene.exampleFrames} frame={frame} portrait={portrait} compact />}
      {!hero && !call && !examples && <div data-film-region="diagram" style={{ flex: portrait ? undefined : 1, minWidth: 0, display: "flex", alignItems: "center", justifyContent: "center" }}><Diagram scene={scene} frame={frame} portrait={portrait} dark={dark} /></div>}
    </div>
    {caption && <div data-film-text="caption" style={{ position: "absolute", bottom: portrait ? 270 : 100, left: portrait ? 88 : 180, right: portrait ? 130 : 180, textAlign: "center", fontSize: 42, lineHeight: 1.48, transform: `translateY(${(1 - progress(frame, caption.from, 4)) * 8 + Math.sin(frame / 40) * 2}px)`, color: dark ? C.inverse : C.ink }}><span style={{ background: dark ? "linear-gradient(180deg, #1A2A58E8, #151515E8)" : "linear-gradient(180deg, #F7FAFFE8, #EEF4FFE8)", padding: "10px 20px", borderRadius: 12, boxDecorationBreak: "clone", WebkitBoxDecorationBreak: "clone", boxShadow: "0 12px 30px rgba(10,46,122,0.16)" }}>{caption.text}</span></div>}
  </AbsoluteFill>;
}

export const MarketingFilm: React.FC<FilmProps> = ({ scenes, portrait, title, preview, audio, audioFrom = 3, craft, durationInFrames }) => (
  <FilmRoot scenes={scenes} portrait={portrait} title={title} preview={preview} audio={audio} audioFrom={audioFrom} craft={craft} durationInFrames={durationInFrames}>
    {scenes.map((scene, i) => <SceneLayer key={i} index={i} scene={scene} total={scenes.length}><Shot scene={scene} index={i} portrait={portrait} title={title} preview={preview} /></SceneLayer>)}
  </FilmRoot>
);
