import React from "react";
import { AbsoluteFill } from "remotion";
import { emphasisMask, useLaunch, wordCues, type LaunchScene } from "../core";
import { A, auraSans, auraSerif, BEAT, glide, rise } from "./tokens";

export type Cue = { word: string; at: number };

/** Reveal frames for a phrase, clamped so the last word always lands before the cut. A headline the narrator only
 *  reaches late in the line is a title: it types in on the cut instead of leaving the frame empty. */
export function phraseCues(scene: LaunchScene, text: string, audioFrom: number): Cue[] {
  const cues = wordCues(scene, text, audioFrom);
  const title = cues.length > 0 && cues[0].at > 24;
  return cues.map((cue, i) => ({ ...cue, at: Math.min(title ? 4 + i * 4 : cue.at, Math.max(2, scene.frames - 18)) }));
}

export function auraSize(count: number, portrait: boolean) {
  if (portrait) return count <= 3 ? 116 : count <= 5 ? 98 : 82;
  return count <= 3 ? 138 : count <= 5 ? 114 : 94;
}

/** Cross-blur out: the phrase softens and lifts away as the next one sharpens through it. */
export const dissolveStyle = (p: number): React.CSSProperties => p <= 0 ? {} : {
  opacity: 1 - p, filter: `blur(${(p * 18).toFixed(2)}px)`, transform: `scale(${1 + p * 0.04})`,
};

/** One short phrase, centred and light. Each character blurs, fades and rises in on the word's spoken cue;
 *  emphasised words switch to the serif accent instead of a pill. */
export function BlurPhrase({ scene, frame, text, cues, mask, size, align = "center", maxWidth, weight = 300, color = A.ink, accent = A.blue, tag = "headline", serif = false, style }: {
  scene: LaunchScene; frame: number; text?: string; cues?: Cue[]; mask?: boolean[]; size: number; align?: "center" | "left";
  maxWidth?: number; weight?: number; color?: string; accent?: string; tag?: string; serif?: boolean; style?: React.CSSProperties;
}) {
  const { audioFrom, portrait } = useLaunch();
  const phrase = text ?? scene.headline;
  const words = cues ?? phraseCues(scene, phrase, audioFrom);
  const lit = mask ?? emphasisMask(phrase, scene.emphasis);
  return <div data-film-text={tag} style={{
    fontFamily: serif ? auraSerif : auraSans, fontSize: size, fontWeight: serif ? 400 : weight, lineHeight: 1.12, letterSpacing: serif ? "-0.01em" : "-0.03em",
    color, textAlign: align, maxWidth: maxWidth ?? (portrait ? 920 : 1500), textWrap: "balance", fontStyle: serif ? "italic" : "normal", ...style,
  }}>
    {words.map(({ word, at }, i) => {
      const accentWord = lit[i] && !serif;
      return <React.Fragment key={i}>
        <span style={{
          display: "inline-block", whiteSpace: "nowrap",
          ...(accentWord ? { fontFamily: auraSerif, fontStyle: "italic", fontWeight: 400, fontSize: "1.08em", letterSpacing: "-0.01em", color: accent } : {}),
        }}>
          {Array.from(word).map((ch, c) => {
            const p = rise(frame, at + c * BEAT.char, BEAT.charIn);
            return <span key={c} style={{
              display: "inline-block", opacity: p, transform: p < 1 ? `translateY(${((1 - p) * 0.26).toFixed(3)}em)` : undefined,
              filter: p < 1 ? `blur(${((1 - p) * size * 0.11).toFixed(2)}px)` : undefined,
            }}>{ch}</span>;
          })}
        </span>{i < words.length - 1 ? " " : ""}
      </React.Fragment>;
    })}
  </div>;
}

/** Splits a headline into the phrases a viewer reads one at a time: at clause punctuation, never leaving a
 *  one-word phrase. */
export function phraseGroups(words: string[]): number[][] {
  if (words.length < 5) return [words.map((_, i) => i)];
  const groups: number[][] = [[]];
  words.forEach((word, i) => {
    groups[groups.length - 1].push(i);
    const rest = words.length - i - 1;
    if (/[,.;:!?]$/.test(word) && groups[groups.length - 1].length >= 2 && rest >= 2 && groups.length < 3) groups.push([]);
  });
  return groups.filter(g => g.length);
}

/** The headline as consecutive phrases in one place: each phrase blurs in on its words and the next
 *  dissolves through it (PhraseDissolve). Short headlines are one phrase. */
export function AuraType({ scene, frame, text, size, align = "center", maxWidth, weight = 300, color = A.ink }: {
  scene: LaunchScene; frame: number; text?: string; size?: number; align?: "center" | "left"; maxWidth?: number; weight?: number; color?: string;
}) {
  const { audioFrom, portrait } = useLaunch();
  const phrase = text ?? scene.headline;
  const cues = phraseCues(scene, phrase, audioFrom);
  const mask = emphasisMask(phrase, scene.emphasis);
  const groups = phraseGroups(cues.map(c => c.word));
  if (groups.length === 1) {
    return <BlurPhrase scene={scene} frame={frame} text={phrase} cues={cues} mask={mask} size={size ?? auraSize(cues.length, portrait)} align={align} maxWidth={maxWidth} weight={weight} color={color} />;
  }
  return <PhraseDissolve frame={frame} starts={groups.map(g => cues[g[0]].at)} align={align}>
    {groups.map((g, k) => <BlurPhrase key={k} scene={scene} frame={frame} text={g.map(i => cues[i].word).join(" ")} cues={g.map(i => cues[i])} mask={g.map(i => mask[i])}
      size={size ?? auraSize(Math.max(...groups.map(x => x.length)), portrait)} align={align} maxWidth={maxWidth} weight={weight} color={color} />)}
  </PhraseDissolve>;
}

/** Consecutive phrases stacked in one cell: each dissolves as the next begins, the last one stays. */
export function PhraseDissolve({ frame, starts, align = "center", children }: { frame: number; starts: number[]; align?: "center" | "left"; children: React.ReactNode[] }) {
  return <div style={{ display: "grid", justifyItems: align === "center" ? "center" : "start", alignItems: "center" }}>
    {children.map((child, k) => {
      const next = starts[k + 1];
      const out = next === undefined ? 0 : glide(frame, next - 4, BEAT.dissolve);
      return <div key={k} style={{ gridArea: "1 / 1", ...dissolveStyle(out), visibility: out >= 1 ? "hidden" : "visible" }}>{child}</div>;
    })}
  </div>;
}

export type CamKey = { at: number; x: number; y: number; zoom: number };

/** Where the camera looks: it holds each key, travelling to the next over `travel` frames ending on its cue. */
export function camAt(frame: number, keys: CamKey[], travel = 18) {
  let { x, y, zoom } = keys[0];
  for (const key of keys.slice(1)) {
    const p = glide(frame, key.at - travel, travel);
    x += (key.x - x) * p; y += (key.y - y) * p; zoom += (key.zoom - zoom) * p;
  }
  return { x, y, zoom };
}

/** A canvas larger than the frame, panned and zoomed so canvas point (x, y) sits at the frame centre. */
export function Camera({ view, children }: { view: { x: number; y: number; zoom: number }; children: React.ReactNode }) {
  const { portrait } = useLaunch();
  return <AbsoluteFill style={{ overflow: "hidden" }}>
    <div style={{ position: "absolute", left: portrait ? 540 : 960, top: portrait ? 960 : 540, transformOrigin: "0 0", transform: `scale(${view.zoom}) translate(${-view.x}px, ${-view.y}px)` }}>
      {children}
    </div>
  </AbsoluteFill>;
}

export const CARD_SHADOW = "0 1px 2px rgba(22,26,35,0.04), 0 14px 34px rgba(26,98,242,0.08), 0 46px 110px rgba(26,98,242,0.16)";

/** An isolated surface: soft layered shadow, a slight 3D tilt and an idle drift. `enter` blurs it in. */
export function FloatCard({ children, width, height, enter = 1, global, seed = 0, radius = 28, tilt = 1, style, inner }: {
  children: React.ReactNode; width: number; height: number; enter?: number; global: number; seed?: number; radius?: number; tilt?: number;
  style?: React.CSSProperties; inner?: React.CSSProperties;
}) {
  const drift = Math.sin((global + seed * 37) / 24) * 10;
  const rx = Math.sin((global + seed * 11) / 34) * 2 * tilt + (1 - enter) * 12;
  const ry = Math.cos((global + seed * 5) / 40) * 2.8 * tilt;
  return <div style={{ width, height, perspective: 2200, ...style }}>
    <div style={{
      position: "relative", width, height, borderRadius: radius, background: A.card, boxShadow: CARD_SHADOW, border: "1px solid rgba(214,228,255,0.9)",
      overflow: "hidden", opacity: Math.min(1, enter * 1.6), filter: enter < 1 ? `blur(${((1 - enter) * 16).toFixed(2)}px)` : undefined,
      transform: `translateY(${(1 - enter) * 50 + drift}px) rotateX(${rx}deg) rotateY(${ry}deg) scale(${0.92 + 0.08 * enter})`, ...inner,
    }}>{children}</div>
  </div>;
}

export type Stop = { x: number; y: number; at: number; click?: boolean };

/** Cursor position on an arc between stops: it glides into each stop and arrives on `at`. */
export function cursorAt(frame: number, stops: Stop[], origin: { x: number; y: number }) {
  let from = origin;
  for (let i = 0; i < stops.length; i++) {
    const stop = stops[i];
    const gap = i ? stop.at - stops[i - 1].at : 24;
    const travel = Math.max(7, Math.min(14, gap - 4));
    const p = glide(frame, stop.at - travel, travel);
    if (p < 1) {
      const mx = (from.x + stop.x) / 2, my = (from.y + stop.y) / 2;
      const dx = stop.x - from.x, dy = stop.y - from.y;
      const cx = mx - dy * 0.18, cy = my + dx * 0.18;
      const q = 1 - p;
      return { x: q * q * from.x + 2 * q * p * cx + p * p * stop.x, y: q * q * from.y + 2 * q * p * cy + p * p * stop.y, moving: p > 0 };
    }
    from = stop;
  }
  return { ...from, moving: false };
}

/** The macOS pointer: an arced glide, a hover glow while it rests, a press and a soft ripple on each click. */
export function AuraCursor({ frame, stops, origin, enterAt, leaveAt, scale = 1 }: {
  frame: number; stops: Stop[]; origin: { x: number; y: number }; enterAt?: number; leaveAt?: number; scale?: number;
}) {
  if (!stops.length) return null;
  const pos = cursorAt(frame, stops, origin);
  const start = enterAt ?? stops[0].at - 18;
  const visible = rise(frame, start, 6) * (leaveAt === undefined ? 1 : 1 - rise(frame, leaveAt, 8));
  if (visible <= 0) return null;
  const clicks = stops.filter(s => s.click).map(s => s.at + 3);
  const down = clicks.reduce((v, c) => Math.max(v, frame >= c && frame < c + 6 ? Math.sin(((frame - c) / 6) * Math.PI) : 0), 0);
  const resting = stops.find((s, i) => frame >= s.at - 2 && (i === stops.length - 1 || frame < stops[i + 1].at - 14));
  const hover = resting ? rise(frame, resting.at - 3, 6) : 0;
  return <>
    {clicks.map((c, i) => {
      const r = rise(frame, c, 14);
      const stop = stops.filter(s => s.click)[i];
      if (frame < c || r >= 1) return null;
      return <div key={i} style={{ position: "absolute", left: stop.x - 46 * scale, top: stop.y - 46 * scale, width: 92 * scale, height: 92 * scale, borderRadius: "50%",
        background: "radial-gradient(circle, rgba(127,168,255,0.32) 0%, rgba(127,168,255,0) 70%)", border: `2px solid rgba(26,98,242,${0.45 * (1 - r)})`,
        transform: `scale(${0.25 + r * 0.95})`, opacity: 1 - r * 0.6, pointerEvents: "none" }} />;
    })}
    <div style={{ position: "absolute", left: pos.x - 32 * scale, top: pos.y - 32 * scale, width: 64 * scale, height: 64 * scale, borderRadius: "50%",
      background: "radial-gradient(circle, rgba(127,168,255,0.38) 0%, rgba(127,168,255,0) 70%)", opacity: hover * visible, pointerEvents: "none" }} />
    <svg width={34 * scale} height={40 * scale} viewBox="0 0 34 40" style={{ position: "absolute", left: pos.x - 4 * scale, top: pos.y - 3 * scale, opacity: visible,
      transform: `scale(${1 - down * 0.16})`, transformOrigin: "4px 3px", filter: "drop-shadow(0 8px 14px rgba(22,26,35,0.28))", pointerEvents: "none", overflow: "visible" }}>
      <path d="M4 3 L4 32 L11.5 25 L16.5 36.5 L21.5 34.3 L16.6 23 L27 23 Z" fill="#111318" stroke="#FFFFFF" strokeWidth="2.2" strokeLinejoin="round" />
    </svg>
  </>;
}

export type Morph = "blur" | "zoom" | "dot" | "fill";
export const MORPHS = new Set<string>(["blur", "zoom", "dot", "fill"]);

/** The incoming block: it sharpens through the last one, emerges from the centre, or grows out of a dot. */
export function morphIn(kind: string, p: number): React.CSSProperties {
  if (p >= 1) return {};
  if (kind === "zoom") return { opacity: p, transform: `scale(${0.7 + 0.3 * p})`, filter: `blur(${((1 - p) * 18).toFixed(2)}px)` };
  if (kind === "dot") return { clipPath: `circle(${(p * 72).toFixed(2)}% at 50% 50%)` };
  if (kind === "fill") return { clipPath: `circle(${(p * 74).toFixed(2)}% at 50% 56%)` };
  return { opacity: p, filter: `blur(${((1 - p) * 26).toFixed(2)}px)` };
}

/** The outgoing block under the next one: it blurs away, zooms past the camera, or collapses toward a dot. */
export function morphOut(kind: string, q: number): React.CSSProperties {
  if (q <= 0) return {};
  if (kind === "zoom") return { transform: `scale(${1 + q * 1.1})`, filter: `blur(${(q * 18).toFixed(2)}px)`, opacity: 1 - q * 0.85 };
  if (kind === "dot") return { transform: `scale(${1 - q * 0.6})`, filter: `blur(${(q * 10).toFixed(2)}px)`, borderRadius: `${q * 50}%` };
  if (kind === "fill") return {};
  return { filter: `blur(${(q * 22).toFixed(2)}px)` };
}
