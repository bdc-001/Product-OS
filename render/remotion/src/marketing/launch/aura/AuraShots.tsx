import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";
import { useLaunch, type Field, type LaunchScene } from "../core";
import { iconFor } from "../Orbit";
import { AuraCursor, AuraType, Camera, camAt, dissolveStyle, FloatCard, type CamKey } from "./motion";
import { AppTile, Bloom, GlassSphere, GlossPill } from "./objects";
import { punchAt, punchBlur, PunchLayer, surfaceKeys } from "./rig";
import { A, along, auraSans, auraSerif, glide, rise, springAt } from "./tokens";

/** Aura signature shots. Each label lands on its own narration cue, like the classic style shots. */
type ShotProps = { scene: LaunchScene; frame: number; global: number; field: Field };

const cueAt = (scene: LaunchScene, i: number) => scene.labelFrames?.[i] ?? 14 + i * 22;
const labelsOf = (scene: LaunchScene) => scene.labels || [];

/** The phrase that heads a picture-led shot. */
function TopPhrase({ scene, frame, out = 0 }: { scene: LaunchScene; frame: number; out?: number }) {
  const { portrait } = useLaunch();
  return <div style={{ position: "absolute", left: 0, right: 0, top: portrait ? 230 : 70, height: portrait ? 360 : 190, display: "flex", alignItems: "center", justifyContent: "center",
    padding: portrait ? "0 70px" : "0 220px", ...dissolveStyle(out) }}>
    <AuraType scene={scene} frame={frame} size={portrait ? 74 : 64} />
  </div>;
}

/** Capability pills float with parallax; the pointer clicks each one on its cue and it fills with brand blue. */
export function PillsShot({ scene, frame, global }: ShotProps) {
  const { portrait } = useLaunch();
  const labels = labelsOf(scene).slice(0, 3);
  const scale = portrait ? 0.92 : 1;
  const rows = portrait ? [820, 1000, 1180] : labels.length === 2 ? [500, 680] : [440, 600, 760];
  const shifts = portrait ? [-60, 70, -20] : [-240, 170, -60];
  const pan = (along(frame, Math.max(45, scene.frames)) - 0.5) * (portrait ? -90 : -150);
  const pills = labels.map((label, i) => {
    const est = (label.length * 17 + 140) * scale;
    const cx = (portrait ? 540 : 960) + shifts[i] * (labels.length === 2 && !portrait ? 1.2 : 1);
    const left = cx - est / 2 + Math.cos(global / 34 + i) * 9 + pan * (1 + i * 0.35);
    const top = rows[i] - 44 * scale + Math.sin(global / 28 + i * 2) * 11;
    return { label, left, top, cue: cueAt(scene, i) };
  });
  const stops = pills.map(p => ({ x: p.left + 44 * scale, y: p.top + 44 * scale, at: p.cue + 4, click: true }));
  return <AbsoluteFill>
    <TopPhrase scene={scene} frame={frame} />
    {pills.map((p, i) => {
      const enter = springAt(frame, Math.min(p.cue - 8, 4 + i * 4));
      const selected = rise(frame, p.cue + 6, 6);
      const hover = rise(frame, p.cue, 4) * (1 - selected);
      return <div key={i} style={{ position: "absolute", left: p.left, top: p.top, opacity: enter, filter: enter < 1 ? `blur(${(1 - enter) * 14}px)` : undefined,
        transform: `scale(${0.86 + 0.14 * enter})`, transformOrigin: "left center" }}>
        <GlossPill label={p.label} icon={iconFor(p.label, 30 * scale)} scale={scale} tint={i} selected={selected} hover={hover} />
      </div>;
    })}
    <AuraCursor frame={frame} stops={stops} origin={{ x: (portrait ? 540 : 960) + 300, y: portrait ? 1700 : 1000 }} enterAt={(stops[0]?.at ?? 20) - 28} />
  </AbsoluteFill>;
}

/** App tiles joined by curved lines on a canvas larger than the frame: the camera pans tile to tile on the
 *  cues, then pulls back to show the whole path. */
export function NetworkShot({ scene, frame, global }: ShotProps) {
  const { portrait } = useLaunch();
  const labels = labelsOf(scene).slice(0, 3);
  const size = portrait ? 230 : 210;
  const layout = portrait
    ? (labels.length === 2 ? [[0, 0], [140, 820]] : [[0, 0], [-170, 720], [150, 1440]])
    : (labels.length === 2 ? [[0, 0], [1080, 140]] : [[0, 0], [880, -200], [1760, 90]]);
  const tiles = labels.map((label, i) => ({ label, x: layout[i][0], y: layout[i][1], cue: cueAt(scene, i) }));
  const xs = tiles.map(t => t.x), ys = tiles.map(t => t.y);
  const box = { x0: Math.min(...xs) - size, x1: Math.max(...xs) + size, y0: Math.min(...ys) - size, y1: Math.max(...ys) + size * 1.4 };
  const W = portrait ? 1080 : 1920, H = portrait ? 1920 : 1080;
  const room = portrait ? { w: W - 160, h: H - 760 } : { w: W - 260, h: H - 400 };
  const overview = Math.min(1, room.w / (box.x1 - box.x0), room.h / (box.y1 - box.y0));
  const dip = portrait ? 140 : 90;
  const last = tiles.at(-1)!;
  const keys: CamKey[] = [{ at: 0, x: tiles[0].x, y: tiles[0].y + size * 0.2 - dip, zoom: 1 }];
  tiles.slice(1, -1).forEach(t => keys.push({ at: t.cue, x: t.x, y: t.y + size * 0.2 - dip, zoom: 1 }));
  keys.push({ at: Math.min(scene.frames - 6, last.cue + 14), x: (box.x0 + box.x1) / 2, y: (box.y0 + box.y1) / 2 - dip / overview, zoom: overview });
  const parked = camAt(frame, keys, 18);
  const view = { ...parked, x: parked.x + (frame - scene.frames / 2) * 0.6 };
  const curve = (a: typeof tiles[number], b: typeof tiles[number]) => {
    const dx = b.x - a.x, dy = b.y - a.y;
    return portrait
      ? { p0: [a.x, a.y], p1: [a.x + 260, a.y + dy * 0.4], p2: [b.x - 260, b.y - dy * 0.4], p3: [b.x, b.y] }
      : { p0: [a.x, a.y], p1: [a.x + dx * 0.45, a.y - 180], p2: [b.x - dx * 0.45, b.y + 180], p3: [b.x, b.y] };
  };
  const at = (c: ReturnType<typeof curve>, t: number) => {
    const q = 1 - t;
    return [0, 1].map(k => q * q * q * c.p0[k] + 3 * q * q * t * c.p1[k] + 3 * q * t * t * c.p2[k] + t * t * t * c.p3[k]);
  };
  return <AbsoluteFill>
    <Camera view={view}>
      <svg style={{ position: "absolute", left: box.x0 - 400, top: box.y0 - 400, overflow: "visible" }} width={box.x1 - box.x0 + 800} height={box.y1 - box.y0 + 800}>
        <defs><linearGradient id="aura-net" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stopColor={A.periwinkle} /><stop offset="1" stopColor={A.blue} /></linearGradient></defs>
        <g transform={`translate(${400 - box.x0}, ${400 - box.y0})`}>
          {tiles.slice(1).map((b, i) => {
            const c = curve(tiles[i], b);
            const draw = glide(frame, b.cue - 18, 16);
            return <path key={i} d={`M${c.p0} C${c.p1} ${c.p2} ${c.p3}`} pathLength={1} fill="none" stroke="url(#aura-net)" strokeWidth={3 / Math.max(0.6, view.zoom)}
              strokeLinecap="round" strokeDasharray="1" strokeDashoffset={1 - draw} opacity={0.75} />;
          })}
        </g>
      </svg>
      {tiles.slice(1).map((b, i) => {
        const t = glide(frame, b.cue - 18, 16);
        if (t <= 0 || t >= 1) return null;
        const [x, y] = at(curve(tiles[i], b), t);
        return <div key={i} style={{ position: "absolute", left: x - 11, top: y - 11, width: 22, height: 22, borderRadius: "50%", background: "#FFFFFF", boxShadow: "0 0 0 5px rgba(127,168,255,0.4), 0 0 30px 8px rgba(26,98,242,0.45)" }} />;
      })}
      {tiles.map((t, i) => {
        const enter = springAt(frame, i ? t.cue - 6 : 1);
        const lit = rise(frame, t.cue, 6);
        return <div key={i} style={{ position: "absolute", left: t.x - size, top: t.y - size / 2, width: size * 2, display: "flex", justifyContent: "center",
          opacity: Math.min(1, enter), filter: enter < 1 ? `blur(${(1 - enter) * 14}px)` : undefined, transform: `translateY(${(1 - enter) * 30 + Math.sin(global / 26 + i) * 8}px) scale(${0.7 + 0.3 * enter})` }}>
          <AppTile size={size} tint={i + 1} glyph={iconFor(t.label, size * 0.42)} label={t.label} lit={lit} labelSize={portrait ? 40 : 38} />
        </div>;
      })}
    </Camera>
    <TopPhrase scene={scene} frame={frame} />
  </AbsoluteFill>;
}

/** One short claim inside a glow orb with radiating ticks; it collapses into the glass sphere for the next beat. */
export function StatShot({ scene, frame, global }: ShotProps) {
  const { portrait } = useLaunch();
  const R = portrait ? 380 : 400;
  const collapse = glide(frame, scene.frames - 16, 12);
  const breathe = (1 + Math.sin(global / 14) * 0.025) * (0.92 + 0.12 * along(frame, scene.frames));
  const ticks = 84;
  const label = labelsOf(scene)[0];
  return <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
    <div style={{ position: "absolute", left: "50%", top: "50%", width: 0, height: 0, transform: `scale(${(1 - collapse * 0.7) * breathe})`, opacity: 1 - collapse * 0.9 }}>
      <div style={{ position: "absolute", left: -R * 0.95, top: -R * 0.95, width: R * 1.9, height: R * 1.9, borderRadius: "50%", filter: "blur(36px)",
        background: `radial-gradient(circle, #FFFFFF 0%, ${A.haze} 38%, rgba(127,168,255,0.55) 62%, rgba(127,168,255,0) 74%)`, opacity: rise(frame, 0, 12) }} />
      <svg width={R * 2.4} height={R * 2.4} viewBox={`${-R * 1.2} ${-R * 1.2} ${R * 2.4} ${R * 2.4}`} style={{ position: "absolute", left: -R * 1.2, top: -R * 1.2, transform: `rotate(${frame * 0.35}deg)` }}>
        {Array.from({ length: ticks }, (_, i) => {
          const p = rise(frame, 2 + i * 0.22, 7);
          const a = (i / ticks) * Math.PI * 2 - Math.PI / 2;
          const long = i % 7 === 0;
          const r0 = R * 1.0, r1 = R * (long ? 1.12 : 1.06) * (0.96 + 0.04 * p);
          return <line key={i} x1={Math.cos(a) * r0} y1={Math.sin(a) * r0} x2={Math.cos(a) * r1} y2={Math.sin(a) * r1} stroke={long ? A.blue : A.glow} strokeWidth={long ? 3 : 2} strokeLinecap="round" opacity={p * (long ? 0.8 : 0.5)} />;
        })}
      </svg>
    </div>
    <div style={{ position: "absolute", left: "50%", top: "50%", transform: `translate(-50%, -50%) scale(${collapse})`, opacity: collapse }}>
      <GlassSphere size={portrait ? 320 : 300} turn={global} />
    </div>
    <div style={{ position: "relative", display: "flex", flexDirection: "column", alignItems: "center", gap: 26, padding: portrait ? "0 120px" : "0 300px", ...dissolveStyle(collapse) }}>
      <AuraType scene={scene} frame={frame} size={portrait ? 104 : 112} maxWidth={portrait ? 780 : 900} />
      {label && <div data-film-text="label" style={{ fontFamily: auraSans, fontSize: portrait ? 32 : 28, color: A.muted, fontWeight: 400, opacity: rise(frame, cueAt(scene, 0), 8) }}>{label}</div>}
    </div>
  </AbsoluteFill>;
}

/** Settings cards whose switches flip on their cues as the pointer presses them. Labels are verbatim settings. */
export function TogglesShot({ scene, frame, global }: ShotProps) {
  const { portrait } = useLaunch();
  const labels = labelsOf(scene).slice(0, 3);
  const w = portrait ? 900 : 780, h = portrait ? 124 : 112, gap = 24;
  const top0 = (portrait ? 1040 : 640) - (labels.length * h + (labels.length - 1) * gap) / 2;
  const left = ((portrait ? 1080 : 1920) - w) / 2;
  const heading = scene.screen?.title;
  const stops = labels.map((_, i) => ({ x: left + w - 34 - 44, y: top0 + i * (h + gap) + h / 2, at: cueAt(scene, i) + 4, click: true }));
  return <AbsoluteFill>
    <TopPhrase scene={scene} frame={frame} />
    {heading && <div data-film-text="label" style={{ position: "absolute", left, top: top0 - 56, fontFamily: auraSans, fontSize: 22, fontWeight: 500, letterSpacing: "0.18em", textTransform: "uppercase", color: A.muted, opacity: rise(frame, 1, 8) }}>{heading}</div>}
    {labels.map((label, i) => {
      const on = rise(frame, cueAt(scene, i) + 6, 6);
      const enter = rise(frame, 2 + i * 4, 12);
      return <div key={i} style={{ position: "absolute", left, top: top0 + i * (h + gap) }}>
        <FloatCard width={w} height={h} enter={enter} global={global} seed={i} radius={24} tilt={0.4}
          inner={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 34px" }}>
          <span data-film-text="label" style={{ fontFamily: auraSans, fontSize: portrait ? 34 : 30, fontWeight: 400, color: A.ink, letterSpacing: "-0.01em", whiteSpace: "nowrap" }}>{label}</span>
          <div style={{ position: "relative", width: 88, height: 50, borderRadius: 25, flexShrink: 0,
            background: on > 0.01 ? `linear-gradient(135deg, rgba(102,153,255,${on}), rgba(26,98,242,${on})), #E3E8F2` : "#E3E8F2",
            boxShadow: `inset 0 1px 3px rgba(22,26,35,0.12), 0 0 0 ${on * 6}px rgba(127,168,255,${0.18 * on})` }}>
            <div style={{ position: "absolute", top: 4, left: 4 + on * 38, width: 42, height: 42, borderRadius: 21, background: "#FFFFFF", boxShadow: "0 3px 8px rgba(22,26,35,0.2)" }} />
          </div>
        </FloatCard>
      </div>;
    })}
    <AuraCursor frame={frame} stops={stops} origin={{ x: left + w + 220, y: portrait ? 1700 : 1000 }} />
  </AbsoluteFill>;
}

/** A bloom opens and zooms until it fills the frame while two or three workflow words cycle over it. */
export function BloomShot({ scene, frame, global }: ShotProps) {
  const { portrait } = useLaunch();
  const labels = labelsOf(scene).slice(0, 3);
  const first = cueAt(scene, 0);
  // The bloom bursts from a dot to filling the frame in about two-thirds of a second, then keeps pushing in.
  const zoom = 0.3 + rise(frame, Math.max(0, first - 24), 20) * 2.9 + along(frame, scene.frames) * 1.4;
  const base = portrait ? 620 : 560;
  const veil = glide(frame, Math.max(0, first - 12), 14);
  return <AbsoluteFill style={{ overflow: "hidden" }}>
    <div style={{ position: "absolute", left: "50%", top: "52%", width: 0, height: 0, transform: `scale(${zoom})` }}>
      <div style={{ position: "absolute", left: -base / 2, top: -base / 2 }}>
        <Bloom size={base} open={rise(frame, 0, 18)} spin={frame * 0.4} tint={1} />
      </div>
    </div>
    <AbsoluteFill style={{ background: `radial-gradient(circle at 50% 52%, rgba(255,255,255,${0.55 * veil}) 0%, rgba(255,255,255,${0.25 * veil}) 60%, rgba(255,255,255,0) 100%)` }} />
    <TopPhrase scene={scene} frame={frame} out={glide(frame, first - 8, 8)} />
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", padding: portrait ? "0 80px" : "0 200px" }}>
      <div style={{ display: "grid", justifyItems: "center" }}>
        {labels.map((label, i) => {
          const cue = cueAt(scene, i), next = labels[i + 1] !== undefined ? cueAt(scene, i + 1) : undefined;
          const p = rise(frame, cue - 2, 9);
          const out = next === undefined ? 0 : glide(frame, next - 5, 7);
          return <div key={i} data-film-text="label" style={{ gridArea: "1 / 1", fontFamily: auraSerif, fontStyle: "italic", fontSize: portrait ? 124 : 150, lineHeight: 1.05,
            color: A.ink, textAlign: "center", textShadow: "0 0 40px rgba(255,255,255,0.95), 0 0 80px rgba(255,255,255,0.8)",
            opacity: p * (1 - out), filter: p < 1 || out > 0 ? `blur(${((1 - p) * 16 + out * 18).toFixed(2)}px)` : undefined, transform: `scale(${0.94 + 0.06 * p + out * 0.04})` }}>{label}</div>;
        })}
      </div>
    </AbsoluteFill>
  </AbsoluteFill>;
}

/** A real product capture as a floating card: a slow camera push and a pointer gliding across it. */
export function ScreenshotShot({ scene, frame, global }: ShotProps) {
  const { portrait } = useLaunch();
  if (!scene.src) return <AuraType scene={scene} frame={frame} />;
  const w = scene.shotWidth || 1600, h = scene.shotHeight || 1000;
  const maxW = portrait ? 960 : 1300, maxH = portrait ? 1040 : 650;
  const scale = Math.min(maxW / w, maxH / h);
  const cw = w * scale, ch = h * scale;
  const left = ((portrait ? 1080 : 1920) - cw) / 2;
  const top = portrait ? 680 : 300;
  const enter = springAt(frame, 1, { damping: 16 });
  const stops = [
    { x: left + cw * 0.34, y: top + ch * 0.4, at: Math.round(scene.frames * 0.3) },
    { x: left + cw * 0.62, y: top + ch * 0.56, at: Math.round(scene.frames * 0.62), click: true },
  ];
  // A capture is a bitmap, so its dives stay shallow enough to keep the pixels sharp.
  const rest = { x: (portrait ? 1080 : 1920) / 2, y: top + ch * 0.55 };
  const keys = surfaceKeys({ rest, opener: stops[1], focus: [stops[0]], cues: [stops[0].at], click: stops[1], clickAt: stops[1].at, frames: scene.frames,
    openZoom: 1.5, focusZoom: 1.3, clickZoom: 1.5 });
  const view = punchAt(frame, keys);
  const veil = Math.min(1, Math.max(0, (view.zoom - 1.02) / 0.3));
  return <AbsoluteFill>
    <PunchLayer view={view} anchor={rest} blur={punchBlur(frame, keys)}>
      <div style={{ position: "absolute", left, top, width: cw, height: ch }}>
        <FloatCard width={cw} height={ch} enter={enter} global={global} seed={3} radius={22} tilt={0.6 * (1 - veil)}>
          <Img src={staticFile(scene.src)} style={{ width: cw, height: ch, objectFit: "contain", display: "block" }} />
        </FloatCard>
      </div>
      <AuraCursor frame={frame} stops={stops} origin={{ x: left + cw + 160, y: top + ch + 160 }} />
    </PunchLayer>
    <div style={{ position: "absolute", left: 0, right: 0, top: 0, height: portrait ? 700 : 300, opacity: veil,
      background: `linear-gradient(180deg, ${A.field} 0%, ${A.field} 62%, rgba(250,251,253,0) 100%)` }} />
    <TopPhrase scene={scene} frame={frame} />
    {scene.shotCaption && <div data-film-text="caption" style={{ position: "absolute", left: 0, right: 0, top: top + ch + (portrait ? 60 : 34), textAlign: "center", fontFamily: auraSans,
      fontSize: portrait ? 26 : 22, color: A.muted, opacity: rise(frame, 10, 10) * (1 - veil), padding: "0 120px" }}>{scene.shotCaption}</div>}
  </AbsoluteFill>;
}

export const AURA_SHOTS: Record<string, (props: ShotProps) => React.ReactElement> = {
  pills: PillsShot, network: NetworkShot, stat: StatShot, toggles: TogglesShot, bloom: BloomShot, screenshot: ScreenshotShot,
};

export const AURA_SHOT_FIELDS: Record<string, Field> = {
  pills: "aura", network: "aura", stat: "aura", toggles: "aura", bloom: "aura", screenshot: "aura",
};
