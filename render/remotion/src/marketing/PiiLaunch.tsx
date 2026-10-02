import React, { useLayoutEffect, useRef } from "react";
import { moduleName } from "./brand";
import { AbsoluteFill, Audio, Easing, Img, interpolate, Sequence, staticFile, useCurrentFrame } from "remotion";
import { FilmRoot, SceneLayer, useSceneCraft } from "./World";
import type { FilmProps, Scene } from "./Film";
import { BrandArrow, LockMark, Motif } from "./Motifs";

const C = { blue: "#1A62F2", navy: "#0A2E7A", dark: "#151515", ink: "#050505", pale: "#EEF4FF", line: "#AFCAFB", inverse: "#F1F1F1" };
const display = "'Helvetica Neue', Helvetica, Arial, sans-serif";
const ease = Easing.bezier(0.16, 1, 0.3, 1);
const progress = (frame: number, start = 0, duration = 14) => interpolate(frame, [start, start + duration], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
const clamp = (frame: number, from: number, to: number, a: number, b: number) => interpolate(frame, [from, to], [a, b], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

const LINES = [
  { beat: 0, who: "agent" as const, text: "Hi, good morning. Am I speaking with Rahul Sharma?" },
  { beat: 1, who: "customer" as const, text: "Yes, this is Rahul Sharma." },
  { beat: 2, who: "agent" as const, text: "Before I proceed, could you confirm your registered mobile number?" },
  { beat: 3, who: "customer" as const, text: "My registered number is 9876543242." },
  { beat: 4, who: "agent" as const, text: "And the last four digits of your PAN, then your date of birth?" },
  { beat: 5, who: "customer" as const, text: "Last four are 4721, born 12 March 1995." },
];

function beatOf(scene: Scene) {
  const v = scene.visual, voice = scene.voice;
  if (v === "call" && voice === "agent") return 0;
  if (v === "call") return 1;
  if (v === "detect" && voice === "agent") return 2;
  if (v === "detect") return 3;
  if (v === "collect" && voice === "agent") return 4;
  if (v === "collect") return 5;
  return -1;
}

function Wave({ frame, live, mutedFrom, tall }: { frame: number; live: boolean; mutedFrom?: number; tall?: boolean }) {
  const height = tall ? 72 : 44;
  return <div style={{ display: "flex", alignItems: "flex-end", gap: 4, height }}>
    {Array.from({ length: tall ? 28 : 22 }, (_, i) => {
      const inMute = mutedFrom !== undefined && i >= mutedFrom && i <= mutedFrom + 5;
      const h = !live || inMute ? (tall ? 10 : 7) : (tall ? 14 : 8) + Math.abs(Math.sin(frame * 0.38 + i * 0.55)) * (tall ? 52 : 32);
      return <div key={i} style={{ width: tall ? 6 : 5, height: h, borderRadius: 3, background: inMute ? "#6A6A6A" : C.line }} />;
    })}
  </div>;
}

function Lock({ size = 22, on = true }: { size?: number; on?: boolean }) {
  return <LockMark size={size} on={on} dark />;
}

function HighlightName({ text, frame, on }: { text: string; frame: number; on: boolean }) {
  const lit = on && frame >= 6 && frame < 21;
  if (!text.includes("Rahul Sharma")) return <>{text}</>;
  const [before, after] = text.split("Rahul Sharma");
  return <>{before}<span style={{ background: lit ? "#1A62F244" : "transparent", boxShadow: lit ? `0 0 0 4px #1A62F244` : "none", borderRadius: 6, color: lit ? C.navy : undefined, transition: "none" }}>Rahul Sharma</span>{after}</>;
}

function CallDesk({ scene, frame, portrait, frozen }: { scene: Scene; frame: number; portrait: boolean; frozen?: boolean }) {
  const beat = Math.max(0, beatOf(scene));
  const labels = scene.labels || [];
  const reveal = (i: number) => progress(frame, scene.labelFrames?.[i] ?? 10 + i * 16);
  const live = !frozen && scene.visual !== "spread";
  const box = beat === 3 ? clamp(frame, 10, 28, 0, 1) * (1 - clamp(frame, 36, 50, 0, 1)) : 0;
  const rows = [
    { label: "Name", value: "Rahul Sharma", from: 1 },
    { label: "Phone", value: "9876543242", from: 3 },
    { label: "PAN", value: "******4721", from: 5 },
    { label: "DOB", value: "12 Mar 1995", from: 5 },
  ].filter(row => beat >= row.from);
  const panIn = beat === 5 ? progress(frame, scene.labelFrames?.[0] ?? 12, 10) : beat > 5 ? 1 : 0;
  const dobIn = beat === 5 ? progress(frame, scene.labelFrames?.[1] ?? 28, 10) : beat > 5 ? 1 : 0;
  const count = beat >= 5 ? 2 + Math.round(panIn) + Math.round(dobIn) : beat >= 3 ? 2 : beat >= 1 ? 1 : 0;
  const history = LINES.filter(line => line.beat < beat).slice(-2);
  const sidebar = beat >= 3 && (scene.visual === "detect" || scene.visual === "collect");
  const card: React.CSSProperties = { flex: 1, minWidth: 0, borderRadius: 24, border: `1.5px solid ${C.navy}`, background: `linear-gradient(165deg, ${C.navy} 0%, ${C.dark} 82%)`, padding: portrait ? 22 : 28, display: "flex", flexDirection: "column", overflow: "hidden", boxShadow: "0 24px 70px #1A62F255" };
  return <div style={{ display: "flex", gap: 22, width: "100%", height: "100%", flexDirection: portrait && sidebar ? "column" : "row" }}>
    <div style={card}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div style={{ color: C.line, fontSize: 13, letterSpacing: 1.4, opacity: 0.8 }}>ILLUSTRATIVE CALL</div>
        <div style={{ color: C.inverse, fontSize: 18, opacity: 0.7 }}>{frozen ? "00:16" : `00:${String(Math.floor(frame / 30) + beat * 3).padStart(2, "0")}`}</div>
      </div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, marginBottom: 14 }}>
        {[{ initials: "A", name: "Agent" }, { initials: "RS", name: "Rahul Sharma" }].map((person, i) => (
          <div key={person.name} style={{ display: "flex", alignItems: "center", gap: 10, flexDirection: i ? "row-reverse" : "row" }}>
            <div style={{ width: portrait ? 48 : 56, height: portrait ? 48 : 56, borderRadius: "50%", background: C.pale, color: C.navy, display: "grid", placeItems: "center", fontFamily: display, fontWeight: 700, fontSize: 18, boxShadow: live && ((i === 0 && beat % 2 === 0) || (i === 1 && beat % 2 === 1)) ? "0 0 0 5px #1A62F266" : "0 0 0 3px #1A62F233" }}>{person.initials}</div>
            <div style={{ color: C.inverse, fontSize: portrait ? 16 : 18, fontWeight: 600 }}>{person.name}</div>
          </div>
        ))}
      </div>
      <div style={{ display: "flex", justifyContent: "center", marginBottom: 12 }}><Wave frame={frame} live={live} /></div>
      <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 8, justifyContent: "flex-end", minHeight: 0 }}>
        {history.map((line, i) => <div key={i} style={{ alignSelf: line.who === "agent" ? "flex-start" : "flex-end", maxWidth: "92%", padding: "8px 12px", borderRadius: 14, background: line.who === "agent" ? "#1A62F233" : C.pale, color: line.who === "agent" ? C.inverse : C.ink, fontSize: portrait ? 16 : 18, lineHeight: 1.3, opacity: 0.5 }}>{line.text}</div>)}
        <div style={{ display: "flex", flexDirection: "column", gap: 6, alignSelf: LINES[beat].who === "agent" ? "flex-start" : "flex-end", maxWidth: "92%", width: "92%" }}>
          {labels.map((label, i) => {
            const last = i === labels.length - 1;
            const phoneTag = beat === 3 && last;
            const text = phoneTag ? "PHONE NUMBER DETECTED" : i === 0 ? LINES[beat].text : label;
            const boxed = beat === 3 && !phoneTag;
            return <div key={i} data-film-text="label" style={{ alignSelf: phoneTag || LINES[beat].who === "customer" ? "flex-end" : "flex-start", padding: phoneTag ? "4px 10px" : "10px 14px", borderRadius: phoneTag ? 8 : 16, background: phoneTag ? C.line : LINES[beat].who === "agent" ? "#1A62F244" : C.pale, color: phoneTag ? C.navy : LINES[beat].who === "agent" ? C.inverse : C.ink, fontSize: phoneTag ? 12 : portrait ? 20 : 22, letterSpacing: phoneTag ? 1.1 : undefined, lineHeight: 1.35, opacity: reveal(i), transform: `translateY(${(1 - reveal(i)) * 14}px)`, boxShadow: boxed && box > 0.2 ? `0 0 0 2px ${C.line}` : undefined, order: phoneTag ? -1 : 0 }}>
              {i === 0 ? <HighlightName text={text} frame={frame} on={beat === 1} /> : text}
            </div>;
          })}
        </div>
      </div>
    </div>
    {sidebar && <div style={{ width: portrait ? "100%" : 300, flexShrink: 0, borderRadius: 20, background: "linear-gradient(165deg, #F7FAFF, #EEF4FF 55%, #D7E6FF)", border: `1.5px solid ${C.line}`, padding: 18, color: C.ink, display: "flex", flexDirection: "column", gap: 10, boxShadow: "0 16px 40px #AFCAFB40" }}>
      <div style={{ fontSize: 13, letterSpacing: 1.2, color: C.blue }}>SENSITIVE DATA DETECTED</div>
      {rows.map((row, i) => {
        const shown = row.label === "PAN" ? panIn : row.label === "DOB" ? dobIn : 1;
        return <div key={row.label} style={{ opacity: shown, transform: `translateX(${(1 - shown) * 24}px)`, padding: "8px 0", borderBottom: "1px solid #EEF4FF", fontSize: portrait ? 20 : 22 }}>
          <span style={{ color: "#6A6A6A", fontSize: 14, display: "block" }}>{row.label}</span>{row.value}
        </div>;
      })}
      <div style={{ marginTop: "auto", fontFamily: display, fontWeight: 700, fontSize: 28, color: C.navy }}>{count} PII detected</div>
    </div>}
  </div>;
}

function Spread({ scene, frame, portrait }: { scene: Scene; frame: number; portrait: boolean }) {
  const count = Math.round(frame < 18 ? clamp(frame, 8, 18, 1, 10) : frame < 32 ? clamp(frame, 18, 32, 10, 100) : clamp(frame, 32, 52, 100, 10000));
  const cards = Math.min(16, 1 + Math.floor(clamp(frame, 10, 48, 0, 15)));
  const reveal = (i: number) => progress(frame, scene.labelFrames?.[i] ?? 10 + i * 16);
  return <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", gap: 10 }}>
    <div data-film-text="label" style={{ fontSize: portrait ? 26 : 28, color: C.line, opacity: reveal(0) }}>{scene.labels?.[0]}</div>
    <div style={{ flex: 1, position: "relative", minHeight: 0 }}>
      <div style={{ position: "absolute", inset: 0, display: "grid", gridTemplateColumns: portrait ? "repeat(3, 1fr)" : "repeat(4, 1fr)", gap: 8 }}>
        {Array.from({ length: cards }, (_, i) => <div key={i} style={{ borderRadius: 12, background: "#0E1C44", border: `1px solid ${C.line}`, padding: 10, fontSize: portrait ? 13 : 14, color: C.inverse, opacity: progress(frame, 8 + i * 2, 8), lineHeight: 1.35 }}>
          <div style={{ opacity: 0.55, fontSize: 10, letterSpacing: 1 }}>CALL {i + 1}</div>
          <div style={{ color: C.line }}>Rahul Sharma</div>
          <div>9876543242</div>
          <div>******4721</div>
        </div>)}
      </div>
      <div style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", fontFamily: display, fontWeight: 700, fontSize: portrait ? 36 : 48, color: C.inverse, textShadow: "0 10px 40px #050505" }}>{count.toLocaleString("en-IN")}</div>
    </div>
    <div data-film-text="label" style={{ fontSize: portrait ? 26 : 28, color: C.inverse, opacity: reveal(1) }}>{scene.labels?.[1]}</div>
  </div>;
}

function Flow({ scene, frame, portrait }: { scene: Scene; frame: number; portrait: boolean }) {
  const steps = ["Customer call", "Audio recording", "Transcript", "UI and reports"];
  const tokens = ["Rahul Sharma", "9876543242", "PAN ABCDE4721F", "DOB 12/03/1995"];
  const reveal = (i: number) => progress(frame, 6 + i * 10, 12);
  return <div style={{ width: "100%", display: "flex", flexDirection: "column", gap: portrait ? 12 : 14 }}>
    {steps.map((step, i) => <React.Fragment key={step}>
      {i > 0 && <div style={{ marginLeft: portrait ? 24 : 40, opacity: reveal(i) }}><BrandArrow direction="down" dark length={28} /></div>}
      <div style={{ display: "flex", alignItems: "center", gap: 16, opacity: reveal(i) }}>
        <div style={{ minWidth: portrait ? 210 : 300, padding: "16px 20px", borderRadius: 14, background: C.navy, color: C.inverse, fontFamily: display, fontWeight: 700, fontSize: portrait ? 22 : 26 }}>{step}</div>
        <div style={{ color: C.inverse, fontSize: portrait ? 20 : 24, padding: "10px 14px", borderRadius: 10, background: "#1A62F233" }}>{tokens[i]}</div>
        <span style={{ color: "#F5C542", fontSize: 22 }}>!</span>
      </div>
    </React.Fragment>)}
    <div data-film-text="label" style={{ marginTop: 8, fontSize: portrait ? 26 : 28, color: C.inverse, opacity: progress(frame, scene.labelFrames?.[0] ?? 18) }}>{scene.labels?.[0]}</div>
    <div data-film-text="label" style={{ fontSize: portrait ? 26 : 28, color: C.line, opacity: progress(frame, scene.labelFrames?.[1] ?? 36) }}>{scene.labels?.[1]}</div>
  </div>;
}

function MaskPlay({ scene, frame, portrait }: { scene: Scene; frame: number; portrait: boolean }) {
  const items = [
    { from: "My PAN number is ABCDE4721F.", to: "My PAN number is **********.", at: 16 },
    { from: "9876543242", to: "********42", at: 36 },
    { from: "12 March 1995", to: "*************", at: 56 },
    { from: "Rahul Sharma", to: "[REDACTED]", at: 76 },
  ];
  const scan = clamp(frame, 4, 18, 0, 100);
  const reveal = (i: number) => progress(frame, scene.labelFrames?.[i] ?? 10 + i * 16);
  return <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", gap: 10, position: "relative" }}>
    <div style={{ display: "flex", alignItems: "center", gap: 10, opacity: reveal(0) }}>
      <div style={{ width: 28, height: 28, flexShrink: 0, overflow: "hidden" }}><Motif visual="mask" dark size={28} /></div>
      <div data-film-text="label" style={{ fontSize: portrait ? 26 : 28, color: C.line }}>{scene.labels?.[0]}</div>
    </div>
    <div style={{ position: "absolute", top: 48, bottom: 40, width: 4, left: `${scan}%`, background: C.line, opacity: frame < 22 ? 0.85 : 0, boxShadow: `0 0 18px ${C.line}`, zIndex: 2 }} />
    {items.map((item, i) => {
      const on = frame >= item.at;
      const lock = progress(frame, item.at + 4, 8);
      return <div key={i} style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 16px", borderRadius: 16, background: "#0E1C44", border: `1px solid ${C.line}`, fontSize: portrait ? 22 : 26, color: C.inverse, fontFamily: display, fontWeight: 600, opacity: progress(frame, item.at - 4, 8) }}>
        <span style={{ flex: 1 }}>{on ? item.to : item.from}</span>
        <span style={{ transform: `scale(${0.6 + lock * 0.4})` }}><Lock on={on} /></span>
      </div>;
    })}
    <div data-film-text="label" style={{ fontSize: portrait ? 26 : 28, color: C.inverse, marginTop: "auto", opacity: reveal(1) }}>{scene.labels?.[1]}</div>
  </div>;
}

function Split({ scene, frame, portrait }: { scene: Scene; frame: number; portrait: boolean }) {
  const masked = frame > Math.max(40, Math.round((scene.frames || 90) * 0.45));
  const reveal = (i: number) => progress(frame, scene.labelFrames?.[i] ?? 10 + i * 18);
  return <div style={{ display: "flex", gap: 20, width: "100%", height: "100%", flexDirection: portrait ? "column" : "row" }}>
    {[{ title: "Transcript", body: masked ? "My account number is ************." : "My account number is 123456789012.", i: 0 }, { title: "Recording", body: masked ? "Your account number is [MUTED], correct?" : "Waveform playing", i: 1 }].map(panel => (
      <div key={panel.title} style={{ flex: 1, borderRadius: 20, background: "#0E1C44", border: `1.5px solid ${C.line}`, padding: 22, display: "flex", flexDirection: "column", gap: 16 }}>
        <div style={{ color: C.line, letterSpacing: 1.3, fontSize: 14 }}>{panel.title}</div>
        <div data-film-text="label" style={{ color: C.inverse, fontSize: portrait ? 28 : 32, fontFamily: display, fontWeight: 700, lineHeight: 1.3, opacity: reveal(panel.i) }}>{scene.labels?.[panel.i]}</div>
        <div style={{ color: C.inverse, fontSize: portrait ? 22 : 24, lineHeight: 1.4 }}>{panel.body}</div>
        {panel.i === 1 && <div style={{ marginTop: "auto", display: "flex", flexDirection: "column", gap: 12 }}><Wave frame={frame} live={!masked} mutedFrom={masked ? 10 : undefined} tall />{masked && <div style={{ display: "flex", alignItems: "center", gap: 8, color: C.line }}><Lock /> Audio PII masked</div>}</div>}
      </div>
    ))}
  </div>;
}

function Chips({ scene, frame, portrait }: { scene: Scene; frame: number; portrait: boolean }) {
  const chips = ["Phone Number", "PAN", "Aadhaar", "Email", "Date of Birth", "Account Number", "Card Information"];
  const steps = ["Detect", "Mask", "Protect"];
  const reveal = (i: number) => progress(frame, scene.labelFrames?.[i] ?? 12 + i * 16);
  return <div style={{ width: "100%" }}>
    <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginBottom: 28 }}>
      {chips.map((chip, i) => <div key={chip} style={{ padding: "10px 16px", borderRadius: 999, border: `1.5px solid ${C.line}`, color: C.inverse, fontSize: portrait ? 20 : 22, opacity: progress(frame, 4 + i * 4, 10) }}>{chip}</div>)}
    </div>
    <div data-film-text="label" style={{ fontSize: portrait ? 28 : 32, color: C.inverse, marginBottom: 18, opacity: reveal(0) }}>{scene.labels?.[0]}</div>
    <div style={{ display: "flex", gap: 18, alignItems: "center", marginBottom: 18 }}>
      {steps.map((step, i) => <React.Fragment key={step}><div style={{ padding: "16px 26px", borderRadius: 14, background: C.blue, color: C.inverse, fontFamily: display, fontWeight: 700, fontSize: portrait ? 26 : 32, opacity: progress(frame, 16 + i * 14, 10) }}>{step}</div>{i < 2 && <span style={{ opacity: progress(frame, 22 + i * 14, 8) }}><BrandArrow direction="right" dark length={36} /></span>}</React.Fragment>)}
    </div>
    <div data-film-text="label" style={{ fontSize: portrait ? 28 : 32, color: C.line, opacity: reveal(1) }}>{scene.labels?.[1]}</div>
  </div>;
}

function Payoff({ scene, frame, portrait }: { scene: Scene; frame: number; portrait: boolean }) {
  const rows = [
    ["Customer intent", "Loan repayment query"],
    ["Sentiment", "Neutral"],
    ["Resolution", "Successful"],
    ["Name", "[REDACTED]"],
    ["Phone", "********42"],
    ["PAN", "**********"],
  ];
  return <div style={{ width: "100%", display: "flex", flexDirection: portrait ? "column" : "row", gap: 28, alignItems: "stretch" }}>
    <div style={{ flex: 1, borderRadius: 20, background: "#0E1C44", border: `1.5px solid ${C.line}`, padding: 22 }}>
      <div style={{ color: C.line, fontSize: 13, letterSpacing: 1.3, marginBottom: 14 }}>ILLUSTRATIVE INSIGHTS</div>
      {rows.map((row, i) => <div key={row[0]} style={{ display: "flex", justifyContent: "space-between", gap: 12, padding: portrait ? "7px 0" : "10px 0", borderBottom: "1px solid #1A62F244", fontSize: portrait ? 20 : 24, color: C.inverse, opacity: progress(frame, 6 + i * 5, 10) }}><span style={{ opacity: 0.65 }}>{row[0]}</span><span>{row[1]}</span></div>)}
    </div>
    <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center", color: C.inverse }}>
      <div style={{ fontSize: 18, letterSpacing: 2, color: C.line, marginBottom: 16 }}>{moduleName().toUpperCase()} PII MASKING</div>
      <div data-film-text="body" style={{ fontSize: portrait ? 28 : 30, lineHeight: 1.45, color: C.line }}>{scene.body}</div>
    </div>
  </div>;
}

function Shot({ scene, index, portrait, title, preview }: { scene: Scene; index: number; portrait: boolean; title: string; preview?: boolean }) {
  const frame = useCurrentFrame();
  const root = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    if (!root.current || frame < Math.min(scene.frames - 2, Math.max(35, ...(scene.labelFrames || [0])) + 25)) return;
    const bounds = root.current.getBoundingClientRect();
    if (bounds.width < 8 || bounds.height < 8 || bounds.top < -100) return;
    const boxes = Array.from(root.current.querySelectorAll<HTMLElement>("[data-film-text]")).map(el => ({ rect: el.getBoundingClientRect(), text: el.textContent?.slice(0, 70) }));
    for (const box of boxes) {
      const r = box.rect;
      if (r.left < bounds.left - 1 || r.right > bounds.right + 1 || r.top < bounds.top - 1 || r.bottom > bounds.bottom + 1) {
        throw new Error(`Shot ${index + 1} text exceeds the frame: ${box.text}`);
      }
    }
    for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
      const a = boxes[i].rect, b = boxes[j].rect;
      if (Math.min(a.right, b.right) - Math.max(a.left, b.left) > 2 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 2) {
        throw new Error(`Shot ${index + 1} has overlapping text: ${boxes[i].text} / ${boxes[j].text}`);
      }
    }
  }, [frame, scene, index]);
  const desk = scene.visual === "call" || scene.visual === "detect" || scene.visual === "collect";
  const dark = useSceneCraft().luma === "dark";
  const text = dark ? C.inverse : C.ink;
  const caption = scene.captions.find(c => frame >= c.from && frame < c.to);
  const p = progress(frame, 0, 12);
  const headlineSize = desk ? (portrait ? 42 : 44) : portrait ? 72 : 78;
  return <AbsoluteFill ref={root} style={{ background: "transparent", color: text, overflow: "hidden" }}>
    {scene.audio && <Sequence from={scene.audioFrom ?? 9}><Audio src={staticFile(scene.audio)} /></Sequence>}
    {dark && <svg viewBox="0 0 1920 1080" preserveAspectRatio="none" style={{ position: "absolute", inset: 0, width: "100%", height: "100%", opacity: 0.15 }}><path d="M0 700C500 700 600 160 1920 160M0 730C500 730 630 190 1920 190" fill="none" stroke={C.line} strokeWidth="1" /></svg>}
    <div data-film-region="content" style={{ position: "absolute", top: portrait ? 168 : 112, left: portrait ? 64 : 72, right: portrait ? 64 : 72, bottom: portrait ? 330 : 168, display: "flex", flexDirection: "column", gap: 14, opacity: p }}>
      <div data-film-text="headline" style={{ fontFamily: display, fontSize: headlineSize, lineHeight: 1.15, letterSpacing: -1.5, fontWeight: 700, color: text, flexShrink: 0 }}>{scene.headline}</div>
      {desk && <div data-film-text="body" style={{ fontSize: portrait ? 22 : 22, color: dark ? C.line : "#2C4A7A", flexShrink: 0 }}>{scene.body}</div>}
      <div style={{ flex: 1, minHeight: 0, display: "flex", alignItems: "stretch" }}>
        {desk && <CallDesk scene={scene} frame={frame} portrait={portrait} />}
        {scene.visual === "spread" && <Spread scene={scene} frame={frame} portrait={portrait} />}
        {scene.visual === "flow" && <Flow scene={scene} frame={frame} portrait={portrait} />}
        {scene.visual === "mask" && <MaskPlay scene={scene} frame={frame} portrait={portrait} />}
        {scene.visual === "split" && <Split scene={scene} frame={frame} portrait={portrait} />}
        {scene.visual === "orchestration" && <Chips scene={scene} frame={frame} portrait={portrait} />}
        {scene.visual === "statement" && <Payoff scene={scene} frame={frame} portrait={portrait} />}
      </div>
    </div>
    {caption && <div data-film-text="caption" style={{ position: "absolute", bottom: portrait ? 220 : 72, left: portrait ? 64 : 160, right: portrait ? 64 : 160, textAlign: "center", fontSize: 40, lineHeight: 1.4, color: dark ? C.inverse : C.ink }}>
      <span style={{ background: dark ? "#151515E8" : "#EEF4FFE8", padding: "10px 20px", borderRadius: 12, boxDecorationBreak: "clone", WebkitBoxDecorationBreak: "clone" }}>{caption.text}</span>
    </div>}
  </AbsoluteFill>;
}

export const PiiLaunch: React.FC<FilmProps> = ({ scenes, portrait, title, preview, audio, audioFrom = 3, craft, durationInFrames }) => (
  <FilmRoot scenes={scenes} portrait={portrait} title={title} preview={preview} audio={audio} audioFrom={audioFrom} craft={craft} durationInFrames={durationInFrames} photographic="conversation.jpg">
    {scenes.map((scene, i) => <SceneLayer key={i} index={i} scene={scene} total={scenes.length}><Shot scene={scene} index={i} portrait={portrait} title={title} preview={preview} /></SceneLayer>)}
  </FilmRoot>
);
