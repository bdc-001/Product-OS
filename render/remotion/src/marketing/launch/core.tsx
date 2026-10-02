import React, { createContext, useContext } from "react";
import { AbsoluteFill, Easing, interpolate } from "remotion";
import type { Scene } from "../Film";
import type { Screen } from "../kit/ProductUI";

export const FPS = 30;
export const OVERLAP = 12;
export const CLICK_OFFSET = 8;
export const K = {
  blue: "#1A62F2", navy: "#0A2E7A", ink: "#0A0F1F", dark: "#151515", pale: "#EEF4FF", line: "#AFCAFB",
  inverse: "#F4F7FF", muted: "#6B7A90", rule: "#E3EBF8", sky: "#7FA8FF",
};
export const display = "'Helvetica Neue', Helvetica, Arial, sans-serif";
export const body = "Inter, 'Helvetica Neue', Arial, sans-serif";
export const ease = Easing.bezier(0.16, 1, 0.3, 1);

export type Field = "light" | "brand" | "dark" | "stage";
export type LaunchTransition = "wipe" | "slide" | "push" | "fade";
export type Background = "cloud" | "horizon" | "grid" | "stage" | "porcelain" | "tint" | "brand" | "beam" | "deep" | "midnight" | "ink" | "rings";
export type ScaleLayout = "wall" | "dots" | "timeline" | "dialer" | "thread" | "lanes" | "phone";
export type LaunchCraft = { luma: "light" | "dark"; treatment: string; transition: LaunchTransition; plate?: null; field: Field; bg?: Background; layout?: ScaleLayout };
export type LaunchScene = Omit<Scene, "visual"> & {
  visual?: Scene["visual"] | "kinetic" | "ui" | "orbit" | "volume" | "endcard" | "messages";
  screen?: Screen; endsCall?: boolean; hangupFrame?: number; clickAt?: number; tag?: string;
};

type LaunchValue = { audioFrom: number; portrait: boolean; title: string };
export const LaunchCtx = createContext<LaunchValue>({ audioFrom: 3, portrait: false, title: "" });
export const useLaunch = () => useContext(LaunchCtx);

export const progress = (frame: number, start = 0, duration = 14) =>
  interpolate(frame, [start, start + duration], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
export const bump = (frame: number, at: number, duration = 6) =>
  frame < at || frame > at + duration ? 0 : Math.sin(((frame - at) / duration) * Math.PI);
export function seeded(i: number) {
  const x = Math.sin(i * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x);
}
export const norm = (word: string) => word.toLowerCase().normalize("NFC").replace(/[^\p{L}\p{N}]/gu, "");

/** Scene-local frame at which a provider timestamp (seconds on the narration clock) is heard. */
export const heard = (scene: LaunchScene, seconds: number, audioFrom: number) => audioFrom + Math.round(seconds * FPS) - scene.from;

/** Reveal frame for each display word: the spoken word it quotes, or a short stagger after the last one. */
export function wordCues(scene: LaunchScene, text: string, audioFrom: number, lead = 3) {
  const spoken = scene.wordTimings || [];
  const words = text.split(/\s+/).filter(Boolean);
  let cursor = 0;
  let last = 2;
  return words.map((word, i) => {
    const key = norm(word);
    let hit = -1;
    for (let j = cursor; j < spoken.length && key; j++) {
      if (norm(spoken[j].word) === key) { hit = j; break; }
    }
    if (hit >= 0) {
      cursor = hit + 1;
      last = Math.max(i ? last + 1 : 2, heard(scene, spoken[hit].start, audioFrom) - lead);
    } else {
      last = i ? last + 3 : 4;
    }
    return { word, at: last };
  });
}

export function emphasisMask(text: string, emphasis?: string) {
  const words = text.split(/\s+/).filter(Boolean);
  if (!emphasis) return words.map(() => false);
  const start = text.indexOf(emphasis);
  if (start < 0) return words.map(() => false);
  let offset = 0;
  return words.map(word => {
    const at = text.indexOf(word, offset);
    offset = at + word.length;
    return at >= start && at < start + emphasis.length;
  });
}

function Blob({ x, y, size, color, blur = 70, opacity = 1 }: { x: number; y: number; size: number; color: string; blur?: number; opacity?: number }) {
  return <div style={{
    position: "absolute", left: `${x}%`, top: `${y}%`, width: size, height: size, borderRadius: "50%",
    transform: "translate(-50%, -50%)", background: `radial-gradient(circle, ${color} 0%, transparent 68%)`,
    filter: `blur(${blur}px)`, opacity,
  }} />;
}

function Grain({ opacity = 0.05 }: { opacity?: number }) {
  return <AbsoluteFill style={{
    opacity, mixBlendMode: "multiply", pointerEvents: "none",
    backgroundImage: "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='96' height='96'><filter id='n'><feTurbulence baseFrequency='.85' numOctaves='2' stitchTiles='stitch'/></filter><rect width='100%' height='100%' filter='url(%23n)' opacity='.6'/></svg>\")",
  }} />;
}

/** Glass pebble from the reference white scenes: a translucent blue form that breathes in the corner. */
function Pebble({ global, portrait }: { global: number; portrait: boolean }) {
  const t = global / FPS;
  return <div style={{
    position: "absolute", right: portrait ? -220 : -160, bottom: portrait ? -180 : -210, width: portrait ? 620 : 700, height: portrait ? 520 : 560,
    borderRadius: "46% 54% 42% 58% / 56% 44% 56% 44%", transform: `rotate(${-18 + Math.sin(t * 0.35) * 6}deg) scale(${1 + Math.sin(t * 0.5) * 0.02})`,
    background: "linear-gradient(140deg, rgba(255,255,255,0.95) 0%, rgba(196,216,255,0.75) 34%, rgba(84,140,255,0.62) 72%, rgba(26,98,242,0.72) 100%)",
    boxShadow: "inset 18px 24px 60px rgba(255,255,255,0.85), inset -30px -40px 80px rgba(10,46,122,0.25), 0 50px 140px rgba(26,98,242,0.32)",
  }} />;
}

/** Thin Swiss grid that drifts a few pixels a second and fades out toward the edges. */
function GridLines({ t, color, step = 120, opacity = 0.8, at = "50% 50%" }: { t: number; color: string; step?: number; opacity?: number; at?: string }) {
  const mask = `radial-gradient(ellipse at ${at}, black 0%, transparent 70%)`;
  return <AbsoluteFill style={{
    opacity, backgroundSize: `${step}px ${step}px`, backgroundPosition: `${(t * 4) % step}px ${(t * 2) % step}px`,
    backgroundImage: `linear-gradient(${color} 1px, transparent 1px), linear-gradient(90deg, ${color} 1px, transparent 1px)`,
    maskImage: mask, WebkitMaskImage: mask,
  }} />;
}

/** Concentric hairline rings that expand slowly from below the frame: an orbit, not a pulse. */
function Rings({ t, portrait }: { t: number; portrait: boolean }) {
  const gap = portrait ? 200 : 230;
  const drift = (t * 12) % gap;
  return <AbsoluteFill style={{ overflow: "hidden" }}>
    {Array.from({ length: 8 }, (_, i) => {
      const r = 260 + i * gap + drift;
      return <div key={i} style={{
        position: "absolute", left: "50%", top: portrait ? "104%" : "112%", width: r * 2, height: r * 2, marginLeft: -r, marginTop: -r,
        borderRadius: "50%", border: "1.5px solid rgba(125,168,248,1)", opacity: 0.2 * Math.max(0, 1 - r / (gap * 8.5)),
      }} />;
    })}
  </AbsoluteFill>;
}

/** One soft diagonal beam crossing the field over ~24 seconds: the brand's signal-flow sweep. */
function Beam({ t, portrait }: { t: number; portrait: boolean }) {
  const span = portrait ? 2200 : 3000;
  const x = ((t * 110) % span) - span * 0.35;
  return <div style={{
    position: "absolute", top: "-50%", left: x, width: portrait ? 520 : 680, height: "200%", transform: "rotate(24deg)",
    background: "linear-gradient(90deg, transparent 0%, rgba(125,168,248,0.26) 38%, rgba(209,225,253,0.2) 52%, transparent 100%)", filter: "blur(30px)",
  }} />;
}

/** One hairline signal path low in the frame, below the content, with a single bright pulse travelling along it. */
function Signals({ t, portrait }: { t: number; portrait: boolean }) {
  const rows = portrait ? [90] : [88];
  const active = Math.floor(t / 4) % rows.length;
  const run = (t % 4) / 4;
  return <AbsoluteFill>
    {rows.map((y, i) => <div key={y} style={{ position: "absolute", left: 0, right: 0, top: `${y}%`, height: 1, background: "linear-gradient(90deg, transparent, rgba(74,132,245,0.18) 30%, rgba(74,132,245,0.18) 70%, transparent)" }}>
      {i === active && <div style={{ position: "absolute", top: -1.5, height: 4, width: 220, left: `${-15 + run * 130}%`, borderRadius: 2, background: "linear-gradient(90deg, transparent, rgba(175,202,251,0.95), transparent)", boxShadow: "0 0 18px 4px rgba(26,98,242,0.55)" }} />}
    </div>)}
  </AbsoluteFill>;
}

const DEFAULT_BG: Record<Field, Background> = { light: "cloud", stage: "stage", brand: "brand", dark: "midnight" };

/** Every field is a moving gradient world; nothing is ever a flat fill. Ambient motion uses the film clock.
 *  Variants stay inside the brand ramp (#0A2E7A to #EEF4FF), the neutrals and the two approved gradients. */
export function FieldLayer({ field, bg, global, portrait }: { field: Field; bg?: Background; global: number; portrait: boolean }) {
  const t = global / FPS;
  const look = bg ?? DEFAULT_BG[field];
  if (look === "horizon") {
    return <AbsoluteFill style={{ overflow: "hidden", background: "linear-gradient(180deg, #FFFFFF 0%, #FFFFFF 44%, #EEF4FF 62%, #AFCAFB 84%, #4A84F5 100%)" }}>
      <Blob x={50 + Math.sin(t * 0.18) * 14} y={112} size={portrait ? 1500 : 1900} color="rgba(26,98,242,0.85)" blur={110} />
      <Blob x={8} y={-8} size={portrait ? 700 : 820} color="rgba(209,225,253,0.9)" blur={90} />
      <div style={{ position: "absolute", left: 0, right: 0, top: portrait ? "78%" : "74%", height: 2, background: `linear-gradient(90deg, transparent ${(t * 6) % 100 - 30}%, rgba(255,255,255,0.9) ${(t * 6) % 100}%, transparent ${(t * 6) % 100 + 30}%)` }} />
      <Grain opacity={0.03} />
    </AbsoluteFill>;
  }
  if (look === "grid") {
    return <AbsoluteFill style={{ overflow: "hidden", background: "linear-gradient(160deg, #FFFFFF 0%, #FFFFFF 40%, #EEF4FF 100%)" }}>
      <GridLines t={t} color="#D1E1FD" at="60% 55%" />
      <Blob x={-6 + Math.sin(t * 0.2) * 3} y={-10 + Math.cos(t * 0.22) * 3} size={portrait ? 1300 : 1500} color="rgba(26,98,242,0.85)" blur={100} />
      <Blob x={104} y={104} size={portrait ? 900 : 1000} color="rgba(125,168,248,0.75)" blur={95} />
      <Grain opacity={0.03} />
    </AbsoluteFill>;
  }
  if (look === "porcelain") {
    return <AbsoluteFill style={{ overflow: "hidden", background: "linear-gradient(135deg, #FFFFFF 0%, #EEF4FF 58%, #D1E1FD 100%)" }}>
      <Blob x={100 + Math.sin(t * 0.2) * 3} y={104} size={portrait ? 1150 : 1300} color="rgba(74,132,245,0.7)" blur={100} />
      <Blob x={-4} y={-6} size={portrait ? 800 : 900} color="rgba(175,202,251,0.7)" blur={90} />
      <Grain opacity={0.03} />
    </AbsoluteFill>;
  }
  if (look === "tint") {
    return <AbsoluteFill style={{ overflow: "hidden", background: "linear-gradient(180deg, #EEF4FF 0%, #D6E4FF 100%)" }}>
      <Blob x={-8} y={50 + Math.sin(t * 0.2) * 12} size={portrait ? 1200 : 1400} color="rgba(26,98,242,0.6)" blur={110} />
      <Blob x={96} y={-6} size={portrait ? 700 : 820} color="rgba(255,255,255,0.9)" blur={80} />
      <Grain opacity={0.03} />
    </AbsoluteFill>;
  }
  if (look === "beam") {
    return <AbsoluteFill style={{ overflow: "hidden", background: "linear-gradient(135deg, #1658E1 0%, #1A62F2 50%, #144ECF 100%)" }}>
      <Beam t={t} portrait={portrait} />
      <Blob x={92} y={100} size={portrait ? 1000 : 1200} color="rgba(10,46,122,0.7)" blur={100} />
      <Grain opacity={0.05} />
    </AbsoluteFill>;
  }
  if (look === "deep") {
    return <AbsoluteFill style={{ overflow: "hidden", background: "linear-gradient(180deg, #1658E1 0%, #103EA6 55%, #0A2E7A 100%)" }}>
      <Blob x={12 + Math.sin(t * 0.25) * 5} y={6} size={portrait ? 1100 : 1300} color="rgba(74,132,245,0.75)" blur={100} />
      <Blob x={90} y={98} size={portrait ? 900 : 1000} color="rgba(26,98,242,0.55)" blur={100} />
      <Grain opacity={0.06} />
    </AbsoluteFill>;
  }
  if (look === "ink") {
    return <AbsoluteFill style={{ overflow: "hidden", background: "radial-gradient(115% 90% at 86% 108%, #1A62F2 0%, #151515 64%, #0F0F0F 100%)" }}>
      <Blob x={86 + Math.sin(t * 0.2) * 4} y={104} size={portrait ? 1200 : 1400} color="rgba(26,98,242,0.6)" blur={110} />
      <Signals t={t} portrait={portrait} />
      <Grain opacity={0.05} />
    </AbsoluteFill>;
  }
  if (look === "rings") {
    return <AbsoluteFill style={{ overflow: "hidden", background: "radial-gradient(130% 100% at 50% 112%, #1A62F2 0%, #0A2E7A 40%, #151515 88%)" }}>
      <Rings t={t} portrait={portrait} />
      <Blob x={50} y={110} size={portrait ? 1100 : 1300} color="rgba(26,98,242,0.55)" blur={110} />
      <Grain opacity={0.05} />
    </AbsoluteFill>;
  }
  if (look === "brand") {
    return <AbsoluteFill style={{ overflow: "hidden", background: "linear-gradient(135deg, #3B7CFF 0%, #1A62F2 44%, #0C45C4 100%)" }}>
      <Blob x={18 + Math.sin(t * 0.3) * 6} y={8 + Math.cos(t * 0.25) * 5} size={portrait ? 1200 : 1400} color="rgba(140,185,255,0.75)" blur={90} />
      <Blob x={88 + Math.cos(t * 0.28) * 4} y={96} size={1000} color="rgba(6,34,120,0.7)" blur={100} />
      <Blob x={62 + Math.sin(t * 0.4) * 8} y={60} size={520} color="rgba(255,255,255,0.18)" blur={70} />
      <Grain opacity={0.06} />
    </AbsoluteFill>;
  }
  if (look === "midnight") {
    return <AbsoluteFill style={{ overflow: "hidden", background: "radial-gradient(130% 95% at 50% 118%, #2166F5 0%, #0C3395 30%, #06123A 60%, #03060F 100%)" }}>
      <Blob x={50 + Math.sin(t * 0.22) * 10} y={102} size={portrait ? 1300 : 1500} color="rgba(46,116,255,0.8)" blur={110} />
      <Blob x={12 + Math.cos(t * 0.3) * 5} y={14} size={700} color="rgba(26,98,242,0.35)" blur={90} />
      <AbsoluteFill style={{
        opacity: 0.22, backgroundSize: "56px 56px", backgroundPosition: `${(t * 6) % 56}px 0px`,
        backgroundImage: "radial-gradient(circle, rgba(175,202,251,0.55) 1.2px, transparent 1.6px)",
        maskImage: "radial-gradient(ellipse at 50% 60%, black 0%, transparent 72%)", WebkitMaskImage: "radial-gradient(ellipse at 50% 60%, black 0%, transparent 72%)",
      }} />
      <Grain opacity={0.08} />
    </AbsoluteFill>;
  }
  if (look === "stage") {
    return <AbsoluteFill style={{ overflow: "hidden", background: "linear-gradient(180deg, #F7FAFF 0%, #EEF4FF 52%, #E1ECFF 100%)" }}>
      <Blob x={-2 + Math.sin(t * 0.2) * 3} y={96} size={portrait ? 1000 : 1100} color="rgba(26,98,242,0.55)" blur={100} />
      <Blob x={100} y={0} size={800} color="rgba(127,168,255,0.45)" blur={90} />
      <Grain opacity={0.035} />
    </AbsoluteFill>;
  }
  return <AbsoluteFill style={{ overflow: "hidden", background: "linear-gradient(180deg, #FFFFFF 0%, #F6F9FF 60%, #EDF3FF 100%)" }}>
    <Blob x={-4 + Math.sin(t * 0.24) * 4} y={100 + Math.cos(t * 0.2) * 3} size={portrait ? 1100 : 1250} color="rgba(26,98,242,0.9)" blur={95} />
    <Blob x={104 + Math.cos(t * 0.3) * 3} y={-6} size={portrait ? 800 : 900} color="rgba(127,168,255,0.65)" blur={90} />
    <Pebble global={global} portrait={portrait} />
    <Grain opacity={0.035} />
  </AbsoluteFill>;
}

export const ink = (field: Field) => field === "light" || field === "stage" ? K.ink : "#FFFFFF";
