import React from "react";
import { productName } from "../brand";
import { AbsoluteFill, Img, staticFile } from "remotion";
import { BarChart3, Building2, FileText, Headphones, LayoutTemplate, ListChecks, Megaphone, MessageSquare, Network, PhoneCall, ShieldCheck, SlidersHorizontal, Smartphone, Sparkles, Users, WandSparkles } from "lucide-react";
import { SignalTrail, WriteOnPath } from "../Motifs";
import { body, display, K, progress, useLaunch, type LaunchScene } from "./core";
import { KineticType } from "./Kinetic";

export function iconFor(label: string, size = 28) {
  const text = label.toLowerCase();
  const props = { size, strokeWidth: 2 };
  if (/waba|account/.test(text)) return <Building2 {...props} />;
  if (/number|sender|\bdid\b/.test(text)) return <Smartphone {...props} />;
  if (/template/.test(text)) return <LayoutTemplate {...props} />;
  if (/analytic|chart|dashboard/.test(text)) return <BarChart3 {...props} />;
  if (/campaign/.test(text)) return <Megaphone {...props} />;
  if (/filter|condition/.test(text)) return <SlidersHorizontal {...props} />;
  if (/call|interaction|conversation|lead/.test(text)) return <PhoneCall {...props} />;
  if (/parameter|evaluat|score|judge/.test(text)) return <ListChecks {...props} />;
  if (/root|cause|cluster|pattern|group/.test(text)) return <Network {...props} />;
  if (/patch|prompt|fix/.test(text)) return <WandSparkles {...props} />;
  if (/safe|compliance|privacy/.test(text)) return <ShieldCheck {...props} />;
  if (/team|operator|agent/.test(text)) return <Users {...props} />;
  if (/transcript|report|finding/.test(text)) return <FileText {...props} />;
  return <Sparkles {...props} />;
}

const DECOR = [PhoneCall, MessageSquare, Headphones, FileText, ListChecks];

/** A hub with its real inputs and outputs: nodes connect on the words that name them. */
export function Orbit({ scene, frame, global }: { scene: LaunchScene; frame: number; global: number }) {
  const { portrait } = useLaunch();
  const W = portrait ? 1080 : 1920, H = portrait ? 1920 : 1080;
  const hub = portrait ? { x: 540, y: 820 } : { x: 960, y: 590 };
  const labels = scene.labels || [];
  const anchors = portrait
    ? labels.map((_, i) => ({ x: 540, y: 1180 + i * 150 }))
    : labels.length === 2 ? [{ x: 430, y: 590 }, { x: 1490, y: 590 }]
    : [{ x: 420, y: 450 }, { x: 1500, y: 450 }, { x: 1500, y: 760 }].slice(0, labels.length);
  const reveal = (i: number) => progress(frame, scene.labelFrames?.[i] ?? 12 + i * 18, 14);
  const intro = progress(frame, 0, 16);
  const spin = global * 0.25;
  return <AbsoluteFill>
    <div style={{ position: "absolute", top: portrait ? 220 : 110, left: 0, right: 0, display: "flex", justifyContent: "center", padding: "0 120px" }}>
      <KineticType scene={scene} frame={frame} field="dark" size={portrait ? 76 : 70} />
    </div>
    <svg viewBox={`0 0 ${W} ${H}`} style={{ position: "absolute", inset: 0, width: "100%", height: "100%", overflow: "visible" }}>
      {anchors.map((a, i) => {
        const d = `M${hub.x} ${hub.y} L${a.x} ${a.y}`;
        return <WriteOnPath key={i} d={d} progress={reveal(i)} color={K.sky} width={2.5} />;
      })}
      <g transform={`translate(${hub.x} ${hub.y})`} opacity={intro}>
        <circle r={250} fill="none" stroke="rgba(175,202,251,0.18)" strokeWidth={1.5} />
        <g transform={`rotate(${spin})`}>
          {Array.from({ length: 72 }, (_, t) => {
            const long = t % 6 === 0;
            const a = (t / 72) * Math.PI * 2;
            return <line key={t} x1={Math.cos(a) * 176} y1={Math.sin(a) * 176} x2={Math.cos(a) * (long ? 196 : 188)} y2={Math.sin(a) * (long ? 196 : 188)} stroke="rgba(220,231,255,0.6)" strokeWidth={long ? 2 : 1} />;
          })}
        </g>
        <circle r={200} fill="none" stroke="rgba(220,231,255,0.35)" strokeWidth={1} />
        <circle r={150} fill="url(#hubGlow)" />
        <defs><radialGradient id="hubGlow"><stop offset="0%" stopColor="rgba(46,116,255,0.55)" /><stop offset="100%" stopColor="rgba(46,116,255,0)" /></radialGradient></defs>
      </g>
    </svg>
    {anchors.map((a, i) => reveal(i) > 0.2 ? <SignalTrail key={`s${i}`} d={`M${hub.x} ${hub.y} L${a.x} ${a.y}`} start={scene.labelFrames?.[i] ?? 12 + i * 18} viewW={W} viewH={H} color={K.sky} size={12} /> : null)}
    {DECOR.map((Icon, i) => {
      const a = (i / DECOR.length) * Math.PI * 2 + global * 0.006;
      const p = progress(frame, 4 + i * 3, 12);
      return <div key={i} style={{ position: "absolute", left: hub.x + Math.cos(a) * 250 - 30, top: hub.y + Math.sin(a) * 250 - 30, width: 60, height: 60, borderRadius: 30, background: "rgba(10,46,122,0.85)", border: "1px solid rgba(175,202,251,0.45)", color: "#DCE7FF", display: "grid", placeItems: "center", opacity: p * 0.9, transform: `scale(${0.6 + p * 0.4})` }}><Icon size={26} strokeWidth={1.8} /></div>;
    })}
    <div style={{ position: "absolute", left: hub.x - 95, top: hub.y - 95, width: 190, height: 190, borderRadius: 95, background: "radial-gradient(circle at 35% 30%, #FFFFFF 0%, #EEF4FF 70%, #D6E4FF 100%)", display: "grid", placeItems: "center", opacity: intro, transform: `scale(${(0.8 + intro * 0.2) * (1 + Math.sin(global / 22) * 0.015)})`, boxShadow: `0 0 ${60 + Math.sin(global / 18) * 20}px rgba(46,116,255,0.65)` }}>
      <Img src={staticFile("brand-mark.svg")} style={{ width: 112 }} />
    </div>
    {labels.map((label, i) => {
      const a = anchors[i];
      const p = reveal(i);
      return <div key={i} style={{ position: "absolute", left: a.x, top: a.y, transform: `translate(-50%, -50%) scale(${0.82 + p * 0.18})`, opacity: p }}>
        <div data-film-text="label" style={{ display: "flex", alignItems: "center", gap: 18, padding: "16px 30px 16px 16px", borderRadius: 999, background: "rgba(255,255,255,0.97)", boxShadow: "0 24px 60px rgba(3,6,15,0.45), 0 0 0 6px rgba(46,116,255,0.18)", whiteSpace: "nowrap" }}>
          <div style={{ width: 56, height: 56, borderRadius: 28, background: `linear-gradient(145deg, ${K.blue}, ${K.navy})`, color: "#FFFFFF", display: "grid", placeItems: "center" }}>{iconFor(label)}</div>
          <span style={{ fontFamily: body, fontWeight: 600, fontSize: portrait ? 34 : 32, color: K.ink }}>{label}</span>
        </div>
      </div>;
    })}
    <div style={{ position: "absolute", left: 0, right: 0, top: hub.y + 128, textAlign: "center", fontFamily: display, fontSize: 18, letterSpacing: 3, color: "rgba(220,231,255,0.7)", opacity: intro }}>{productName().toUpperCase()}</div>
  </AbsoluteFill>;
}
