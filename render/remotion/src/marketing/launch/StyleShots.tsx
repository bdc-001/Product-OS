import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";
import { Bell, Check, FileText, Mic, Pause, Search, SkipBack, SkipForward } from "lucide-react";
import { SignalTrail, WriteOnPath } from "../Motifs";
import { IPhone } from "../kit/IPhone";
import { body, display, emphasisMask, K, progress, seeded, useLaunch, wordCues, type Field, type LaunchScene } from "./core";
import { KineticType } from "./Kinetic";
import { iconFor } from "./Orbit";

/** Shots for the chat, signal and compare film styles. Each style has its own devices, so no two films share a frame grammar. */

type ShotProps = { scene: LaunchScene; frame: number; global: number; field: Field };

const cueAt = (scene: LaunchScene, i: number) => scene.labelFrames?.[i] ?? 14 + i * 22;
const reveal = (scene: LaunchScene, frame: number, i: number, span = 12) => progress(frame, cueAt(scene, i), span);
const labelsOf = (scene: LaunchScene) => scene.labels || [];

/** The body line (often the illustrative-scenario disclaimer) sits low and quiet so it never competes with the device. */
function Footnote({ scene, frame, field }: { scene: LaunchScene; frame: number; field: Field }) {
  const { portrait } = useLaunch();
  if (!scene.body) return null;
  const light = field === "light" || field === "stage";
  return <div style={{ position: "absolute", left: 0, right: 0, bottom: portrait ? 140 : 44, display: "flex", justifyContent: "center", opacity: progress(frame, 18, 14) }}>
    <div data-film-text="body" style={{ maxWidth: portrait ? 920 : 1400, padding: "10px 22px", borderRadius: 999, fontFamily: body, fontSize: portrait ? 24 : 20, textAlign: "center",
      background: light ? "rgba(255,255,255,0.88)" : "rgba(3,10,35,0.55)", color: light ? "#334155" : "#E2EBFF", boxShadow: light ? "0 8px 24px rgba(10,46,122,0.12)" : "none" }}>{scene.body}</div>
  </div>;
}

function TopHeadline({ scene, frame, field, size }: { scene: LaunchScene; frame: number; field: Field; size?: number }) {
  const { portrait } = useLaunch();
  return <>
    <div style={{ position: "absolute", top: portrait ? 220 : 120, left: 0, right: 0, display: "flex", justifyContent: "center", padding: portrait ? "0 80px" : "0 160px" }}>
      <KineticType scene={scene} frame={frame} field={field} size={size ?? (portrait ? 74 : 66)} />
    </div>
    <Footnote scene={scene} frame={frame} field={field} />
  </>;
}

function SideHeadline({ scene, frame, field }: { scene: LaunchScene; frame: number; field: Field }) {
  const { portrait } = useLaunch();
  return <>
    <div style={{ position: "absolute", left: portrait ? 80 : 120, top: portrait ? 200 : 0, bottom: portrait ? undefined : 0, width: portrait ? 920 : 600, display: "flex", flexDirection: "column", justifyContent: "center" }}>
      <KineticType scene={scene} frame={frame} field={field} size={portrait ? 80 : 74} align="left" maxWidth={portrait ? 920 : 600} />
    </div>
    <Footnote scene={scene} frame={frame} field={field} />
  </>;
}

function Typing({ frame, color }: { frame: number; color: string }) {
  return <div style={{ display: "flex", gap: 8, padding: "18px 22px" }}>
    {[0, 1, 2].map(i => <div key={i} style={{ width: 11, height: 11, borderRadius: 6, background: color, opacity: 0.35 + 0.65 * Math.abs(Math.sin(frame / 5 + i * 0.9)) }} />)}
  </div>;
}

/** A team's inbox thread: the customer (named in the header) writes first on the left, replies come from the right. */
export function ChatShot({ scene, frame }: ShotProps) {
  const { portrait } = useLaunch();
  const labels = labelsOf(scene);
  const width = portrait ? 960 : 1240;
  const name = scene.screen?.title || "Customer";
  const replier = scene.screen?.speaker || "";
  // The window fits its thread so a short exchange never sits under an empty half-card.
  const height = (portrait ? 270 : 240) + labels.length * (portrait ? 170 : 150);
  return <AbsoluteFill>
    <TopHeadline scene={scene} frame={frame} field="light" />
    <div style={{ position: "absolute", left: "50%", top: portrait ? 560 : Math.max(300, 570 - height / 2), width, marginLeft: -width / 2, height, borderRadius: 30, background: "rgba(255,255,255,0.92)", boxShadow: "0 40px 90px rgba(10,46,122,0.16)", border: "1px solid #E3EBF8", opacity: progress(frame, 0, 14), transform: `translateY(${(1 - progress(frame, 0, 18)) * 40}px)`, display: "flex", flexDirection: "column" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 16, padding: "22px 30px", borderBottom: "1px solid #EEF2F8" }}>
        <div style={{ width: 48, height: 48, borderRadius: 24, background: "linear-gradient(145deg,#C9D9FF,#7FA8FF)", display: "grid", placeItems: "center", color: K.navy, fontFamily: display, fontWeight: 700, fontSize: 20 }}>{name.slice(0, 1).toUpperCase()}</div>
        <div style={{ fontFamily: body, fontWeight: 600, fontSize: 24, color: K.ink }}>{name}</div>
        <div style={{ marginLeft: "auto", width: 12, height: 12, borderRadius: 6, background: "#22C55E" }} />
      </div>
      <div style={{ flex: 1, padding: "24px 30px", display: "flex", flexDirection: "column", gap: 18, justifyContent: "flex-start" }}>
        {labels.map((label, i) => {
          const mine = i % 2 === 1;
          const at = cueAt(scene, i);
          const typing = frame >= at - 16 && frame < at;
          const p = progress(frame, at, 10);
          if (frame < at - 16) return null;
          return <div key={i} style={{ alignSelf: mine ? "flex-end" : "flex-start", maxWidth: "74%", display: "flex", flexDirection: "column", alignItems: mine ? "flex-end" : "flex-start", gap: 8 }}>
            {mine && replier && <div data-film-text="label" style={{ fontFamily: body, fontSize: portrait ? 24 : 22, fontWeight: 600, color: "#64748B", padding: "0 10px" }}>{replier}</div>}
            {typing ? <div style={{ borderRadius: 26, background: mine ? K.blue : "#EEF1F6" }}><Typing frame={frame} color={mine ? "#FFFFFF" : "#8A97AB"} /></div>
              : <div data-film-text="label" style={{ padding: "22px 32px", borderRadius: mine ? "30px 30px 8px 30px" : "30px 30px 30px 8px", background: mine ? K.blue : "#EEF1F6", color: mine ? "#FFFFFF" : K.ink, fontFamily: body, fontSize: portrait ? 38 : 36, lineHeight: 1.35, opacity: p, transform: `translateY(${(1 - p) * 16}px) scale(${0.96 + p * 0.04})`, transformOrigin: mine ? "100% 100%" : "0% 100%", boxShadow: mine ? "0 14px 30px rgba(26,98,242,0.25)" : "none" }}>{label}</div>}
          </div>;
        })}
      </div>
      <div style={{ margin: "0 24px 24px", padding: "18px 24px", borderRadius: 999, background: "#F3F6FB", display: "flex", alignItems: "center", justifyContent: "space-between", fontFamily: body, fontSize: 22, color: "#94A3B8" }}>
        <span>Type a message…</span>
        <div style={{ width: 42, height: 42, borderRadius: 21, background: K.blue, color: "#FFFFFF", display: "grid", placeItems: "center" }}><Mic size={20} /></div>
      </div>
    </div>
  </AbsoluteFill>;
}

/** A search bar: the first label is typed as the query on its cue, later labels land as results. */
export function SearchShot({ scene, frame }: ShotProps) {
  const { portrait } = useLaunch();
  const [query = "", ...results] = labelsOf(scene);
  const at = Math.min(cueAt(scene, 0), 10);
  const typed = query.slice(0, Math.max(0, Math.floor((frame - at + 6) * 1.6)));
  const width = portrait ? 960 : 1360;
  const caret = Math.floor(frame / 8) % 2 === 0 && typed.length < query.length + 1;
  return <AbsoluteFill>
    <TopHeadline scene={scene} frame={frame} field="light" />
    <div style={{ position: "absolute", left: "50%", top: portrait ? 620 : 330, width, marginLeft: -width / 2 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 26, padding: "34px 44px", borderRadius: 999, background: "#FFFFFF", boxShadow: "0 30px 70px rgba(10,46,122,0.18), 0 0 0 1px #E3EBF8", opacity: progress(frame, 0, 12), transform: `scale(${0.94 + progress(frame, 0, 16) * 0.06})` }}>
        <Search size={44} color="#64748B" />
        <div data-film-text="label" style={{ fontFamily: body, fontSize: portrait ? 42 : 44, color: K.ink, whiteSpace: "nowrap", overflow: "hidden" }}>{typed}<span style={{ opacity: caret ? 1 : 0, color: K.blue }}>|</span></div>
      </div>
      <div style={{ marginTop: 34, display: "flex", flexDirection: "column", gap: 22 }}>
        {results.map((result, i) => {
          const p = reveal(scene, frame, i + 1);
          return <div key={i} style={{ display: "flex", alignItems: "center", gap: 28, padding: "40px 44px", borderRadius: 30, background: "#FFFFFF", boxShadow: "0 30px 70px rgba(10,46,122,0.14)", border: "1px solid #E3EBF8", opacity: p, transform: `translateY(${(1 - p) * 24}px) scale(${0.97 + p * 0.03})` }}>
            <div style={{ width: 64, height: 64, borderRadius: 18, background: K.pale, color: K.blue, display: "grid", placeItems: "center", flexShrink: 0 }}>{iconFor(result, 30)}</div>
            <div data-film-text="label" style={{ fontFamily: display, fontWeight: 700, fontSize: portrait ? 44 : 46, color: K.ink, letterSpacing: -0.5 }}>{result}</div>
          </div>;
        })}
      </div>
    </div>
  </AbsoluteFill>;
}

/** Documents pile up on their cues: the paper trail behind the problem, or the pieces the product reads. */
export function DocsShot({ scene, frame, field }: ShotProps) {
  const { portrait } = useLaunch();
  const labels = labelsOf(scene);
  const fields = (scene.screen?.rows || []).filter(row => row.label && row.hint).slice(0, 5);
  const baseX = portrait ? 120 : 780, baseY = portrait ? 760 : 190;
  const stepY = portrait ? 120 : 96;
  return <AbsoluteFill>
    <SideHeadline scene={scene} frame={frame} field={field} />
    {labels.map((label, i) => {
      // Paper arrives at once so the shot never opens empty; each title lands on its own cue.
      const p = progress(frame, Math.min(cueAt(scene, i), 4 + i * 8), 16);
      const named = reveal(scene, frame, i, 10);
      const blank = /\b(empty|blank|no notes?|nothing)\b/i.test(label);
      const x = baseX + i * (portrait ? 50 : 60), y = baseY + i * stepY;
      // Titles live in the title bar, which the next window down never covers.
      return <div key={i} style={{ position: "absolute", left: x, top: y, width: portrait ? 760 : 860, height: portrait ? 560 : 500, borderRadius: 20, background: "#FFFFFF", boxShadow: `0 36px 80px rgba(6,34,120,0.35), 0 0 0 ${named * 5}px rgba(175,202,251,0.9)`, opacity: p, transform: `translateY(${(1 - p) * 120}px) rotate(${(1 - p) * 3}deg) scale(${0.98 + named * 0.02})`, overflow: "hidden" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, height: stepY - 8, padding: "0 24px", borderBottom: "1px solid #EEF2F8", background: "#F8FAFE" }}>
          {["#FF5F57", "#FEBC2E", "#28C840"].map(c => <div key={c} style={{ width: 12, height: 12, borderRadius: 6, background: c }} />)}
          <FileText size={28} color={K.blue} style={{ marginLeft: 14 }} />
          <div data-film-text="label" style={{ fontFamily: display, fontWeight: 700, fontSize: portrait ? 32 : 30, color: K.ink, whiteSpace: "nowrap" }}>{label}</div>
        </div>
        <div style={{ padding: "26px 34px" }}>
          {blank
            ? <div style={{ marginTop: 60, textAlign: "center", fontFamily: body, fontSize: 26, fontStyle: "italic", color: "#94A3B8" }}>No notes yet</div>
            : i === labels.length - 1 && fields.length
            ? [scene.screen?.title && scene.screen.title !== label
              ? <div key="title" data-film-text="label" style={{ fontFamily: display, fontWeight: 700, fontSize: 28, color: K.blue, marginBottom: 6 }}>{scene.screen.title}</div>
              : null, ...fields.map((row, k) => {
              const q = progress(frame, Math.min(cueAt(scene, i), 12) + 6 + k * 6, 10);
              return <div key={k} style={{ display: "flex", gap: 22, alignItems: "baseline", padding: "12px 0", borderBottom: "1px solid #EEF2F8", opacity: q, transform: `translateX(${(1 - q) * 16}px)` }}>
                <div data-film-text="label" style={{ width: 230, flexShrink: 0, fontFamily: body, fontSize: 22, fontWeight: 600, color: "#64748B" }}>{row.label}</div>
                <div data-film-text="label" style={{ fontFamily: body, fontSize: 26, color: K.ink, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{row.hint}</div>
              </div>;
            })]
            : Array.from({ length: 5 }, (_, k) => <div key={k} style={{ display: "flex", gap: 18, alignItems: "center", marginTop: k ? 20 : 4 }}>
              <div style={{ height: 14, borderRadius: 7, width: 120 + seeded(i * 7 + k) * 60, background: "#D6E4FF" }} />
              <div style={{ height: 14, borderRadius: 7, width: `${30 + seeded(i * 9 + k) * 35}%`, background: "#E6ECF5" }} />
            </div>)}
        </div>
      </div>;
    })}
  </AbsoluteFill>;
}

/** Radar around the brand mark: pulses go out, and a result card fills with the checks the product runs. */
export function PulseShot({ scene, frame, global, field }: ShotProps) {
  const { portrait } = useLaunch();
  const labels = labelsOf(scene);
  const cx = portrait ? 540 : 700, cy = portrait ? 1120 : 600;
  const card = progress(frame, Math.max(8, cueAt(scene, 0) - 10), 16);
  const W = portrait ? 1080 : 1920, H = portrait ? 1920 : 1080;
  const link = portrait ? `M${cx} ${cy + 90} L${cx} 1480` : `M${cx + 90} ${cy} L1120 ${cy}`;
  return <AbsoluteFill>
    <TopHeadline scene={scene} frame={frame} field={field} size={portrait ? 72 : 62} />
    <svg viewBox={`0 0 ${W} ${H}`} style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
      <WriteOnPath d={link} progress={card} color="rgba(220,231,255,0.8)" width={3} />
    </svg>
    {card > 0.6 && <SignalTrail d={link} start={Math.max(8, cueAt(scene, 0) - 10)} viewW={W} viewH={H} color="#FFFFFF" size={14} />}
    {Array.from({ length: 4 }, (_, i) => {
      const t = ((global + i * 22) % 88) / 88;
      const r = 90 + t * 420;
      return <div key={i} style={{ position: "absolute", left: cx - r, top: cy - r, width: r * 2, height: r * 2, borderRadius: "50%", border: "2px solid rgba(127,168,255,0.9)", opacity: (1 - t) * 0.5 }} />;
    })}
    <div style={{ position: "absolute", left: cx - 330, top: cy - 330, width: 660, height: 660, borderRadius: "50%", background: `conic-gradient(from ${global * 3}deg, rgba(127,168,255,0.35), transparent 22%)`, maskImage: "radial-gradient(circle, black 30%, transparent 70%)", WebkitMaskImage: "radial-gradient(circle, black 30%, transparent 70%)" }} />
    <div style={{ position: "absolute", left: cx - 90, top: cy - 90, width: 180, height: 180, borderRadius: 90, background: "radial-gradient(circle at 35% 30%, #FFFFFF, #D6E4FF)", display: "grid", placeItems: "center", boxShadow: `0 0 ${70 + Math.sin(global / 10) * 20}px rgba(46,116,255,0.8)` }}>
      <Img src={staticFile("brand-mark.svg")} style={{ width: 104 }} />
    </div>
    <div style={{ position: "absolute", left: portrait ? 140 : 1120, top: portrait ? 1480 : 360, width: portrait ? 800 : 620, padding: "30px 34px", borderRadius: 26, background: "rgba(16,30,72,0.72)", border: "1px solid rgba(175,202,251,0.4)", boxShadow: "0 40px 90px rgba(3,6,15,0.5)", opacity: card, transform: `translateX(${(1 - card) * 60}px)` }}>
      {scene.screen?.title && <div data-film-text="label" style={{ fontFamily: display, fontWeight: 700, fontSize: 30, color: "#FFFFFF", marginBottom: 20 }}>{scene.screen.title}</div>}
      {labels.map((label, i) => {
        const p = reveal(scene, frame, i);
        return <div key={i} style={{ display: "flex", alignItems: "center", gap: 18, padding: "14px 0", borderTop: i ? "1px solid rgba(175,202,251,0.18)" : "none", opacity: 0.35 + p * 0.65 }}>
          <div style={{ width: 40, height: 40, borderRadius: 20, background: p > 0.5 ? "#22C55E" : "rgba(175,202,251,0.2)", color: "#FFFFFF", display: "grid", placeItems: "center", transform: `scale(${0.8 + p * 0.2})` }}><Check size={22} strokeWidth={3} /></div>
          <div data-film-text="label" style={{ fontFamily: body, fontSize: 27, color: "#EAF1FF" }}>{label}</div>
        </div>;
      })}
    </div>
  </AbsoluteFill>;
}

/** Floating record fields: details scattered across channels, each lighting on its cue; the last one is the one that matters. */
export function FieldsShot({ scene, frame, global, field }: ShotProps) {
  const { portrait } = useLaunch();
  const labels = labelsOf(scene);
  const spots = portrait ? [{ x: 140, y: 760 }, { x: 420, y: 1060 }, { x: 180, y: 1380 }] : [{ x: 260, y: 470 }, { x: 760, y: 660 }, { x: 1240, y: 440 }];
  return <AbsoluteFill>
    <TopHeadline scene={scene} frame={frame} field={field} size={portrait ? 72 : 64} />
    {Array.from({ length: 18 }, (_, i) => {
      const p = progress(frame, 2 + i * 1.5, 12);
      return <div key={`g${i}`} style={{ position: "absolute", left: `${8 + seeded(i) * 84}%`, top: `${30 + seeded(i + 40) * 62}%`, width: 150 + seeded(i + 7) * 120, height: 14, borderRadius: 7, background: "rgba(175,202,251,0.14)", opacity: p, transform: `translateY(${Math.sin(global / 30 + i) * 8}px)` }} />;
    })}
    {labels.map((label, i) => {
      const s = spots[i % spots.length];
      const p = reveal(scene, frame, i, 14);
      const key = i === labels.length - 1 && labels.length > 1;
      return <div key={i} style={{ position: "absolute", left: s.x, top: s.y + Math.sin(global / 24 + i * 2) * 10, display: "flex", alignItems: "center", gap: 18, padding: "18px 30px 18px 18px", borderRadius: 22, background: key ? "#FFFFFF" : "rgba(16,30,72,0.75)", border: key ? "none" : "1px solid rgba(175,202,251,0.45)", boxShadow: key ? `0 0 0 ${6 + Math.sin(global / 8) * 3}px rgba(46,116,255,0.35), 0 30px 70px rgba(3,6,15,0.5)` : "0 24px 60px rgba(3,6,15,0.45)", opacity: p, transform: `scale(${0.85 + p * 0.15})` }}>
        <div style={{ width: 54, height: 54, borderRadius: 16, background: key ? K.blue : "rgba(46,116,255,0.3)", color: "#FFFFFF", display: "grid", placeItems: "center" }}>{iconFor(label, 26)}</div>
        <div>
          <div data-film-text="label" style={{ fontFamily: body, fontWeight: 600, fontSize: portrait ? 32 : 30, color: key ? K.ink : "#EAF1FF", whiteSpace: "nowrap" }}>{label}</div>
          <div style={{ marginTop: 10, height: 10, width: 180, borderRadius: 5, background: key ? "#D6E4FF" : "rgba(175,202,251,0.3)" }} />
        </div>
      </div>;
    })}
  </AbsoluteFill>;
}

/** Inputs pass through the product and come out as one result: the earlier labels go in, the last label comes out. */
export function RelayShot({ scene, frame, field }: ShotProps) {
  const { portrait } = useLaunch();
  const labels = labelsOf(scene);
  const inputs = labels.slice(0, -1), output = labels.at(-1) || "";
  const W = portrait ? 1080 : 1920, H = portrait ? 1920 : 1080;
  const hub = portrait ? { x: 540, y: 1150 } : { x: 960, y: 620 };
  const ins = inputs.map((_, i) => portrait ? { x: 280 + i * 520, y: 760 } : { x: 400, y: 520 + i * 200 - (inputs.length - 1) * 100 });
  const out = portrait ? { x: 540, y: 1560 } : { x: 1520, y: 620 };
  const outAt = cueAt(scene, labels.length - 1);
  const chip = (label: string, at: { x: number; y: number }, p: number, lit: boolean) => <div style={{ position: "absolute", left: at.x, top: at.y, transform: `translate(-50%,-50%) scale(${0.85 + p * 0.15})`, opacity: p }}>
    <div data-film-text="label" style={{ display: "flex", alignItems: "center", gap: 14, padding: "16px 28px 16px 16px", borderRadius: 999, whiteSpace: "nowrap", background: lit ? "#FFFFFF" : "rgba(16,30,72,0.8)", border: lit ? "none" : "1px solid rgba(175,202,251,0.45)", color: lit ? K.ink : "#EAF1FF", fontFamily: body, fontWeight: 600, fontSize: portrait ? 30 : 28, boxShadow: "0 24px 60px rgba(3,6,15,0.45)" }}>
      <div style={{ width: 48, height: 48, borderRadius: 24, background: lit ? K.blue : "rgba(46,116,255,0.35)", color: "#FFFFFF", display: "grid", placeItems: "center" }}>{iconFor(label, 24)}</div>{label}
    </div>
  </div>;
  return <AbsoluteFill>
    <TopHeadline scene={scene} frame={frame} field={field} size={portrait ? 72 : 62} />
    <svg viewBox={`0 0 ${W} ${H}`} style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
      {ins.map((a, i) => <WriteOnPath key={i} d={`M${a.x} ${a.y} L${hub.x} ${hub.y}`} progress={reveal(scene, frame, i, 18)} color={K.sky} width={2.5} />)}
      <WriteOnPath d={`M${hub.x} ${hub.y} L${out.x} ${out.y}`} progress={progress(frame, outAt - 8, 16)} color="#FFFFFF" width={3} />
    </svg>
    {ins.map((a, i) => reveal(scene, frame, i) > 0.3 ? <SignalTrail key={`t${i}`} d={`M${a.x} ${a.y} L${hub.x} ${hub.y}`} start={cueAt(scene, i)} viewW={W} viewH={H} color={K.sky} size={12} /> : null)}
    <div style={{ position: "absolute", left: hub.x - 88, top: hub.y - 88, width: 176, height: 176, borderRadius: 88, background: "radial-gradient(circle at 35% 30%, #FFFFFF, #D6E4FF)", display: "grid", placeItems: "center", boxShadow: "0 0 70px rgba(46,116,255,0.7)", opacity: progress(frame, 0, 14) }}>
      <Img src={staticFile("brand-mark.svg")} style={{ width: 100 }} />
    </div>
    {inputs.map((label, i) => <React.Fragment key={i}>{chip(label, ins[i], reveal(scene, frame, i), false)}</React.Fragment>)}
    {output && chip(output, out, progress(frame, outAt, 14), true)}
  </AbsoluteFill>;
}

/** A recording, played back: the playhead runs and the moment named by the first label lights up on its cue. */
export function WaveformShot({ scene, frame, field }: ShotProps) {
  const { portrait } = useLaunch();
  const labels = labelsOf(scene);
  const bars = portrait ? 46 : 84;
  const width = portrait ? 940 : 1400;
  const spots = labels.map((_, i) => labels.length === 1 ? 0.62 : 0.38 + i * 0.3);
  const head = progress(frame, 0, Math.max(30, scene.frames - 6));
  return <AbsoluteFill>
    <TopHeadline scene={scene} frame={frame} field={field} size={portrait ? 72 : 64} />
    <div style={{ position: "absolute", left: "50%", top: portrait ? 820 : 430, width, marginLeft: -width / 2, padding: "40px 46px 34px", borderRadius: 30, background: "rgba(16,30,72,0.6)", border: "1px solid rgba(175,202,251,0.3)", boxShadow: "0 40px 90px rgba(3,6,15,0.5)", opacity: progress(frame, 0, 14) }}>
      <div style={{ position: "relative", height: 200, display: "flex", alignItems: "center", gap: 6 }}>
        {Array.from({ length: bars }, (_, b) => {
          const x = b / bars;
          const lit = spots.findIndex(s => Math.abs(x - s) < 0.06);
          const hot = lit >= 0 && reveal(scene, frame, lit) > 0.4;
          return <div key={b} style={{ flex: 1, borderRadius: 4, height: 24 + seeded(b + 3) * 150 * (0.5 + 0.5 * Math.abs(Math.sin(b * 0.4))), background: hot ? "#FF6B5B" : x < head ? "#FFFFFF" : "rgba(175,202,251,0.45)" }} />;
        })}
        <div style={{ position: "absolute", top: -10, bottom: -10, left: `${head * 100}%`, width: 3, background: "#FFFFFF", boxShadow: "0 0 18px rgba(255,255,255,0.8)" }} />
        {labels.map((label, i) => {
          const p = reveal(scene, frame, i);
          return <div key={i} data-film-text="label" style={{ position: "absolute", left: `${spots[i] * 100}%`, top: -78, transform: `translate(-50%, ${(1 - p) * 14}px)`, opacity: p, padding: "10px 22px", borderRadius: 999, background: "#FF6B5B", color: "#FFFFFF", fontFamily: body, fontWeight: 600, fontSize: 24, whiteSpace: "nowrap" }}>{label}</div>;
        })}
      </div>
      <div style={{ marginTop: 30, display: "flex", alignItems: "center", justifyContent: "space-between", fontFamily: body, fontSize: 22, color: "#BFD3FF" }}>
        <span>{`00:${String(Math.floor(head * 48)).padStart(2, "0")}`}</span>
        <div style={{ display: "flex", alignItems: "center", gap: 34, color: "#FFFFFF" }}><SkipBack size={28} /><div style={{ width: 64, height: 64, borderRadius: 32, background: "#FFFFFF", color: K.navy, display: "grid", placeItems: "center" }}><Pause size={28} /></div><SkipForward size={28} /></div>
        <span>00:48</span>
      </div>
    </div>
  </AbsoluteFill>;
}

/** A phone at rest: notifications land on the lock screen on their cues, the problem arriving uninvited. */
export function LockscreenShot({ scene, frame, field }: ShotProps) {
  const { portrait } = useLaunch();
  const labels = labelsOf(scene);
  const app = scene.screen?.title || "Messages";
  const enter = progress(frame, 0, 18);
  return <AbsoluteFill>
    <SideHeadline scene={scene} frame={frame} field={field} />
    <div style={{ position: "absolute", left: portrait ? 330 : 1180, top: portrait ? 780 : 70, opacity: enter, transform: `translateY(${(1 - enter) * 60}px)` }}>
      <IPhone scale={portrait ? 0.95 : 1.08} appearance="dark">
        <div style={{ width: 1179, height: 2556, background: "linear-gradient(170deg, #1F3F9E 0%, #0B1D57 45%, #050A1E 100%)", position: "relative", fontFamily: body }}>
          <div style={{ position: "absolute", top: 300, left: 0, right: 0, textAlign: "center", color: "rgba(255,255,255,0.85)", fontSize: 62, fontWeight: 500 }}>Monday 9 June</div>
          <div style={{ position: "absolute", top: 370, left: 0, right: 0, textAlign: "center", color: "#FFFFFF", fontSize: 330, fontWeight: 600, letterSpacing: -6 }}>9:41</div>
          <div style={{ position: "absolute", top: 1060, left: 60, right: 60, display: "flex", flexDirection: "column", gap: 36 }}>
            {labels.map((label, i) => {
              const p = reveal(scene, frame, i, 14);
              return <div key={i} style={{ padding: "40px 46px", borderRadius: 64, background: "rgba(245,247,252,0.88)", opacity: p, transform: `translateY(${(1 - p) * -80}px) scale(${0.94 + p * 0.06})` }}>
                <div style={{ display: "flex", alignItems: "center", gap: 26, fontSize: 44, color: "#475569" }}>
                  <div style={{ width: 84, height: 84, borderRadius: 22, background: "linear-gradient(145deg,#34C759,#1FA347)", color: "#FFFFFF", display: "grid", placeItems: "center" }}><Bell size={46} /></div>
                  <span style={{ fontWeight: 600, color: "#0F172A" }}>{app}</span><span style={{ marginLeft: "auto" }}>now</span>
                </div>
                <div data-film-text="label" style={{ marginTop: 22, fontSize: 56, lineHeight: 1.3, color: "#0F172A" }}>{label}</div>
              </div>;
            })}
          </div>
        </div>
      </IPhone>
    </div>
  </AbsoluteFill>;
}

/** Plain white, one line typed out in sync with the voice. The quietest frame in the film. */
export function TypewriterShot({ scene, frame }: ShotProps) {
  const { audioFrom, portrait } = useLaunch();
  const cues = wordCues(scene, scene.headline, audioFrom);
  const mask = emphasisMask(scene.headline, scene.emphasis);
  const size = portrait ? 92 : 104;
  const last = cues.at(-1)?.at ?? 0;
  const caret = frame > last + 20 ? Math.floor(frame / 9) % 2 === 0 : true;
  return <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", padding: portrait ? "0 90px" : "0 200px" }}>
    <div data-film-text="headline" style={{ fontFamily: display, fontWeight: 600, fontSize: size, lineHeight: 1.12, letterSpacing: -size * 0.03, color: K.ink, textAlign: "center", textWrap: "balance" }}>
      {cues.map(({ word, at }, i) => {
        const chars = Math.max(0, Math.min(word.length, Math.floor((frame - at) * 1.4)));
        return <React.Fragment key={i}>
          <span style={{ color: mask[i] ? K.blue : undefined }}>{word.slice(0, chars)}<span style={{ visibility: "hidden" }}>{word.slice(chars)}</span></span>{i < cues.length - 1 ? " " : ""}
        </React.Fragment>;
      })}
      <span style={{ display: "inline-block", width: size * 0.06, height: size * 0.9, marginLeft: 8, verticalAlign: "-0.1em", background: K.blue, opacity: caret ? 1 : 0 }} />
    </div>
  </AbsoluteFill>;
}

/** The same moment, two ways: left without, right with. Bars compare outcomes without inventing a number. */
export function VersusShot({ scene, frame, field }: ShotProps) {
  const { portrait } = useLaunch();
  const [left = "", right = ""] = labelsOf(scene);
  const panel = (label: string, i: number, good: boolean) => {
    const p = reveal(scene, frame, i, 16);
    const fill = progress(frame, cueAt(scene, i) + 6, 26) * (good ? 0.86 : 0.24);
    return <div style={{ flex: 1, padding: portrait ? "40px 44px" : "46px 52px", borderRadius: 30, background: good ? "#FFFFFF" : "rgba(255,255,255,0.6)", border: good ? `2px solid ${K.blue}` : "1px solid #E3EBF8", boxShadow: good ? "0 40px 90px rgba(26,98,242,0.22)" : "none", opacity: p, transform: `translateY(${(1 - p) * 40}px)` }}>
      <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
        <div style={{ width: 64, height: 64, borderRadius: 32, background: good ? K.blue : "#CBD5E1", color: "#FFFFFF", display: "grid", placeItems: "center" }}>{iconFor(label, 30)}</div>
        <div data-film-text="label" style={{ fontFamily: display, fontWeight: 700, fontSize: portrait ? 38 : 36, color: good ? K.ink : "#64748B" }}>{label}</div>
      </div>
      <div style={{ marginTop: 44, height: 26, borderRadius: 13, background: "#EEF2F8", overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${fill * 100}%`, borderRadius: 13, background: good ? `linear-gradient(90deg, ${K.sky}, ${K.blue})` : "#94A3B8" }} />
      </div>
      {[0.8, 0.55].map((w, k) => <div key={k} style={{ marginTop: 24, height: 12, borderRadius: 6, width: `${w * 100}%`, background: "#EEF2F8" }} />)}
    </div>;
  };
  return <AbsoluteFill>
    <TopHeadline scene={scene} frame={frame} field={field} />
    <div style={{ position: "absolute", left: portrait ? 80 : 200, right: portrait ? 80 : 200, top: portrait ? 700 : 400, display: "flex", flexDirection: portrait ? "column" : "row", gap: portrait ? 40 : 60, alignItems: "stretch" }}>
      {panel(left, 0, false)}
      {panel(right, 1, true)}
    </div>
  </AbsoluteFill>;
}

/** Full-bleed brand blue: arcs leave the product and land on each destination on its cue. */
export function ArcsShot({ scene, frame, global, field }: ShotProps) {
  const { portrait } = useLaunch();
  const labels = labelsOf(scene);
  const W = portrait ? 1080 : 1920, H = portrait ? 1920 : 1080;
  const hub = portrait ? { x: 540, y: 1500 } : { x: 520, y: 700 };
  const ends = portrait ? [{ x: 260, y: 820 }, { x: 800, y: 980 }, { x: 420, y: 1180 }] : [{ x: 1380, y: 400 }, { x: 1560, y: 640 }, { x: 1280, y: 860 }];
  const arc = (a: { x: number; y: number }) => `M${hub.x} ${hub.y} Q${(hub.x + a.x) / 2} ${Math.min(hub.y, a.y) - 260} ${a.x} ${a.y}`;
  return <AbsoluteFill>
    <AbsoluteFill style={{ opacity: 0.35, backgroundSize: "44px 44px", backgroundPosition: `${(global * 0.4) % 44}px 0px`, backgroundImage: "radial-gradient(circle, rgba(255,255,255,0.7) 1.4px, transparent 1.8px)", maskImage: "radial-gradient(ellipse at 60% 55%, black 10%, transparent 75%)", WebkitMaskImage: "radial-gradient(ellipse at 60% 55%, black 10%, transparent 75%)" }} />
    <div style={{ position: "absolute", left: portrait ? 80 : 120, top: portrait ? 220 : 130, width: portrait ? 920 : 900 }}>
      <KineticType scene={scene} frame={frame} field={field} size={portrait ? 76 : 70} align="left" maxWidth={portrait ? 920 : 900} />
    </div>
    <Footnote scene={scene} frame={frame} field={field} />
    <svg viewBox={`0 0 ${W} ${H}`} style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
      {labels.map((_, i) => <WriteOnPath key={i} d={arc(ends[i % ends.length])} progress={reveal(scene, frame, i, 20)} color="#FFFFFF" width={3} />)}
    </svg>
    {labels.map((_, i) => reveal(scene, frame, i) > 0.5 ? <SignalTrail key={`t${i}`} d={arc(ends[i % ends.length])} start={cueAt(scene, i)} viewW={W} viewH={H} color="#FFFFFF" size={12} /> : null)}
    <div style={{ position: "absolute", left: hub.x - 80, top: hub.y - 80, width: 160, height: 160, borderRadius: 80, background: "#FFFFFF", display: "grid", placeItems: "center", boxShadow: `0 0 0 ${14 + Math.sin(global / 9) * 6}px rgba(255,255,255,0.18), 0 30px 70px rgba(6,34,120,0.45)` }}>
      <Img src={staticFile("brand-mark.svg")} style={{ width: 92 }} />
    </div>
    {labels.map((label, i) => {
      const e = ends[i % ends.length];
      const p = progress(frame, cueAt(scene, i) + 12, 12);
      return <div key={i} data-film-text="label" style={{ position: "absolute", left: e.x, top: e.y, transform: `translate(-50%, -50%) scale(${0.85 + p * 0.15})`, opacity: p, padding: "16px 28px", borderRadius: 999, background: "#FFFFFF", color: K.ink, fontFamily: body, fontWeight: 600, fontSize: portrait ? 30 : 28, whiteSpace: "nowrap", boxShadow: "0 24px 60px rgba(6,34,120,0.4)" }}>{label}</div>;
    })}
  </AbsoluteFill>;
}

export const STYLE_SHOTS: Record<string, (props: ShotProps) => React.ReactElement> = {
  chat: ChatShot, search: SearchShot, docs: DocsShot, pulse: PulseShot,
  fields: FieldsShot, relay: RelayShot, waveform: WaveformShot,
  lockscreen: LockscreenShot, typewriter: TypewriterShot, versus: VersusShot, arcs: ArcsShot,
};

export const STYLE_FIELDS: Record<string, Field> = {
  chat: "light", search: "light", lockscreen: "light", typewriter: "light", versus: "light",
  docs: "brand", arcs: "brand", pulse: "brand", fields: "dark", relay: "dark", waveform: "dark",
};
