import React, { useId } from "react";
import { A, auraSans, TINTS } from "./tokens";

/** Every object is drawn in SVG or CSS and is deterministic on the film clock; nothing is a bitmap. */
const useSvgId = () => useId().replace(/[^a-zA-Z0-9_-]/g, "");
const mix = (a: string, b: string, t: number) => {
  const pa = [1, 3, 5].map(i => parseInt(a.slice(i, i + 2), 16)), pb = [1, 3, 5].map(i => parseInt(b.slice(i, i + 2), 16));
  return `rgb(${pa.map((v, i) => Math.round(v + (pb[i] - v) * t)).join(",")})`;
};

/** A glossy capability pill: a tinted icon bubble and a light label. `selected` floods it with brand blue. */
export function GlossPill({ icon, label, scale = 1, tint = 0, selected = 0, hover = 0 }: {
  icon?: React.ReactNode; label: string; scale?: number; tint?: number; selected?: number; hover?: number;
}) {
  const [light, deep] = TINTS[tint % TINTS.length];
  const h = 88 * scale;
  return <div style={{
    position: "relative", display: "inline-flex", alignItems: "center", gap: 18 * scale, height: h, padding: `0 ${34 * scale}px 0 ${14 * scale}px`, borderRadius: h,
    background: "linear-gradient(180deg, #FFFFFF 0%, #F4F7FE 100%)", border: "1px solid rgba(255,255,255,0.95)", whiteSpace: "nowrap",
    boxShadow: `inset 0 2px 0 rgba(255,255,255,1), inset 0 -6px 14px rgba(167,195,255,0.22), 0 ${18 + hover * 8}px ${44 + hover * 16}px rgba(26,98,242,${0.14 + hover * 0.06}), 0 2px 6px rgba(22,26,35,0.05)`,
    transform: `translateY(${-hover * 4}px) scale(${1 + hover * 0.02 - (selected > 0 && selected < 0.25 ? 0.03 : 0)})`,
  }}>
    <div style={{ position: "absolute", inset: 0, borderRadius: h, background: `linear-gradient(135deg, ${A.mark} 0%, ${A.blue} 60%, #144ECF 100%)`, opacity: selected,
      boxShadow: "inset 0 2px 0 rgba(255,255,255,0.35)" }} />
    <div style={{ position: "relative", width: 60 * scale, height: 60 * scale, borderRadius: "50%", display: "grid", placeItems: "center", color: "#FFFFFF",
      background: selected > 0.5 ? "rgba(255,255,255,0.22)" : `radial-gradient(circle at 32% 28%, #FFFFFF 0%, ${light} 30%, ${deep} 100%)`,
      boxShadow: "inset 0 1.5px 0 rgba(255,255,255,0.8), 0 8px 18px rgba(26,98,242,0.22)" }}>{icon}</div>
    <span data-film-text="label" style={{ position: "relative", fontFamily: auraSans, fontSize: 32 * scale, fontWeight: 400, letterSpacing: "-0.01em",
      color: mix(A.ink, "#FFFFFF", selected) }}>{label}</span>
  </div>;
}

export type GemKind = "diamond" | "star" | "orb" | "drop" | "cube";
export const GEMS: GemKind[] = ["diamond", "star", "orb", "drop", "cube"];

/** A faceted brand-tinted gem with a specular highlight. */
export function Gem({ kind, size, tint = 0, spin = 0 }: { kind: GemKind; size: number; tint?: number; spin?: number }) {
  const id = useSvgId();
  const [light, deep] = kind === "star" && tint % 7 === 6 ? ["#FFE3A3", A.amber] : TINTS[tint % TINTS.length];
  const defs = <defs>
    <linearGradient id={`${id}l`} x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#FFFFFF" /><stop offset="0.45" stopColor={light} /><stop offset="1" stopColor={deep} /></linearGradient>
    <linearGradient id={`${id}d`} x1="1" y1="0" x2="0" y2="1"><stop offset="0" stopColor={light} /><stop offset="1" stopColor={deep} /></linearGradient>
    <radialGradient id={`${id}r`} cx="0.34" cy="0.3" r="0.75"><stop offset="0" stopColor="#FFFFFF" /><stop offset="0.35" stopColor={light} /><stop offset="1" stopColor={deep} /></radialGradient>
    <radialGradient id={`${id}s`} cx="0.5" cy="0.5" r="0.5"><stop offset="0" stopColor="#FFFFFF" stopOpacity="0.95" /><stop offset="1" stopColor="#FFFFFF" stopOpacity="0" /></radialGradient>
  </defs>;
  let body: React.ReactNode;
  if (kind === "diamond") {
    body = <>
      <polygon points="18,38 34,20 66,20 82,38" fill={`url(#${id}l)`} />
      <polygon points="34,20 50,38 66,20" fill="#FFFFFF" opacity="0.55" />
      <polygon points="18,38 50,86 50,38" fill={`url(#${id}d)`} />
      <polygon points="82,38 50,86 50,38" fill={deep} opacity="0.85" />
      <polygon points="18,38 50,38 34,20" fill={light} opacity="0.8" />
      <polygon points="36,38 50,86 50,38" fill="#FFFFFF" opacity="0.18" />
    </>;
  } else if (kind === "star") {
    body = <path d="M50 4 C54 36 64 46 96 50 C64 54 54 64 50 96 C46 64 36 54 4 50 C36 46 46 36 50 4Z" fill={`url(#${id}r)`} />;
  } else if (kind === "orb") {
    body = <circle cx="50" cy="50" r="40" fill={`url(#${id}r)`} />;
  } else if (kind === "drop") {
    body = <rect x="30" y="8" width="40" height="84" rx="20" fill={`url(#${id}l)`} transform="rotate(32 50 50)" />;
  } else {
    body = <>
      <polygon points="50,12 86,30 50,48 14,30" fill="#FFFFFF" opacity="0.92" />
      <polygon points="14,30 50,48 50,90 14,72" fill={`url(#${id}l)`} />
      <polygon points="86,30 50,48 50,90 86,72" fill={`url(#${id}d)`} />
    </>;
  }
  return <svg width={size} height={size} viewBox="0 0 100 100" style={{ overflow: "visible", transform: `rotate(${spin}deg)`, filter: `drop-shadow(0 ${size * 0.08}px ${size * 0.14}px rgba(26,98,242,0.28))` }}>
    {defs}{body}
    <ellipse cx="38" cy="30" rx="12" ry="7" fill={`url(#${id}s)`} transform="rotate(-28 38 30)" />
  </svg>;
}

/** A flower drawn from gradient petals around a glowing centre; `open` unfurls it. */
export function Bloom({ size, petals = 7, tint = 0, open = 1, spin = 0 }: { size: number; petals?: number; tint?: number; open?: number; spin?: number }) {
  const id = useSvgId();
  const [light, deep] = TINTS[tint % TINTS.length];
  const petal = "M0 0 C -20 -18, -22 -64, 0 -86 C 22 -64, 20 -18, 0 0Z";
  return <svg width={size} height={size} viewBox="-100 -100 200 200" style={{ overflow: "visible", transform: `rotate(${spin}deg)` }}>
    <defs>
      <linearGradient id={`${id}p`} x1="0" y1="1" x2="0" y2="0"><stop offset="0" stopColor="#FFFFFF" /><stop offset="0.45" stopColor={light} /><stop offset="1" stopColor={deep} /></linearGradient>
      <linearGradient id={`${id}q`} x1="0" y1="1" x2="0" y2="0"><stop offset="0" stopColor="#FFFFFF" /><stop offset="1" stopColor={A.lilac} /></linearGradient>
      <radialGradient id={`${id}c`}><stop offset="0" stopColor="#FFFFFF" /><stop offset="0.5" stopColor={A.cyan} /><stop offset="1" stopColor={A.mark} /></radialGradient>
      <radialGradient id={`${id}g`}><stop offset="0" stopColor={A.glow} stopOpacity="0.55" /><stop offset="1" stopColor={A.glow} stopOpacity="0" /></radialGradient>
    </defs>
    <circle r="98" fill={`url(#${id}g)`} />
    {Array.from({ length: petals }, (_, i) => <path key={`b${i}`} d={petal} fill={`url(#${id}q)`} opacity="0.85"
      transform={`rotate(${(i + 0.5) * 360 / petals}) scale(${0.35 + 0.72 * open})`} />)}
    {Array.from({ length: petals }, (_, i) => <path key={i} d={petal} fill={`url(#${id}p)`} stroke="rgba(255,255,255,0.7)" strokeWidth="1.2"
      transform={`rotate(${i * 360 / petals}) scale(${0.3 + 0.62 * open})`} />)}
    <circle r={12 + 4 * open} fill={`url(#${id}c)`} />
    <ellipse cx="-4" cy="-6" rx="5" ry="3" fill="#FFFFFF" opacity="0.9" />
  </svg>;
}

/** A glass sphere with turning meridians and two tilted orbit rings. */
export function GlassSphere({ size, turn = 0 }: { size: number; turn?: number }) {
  const id = useSvgId();
  return <svg width={size} height={size} viewBox="-80 -80 160 160" style={{ overflow: "visible" }}>
    <defs>
      <radialGradient id={`${id}b`} cx="0.36" cy="0.32" r="0.8">
        <stop offset="0" stopColor="#FFFFFF" stopOpacity="0.98" /><stop offset="0.4" stopColor={A.haze} stopOpacity="0.75" /><stop offset="0.85" stopColor={A.periwinkle} stopOpacity="0.7" /><stop offset="1" stopColor={A.mark} stopOpacity="0.85" />
      </radialGradient>
      <linearGradient id={`${id}o`} x1="0" y1="0" x2="1" y2="0"><stop offset="0" stopColor={A.blue} stopOpacity="0" /><stop offset="0.5" stopColor={A.blue} stopOpacity="0.7" /><stop offset="1" stopColor={A.cyan} stopOpacity="0" /></linearGradient>
    </defs>
    <ellipse rx="74" ry="20" fill="none" stroke={`url(#${id}o)`} strokeWidth="1.6" transform={`rotate(${-18 + Math.sin(turn / 40) * 4})`} />
    <circle r="48" fill={`url(#${id}b)`} stroke="rgba(255,255,255,0.9)" strokeWidth="1.2" />
    {[0, 1, 2, 3, 4, 5].map(k => {
      const a = ((turn * 1.2 + k * 30) % 180) * Math.PI / 180;
      return <ellipse key={k} rx={Math.abs(Math.cos(a)) * 48} ry="48" fill="none" stroke="rgba(26,98,242,0.28)" strokeWidth="0.8" />;
    })}
    {[-26, 0, 26].map(y => <ellipse key={y} cy={y} rx={Math.sqrt(48 * 48 - y * y)} ry={Math.sqrt(48 * 48 - y * y) * 0.18} fill="none" stroke="rgba(26,98,242,0.22)" strokeWidth="0.8" />)}
    <ellipse rx="66" ry="12" fill="none" stroke={`url(#${id}o)`} strokeWidth="1.2" transform={`rotate(${24 + Math.cos(turn / 50) * 5})`} />
    <ellipse cx="-18" cy="-24" rx="14" ry="8" fill="#FFFFFF" opacity="0.85" transform="rotate(-30 -18 -24)" />
  </svg>;
}

/** A rounded app tile: brand gradient, a soft bevel and a white glyph, with its label underneath. */
export function AppTile({ size, tint = 0, glyph, label, lit = 0, labelSize }: { size: number; tint?: number; glyph?: React.ReactNode; label?: string; lit?: number; labelSize?: number }) {
  const [light, deep] = TINTS[tint % TINTS.length];
  return <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: size * 0.2 }}>
    <div style={{
      width: size, height: size, borderRadius: size * 0.27, display: "grid", placeItems: "center", color: "#FFFFFF",
      background: `linear-gradient(150deg, ${light} 0%, ${deep} 100%)`,
      boxShadow: `inset 0 2px 0 rgba(255,255,255,0.65), inset 0 -${size * 0.1}px ${size * 0.22}px rgba(10,46,122,0.22), 0 ${size * 0.2}px ${size * 0.45}px rgba(26,98,242,${0.2 + lit * 0.18}), 0 0 0 ${lit * 10}px rgba(127,168,255,${0.18 * lit})`,
    }}>{glyph}</div>
    {label && <span data-film-text="label" style={{ fontFamily: auraSans, fontSize: labelSize ?? size * 0.22, fontWeight: 400, color: A.ink, letterSpacing: "-0.01em", whiteSpace: "nowrap" }}>{label}</span>}
  </div>;
}

/** Concentric rings pulsing out of a centre; `active` fades them in and out. */
export function Rings({ size, global, count = 4, period = 36, color = "rgba(26,98,242,0.5)", active = 1 }: { size: number; global: number; count?: number; period?: number; color?: string; active?: number }) {
  return <div style={{ position: "absolute", left: "50%", top: "50%", width: 0, height: 0 }}>
    {Array.from({ length: count }, (_, k) => {
      const t = ((global + (k * period) / count) % period) / period;
      const d = size * (1 + t * 1.7);
      return <div key={k} style={{ position: "absolute", left: -d / 2, top: -d / 2, width: d, height: d, borderRadius: "50%", border: `2px solid ${color}`, opacity: (1 - t) * 0.7 * active }} />;
    })}
  </div>;
}

/** The y of strand `k` at x, breathing on the film clock. */
export function strandY(x: number, k: number, width: number, height: number, global: number, amp: number) {
  const env = Math.sin(Math.PI * Math.min(1, Math.max(0, x / width)));
  const phase = global * 0.09 + k * 0.9;
  return height / 2 + env * amp * (Math.sin(x / width * 9 + phase) * 0.6 + Math.sin(x / width * 4.3 - phase * 0.7 + k) * 0.4) * (1 - k * 0.12);
}

/** Waveform strands: a few thin lines that weave across the frame and fade at both ends. */
export function Strands({ width, height, global, count = 5, amp = 70 }: { width: number; height: number; global: number; count?: number; amp?: number }) {
  const id = useSvgId();
  return <svg width={width} height={height} style={{ position: "absolute", left: 0, top: 0, overflow: "visible" }}>
    <defs>
      <linearGradient id={`${id}s`} x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" stopColor={A.glow} stopOpacity="0" /><stop offset="0.3" stopColor={A.blue} stopOpacity="0.75" /><stop offset="0.7" stopColor={A.mark} stopOpacity="0.75" /><stop offset="1" stopColor={A.cyan} stopOpacity="0" />
      </linearGradient>
    </defs>
    {Array.from({ length: count }, (_, k) => {
      const points = Array.from({ length: 61 }, (_, i) => {
        const x = (i / 60) * width;
        return `${x.toFixed(1)},${strandY(x, k, width, height, global, amp).toFixed(1)}`;
      });
      return <polyline key={k} points={points.join(" ")} fill="none" stroke={`url(#${id}s)`} strokeWidth={k === 0 ? 2.6 : 1.4} opacity={k === 0 ? 1 : 0.55 - k * 0.06} strokeLinecap="round" />;
    })}
  </svg>;
}
