import React from "react";
import { AbsoluteFill, interpolate } from "remotion";
import { emphasisMask, seeded, useLaunch, type LaunchScene } from "../core";
import { auraSize, AuraType, BlurPhrase, phraseCues, phraseGroups, type Cue } from "./motion";
import { Gem, GEMS, GlassSphere } from "./objects";
import { A, along, auraEase, auraSans, auraSerif, glide, rise, springAt } from "./tokens";

/** A type-only shot never stands alone on the field: each one takes the next motion device in turn.
 *  orbit: the phrase parts around a glass sphere. track: a line draws and a sphere rides it under the words.
 *  sweep: a stream of gems crosses the frame and the phrase lands in its wake. zoom: each word punches in
 *  from the camera with a ring on its cue. */
type Device = "orbit" | "track" | "sweep" | "zoom";
const DEVICES: Device[] = ["orbit", "track", "sweep", "zoom"];
/** Average advance of light Inter at -0.03em tracking, in ems: enough to fit a phrase on one line. */
const CHAR = 0.52;

type DeviceProps = { scene: LaunchScene; frame: number; cues: Cue[]; mask: boolean[]; size: number; portrait: boolean; W: number; H: number };

export function AuraKinetic({ scene, frame }: { scene: LaunchScene; frame: number }) {
  const { portrait, audioFrom, kinetics = [] } = useLaunch();
  const cues = phraseCues(scene, scene.headline, audioFrom);
  const mask = emphasisMask(scene.headline, scene.emphasis);
  const W = portrait ? 1080 : 1920, H = portrait ? 1920 : 1080;
  const push = 0.97 + along(frame, scene.frames) * 0.08;
  if (!cues.length) return <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}><AuraType scene={scene} frame={frame} /></AbsoluteFill>;
  const single = phraseGroups(cues.map(c => c.word)).length === 1;
  const n = cues.length, chars = cues.map(c => c.word).join(" ").length;
  const split = Math.ceil(n / 2);
  const side = Math.max(cues.slice(0, split).map(c => c.word).join(" ").length, cues.slice(split).map(c => c.word).join(" ").length);
  const fits: Record<Device, number> = {
    orbit: Math.min(auraSize(n, portrait), (portrait ? 900 : (W - 340 - 300) / 2) / (CHAR * side)),
    track: Math.min(auraSize(n, portrait), (W - (portrait ? 160 : 340)) / (CHAR * chars)),
    sweep: auraSize(n, portrait),
    zoom: auraSize(n, portrait),
  };
  let device = DEVICES[Math.max(0, kinetics.indexOf(scene.from)) % DEVICES.length];
  if ((device === "orbit" || device === "track") && (!single || n < 2 || fits[device] < (portrait ? 64 : 76))) device = device === "orbit" ? "zoom" : "sweep";
  const props: DeviceProps = { scene, frame, cues, mask, size: fits[device], portrait, W, H };
  const kick = device === "zoom" ? cues.reduce((v, c) => Math.max(v, pulse(frame, c.at)), 0) * 0.035 : 0;
  return <AbsoluteFill style={{ transform: `scale(${push + kick})` }}>
    {device === "orbit" ? <OrbitDevice {...props} /> : device === "track" ? <TrackDevice {...props} /> : device === "sweep" ? <SweepDevice {...props} /> : <ZoomDevice {...props} single={single} />}
  </AbsoluteFill>;
}

/** A hit that peaks two frames after its cue and decays: the camera's answer to a spoken word. */
const pulse = (frame: number, at: number) => frame < at ? 0 : Math.min(1, (frame - at) / 2) * Math.exp(-(frame - at) / 6);

function Words({ scene, frame, cues, mask, size, from = 0, to }: { scene: LaunchScene; frame: number; cues: Cue[]; mask: boolean[]; size: number; from?: number; to?: number }) {
  const part = cues.slice(from, to);
  return <BlurPhrase scene={scene} frame={frame} text={part.map(c => c.word).join(" ")} cues={part} mask={mask.slice(from, to ?? cues.length)} size={size} style={{ whiteSpace: "nowrap" }} maxWidth={99999} />;
}

/** "Then [sphere] it's live": the sphere pops in throwing rings, the phrase parts around it, orbits draw on. */
function OrbitDevice({ scene, frame, cues, mask, size, portrait }: DeviceProps) {
  const split = Math.ceil(cues.length / 2);
  const S = portrait ? 420 : 400, box = S * 0.66;
  const pop = springAt(frame, 0, { damping: 10 });
  const open = glide(frame, Math.max(0, cues[0].at - 6), 12);
  const orbits = [0, 1].map(j => {
    const d = rise(frame, 6 + j * 5, 20), rx = S * (0.52 + j * 0.16);
    return <ellipse key={j} rx={rx} ry={rx * 0.28} fill="none" stroke={A.blue} strokeOpacity={0.34} strokeWidth={1.6} pathLength={1} strokeDasharray="1 1" strokeDashoffset={1 - d}
      transform={`rotate(${(j ? 26 : -20) + frame * (j ? -0.8 : 1)})`} />;
  });
  const waves = [0, 1, 2].map(j => {
    const r = rise(frame, j * 5, 28);
    return r > 0 && r < 1 ? <circle key={`w${j}`} r={S * 0.3 + r * S * 2.2} fill="none" stroke={A.blue} strokeOpacity={0.24 * (1 - r)} strokeWidth={1.4} /> : null;
  });
  const sphere = <div style={{ position: "relative", width: box, height: box, flexShrink: 0, transform: `scale(${0.2 + 0.8 * pop})`, opacity: Math.min(1, pop * 2) }}>
    <svg width={S * 4} height={S * 4} viewBox={`${-S * 2} ${-S * 2} ${S * 4} ${S * 4}`} style={{ position: "absolute", left: box / 2 - S * 2, top: box / 2 - S * 2, overflow: "visible" }}>{waves}{orbits}</svg>
    <div style={{ position: "absolute", left: (box - S) / 2, top: (box - S) / 2 }}><GlassSphere size={S} turn={frame * 2.2} /></div>
  </div>;
  const shift = (1 - open) * box * 0.35;
  return <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", flexDirection: portrait ? "column" : "row", gap: portrait ? 30 : 44 }}>
    <div style={{ transform: portrait ? `translateY(${shift}px)` : `translateX(${shift}px)` }}><Words scene={scene} frame={frame} cues={cues} mask={mask} size={size} to={split} /></div>
    {sphere}
    <div style={{ transform: portrait ? `translateY(${-shift}px)` : `translateX(${-shift}px)` }}><Words scene={scene} frame={frame} cues={cues} mask={mask} size={size} from={split} /></div>
  </AbsoluteFill>;
}

/** A hairline draws across the frame, a sphere rides it under each word as it lands, a trail of gems follows,
 *  and a vertical rule drops where the phrase ends. */
function TrackDevice({ scene, frame, cues, mask, size, W, H }: DeviceProps) {
  const textW = cues.map(c => c.word).join(" ").length * CHAR * size;
  const cx = W / 2, cy = H / 2, lineY = cy + size * 0.8;
  const first = cues[0].at, end = cues[cues.length - 1].at + 10;
  const x0 = cx - textW / 2 - 60, x1 = cx + textW / 2 + 60;
  const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: auraEase } as const;
  const orbX = frame < first - 4 ? interpolate(frame, [0, first - 4], [-90, x0], clamp) : interpolate(frame, [first - 4, end], [x0, x1], { ...clamp, easing: (t: number) => t });
  const arrive = pulse(frame, end);
  const draw = glide(frame, 0, 14), slant = glide(frame, 6, 16), rule = rise(frame, end, 12);
  const spread = rise(frame, first - 4, 16);
  return <AbsoluteFill>
    <svg width={W} height={H} style={{ position: "absolute", inset: 0 }}>
      <line x1={0} y1={lineY} x2={W * draw} y2={lineY} stroke={A.ink} strokeOpacity={0.26} strokeWidth={2} />
      <line x1={0} y1={lineY + 70} x2={W * slant} y2={lineY + 70 - slant * 160} stroke={A.blue} strokeOpacity={0.24} strokeWidth={1.6} />
      <line x1={x1} y1={lineY} x2={x1} y2={lineY - rule * size * 1.5} stroke={A.ink} strokeOpacity={0.26} strokeWidth={2} />
      <line x1={x1} y1={lineY} x2={x1} y2={lineY + rule * size * 0.9} stroke={A.ink} strokeOpacity={0.26} strokeWidth={2} />
    </svg>
    {[0, 1, 2].map(j => {
      const gx = orbX - (j + 1) * 86 * spread, gs = 46 - j * 6;
      return <div key={j} style={{ position: "absolute", left: gx - gs / 2, top: lineY - gs / 2, opacity: spread }}>
        <Gem kind={GEMS[(j + 1) % GEMS.length]} size={gs} tint={j + 1} spin={frame * (j % 2 ? -3 : 3)} />
      </div>;
    })}
    <div style={{ position: "absolute", left: orbX - 70, top: lineY - 70, transform: `scale(${1 + arrive * 0.25})` }}><GlassSphere size={140} turn={frame * 3} /></div>
    <div style={{ position: "absolute", left: 0, right: 0, top: 0, bottom: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <Words scene={scene} frame={frame} cues={cues} mask={mask} size={size} />
    </div>
  </AbsoluteFill>;
}

/** A diagonal stream of gems crosses the frame just ahead of the words; four of them stay and float around the phrase. */
function SweepDevice({ scene, frame, cues, size, portrait, W, H }: DeviceProps) {
  const first = cues[0].at;
  const from = { x: -260, y: H + 260 }, dir = { x: W + 520, y: -(H + 520) };
  const len = Math.hypot(dir.x, dir.y), perp = { x: -dir.y / len, y: dir.x / len };
  const tw = Math.min(W - (portrait ? 160 : 340), cues.map(c => c.word).join(" ").length * CHAR * size);
  const cx = W / 2, cy = H / 2;
  const rests = [
    { x: cx - tw / 2 - 40, y: cy - size * 1.25 }, { x: cx + tw / 2 + 30, y: cy - size * 1.05 },
    { x: cx - tw / 2 + 60, y: cy + size * 1.3 }, { x: cx + tw / 2 - 10, y: cy + size * 1.2 },
  ];
  const gems = Array.from({ length: portrait ? 12 : 16 }, (_, i) => {
    const offset = (seeded(i + 1) - 0.5) * (portrait ? 1000 : 1100);
    const start = Math.max(0, first - 14) + seeded(i + 5) * 10;
    const sx = from.x + perp.x * offset, sy = from.y + perp.y * offset;
    const rest = i < rests.length ? rests[i] : null;
    const size0 = rest ? 58 + seeded(i + 9) * 26 : 34 + seeded(i + 9) * 92;
    let x: number, y: number, seen: number;
    if (rest) {
      const t = rise(frame, start, 22);
      x = sx + (rest.x - sx) * t + Math.sin(frame / 14 + i) * 6 * t;
      y = sy + (rest.y - sy) * t + Math.cos(frame / 16 + i) * 6 * t;
      seen = Math.min(1, t * 3);
    } else {
      const t = glide(frame, start, 18 + seeded(i + 7) * 10);
      x = sx + dir.x * t; y = sy + dir.y * t;
      seen = t > 0 && t < 1 ? 1 : 0;
    }
    if (!seen) return null;
    const moving = !rest || frame < start + 16;
    return <div key={i} style={{ position: "absolute", left: x - size0 / 2, top: y - size0 / 2, opacity: seen, filter: moving && size0 < 70 ? "blur(1.4px)" : undefined }}>
      <Gem kind={GEMS[i % GEMS.length]} size={size0} tint={i} spin={seeded(i + 3) * 60 + frame * (seeded(i + 4) - 0.5) * 6} />
    </div>;
  });
  return <AbsoluteFill>
    {gems}
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", padding: portrait ? "0 80px" : "0 170px" }}><AuraType scene={scene} frame={frame} /></AbsoluteFill>
  </AbsoluteFill>;
}

/** Each word punches in from the camera, and every spoken cue throws a ring out from the centre. */
function ZoomDevice({ scene, frame, cues, mask, size, portrait, W, H, single }: DeviceProps & { single: boolean }) {
  const rings = cues.map((c, i) => {
    const r = rise(frame, c.at, 24);
    return r > 0 && r < 1 ? <circle key={i} cx={W / 2} cy={H / 2} r={90 + r * W * 0.46} fill="none" stroke={A.blue} strokeOpacity={0.26 * (1 - r)} strokeWidth={1.6} /> : null;
  });
  return <AbsoluteFill>
    <svg width={W} height={H} style={{ position: "absolute", inset: 0 }}>{rings}</svg>
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", padding: portrait ? "0 80px" : "0 170px" }}>
      {single ? <div data-film-text="headline" style={{ fontFamily: auraSans, fontSize: size, fontWeight: 300, lineHeight: 1.12, letterSpacing: "-0.03em", color: A.ink, textAlign: "center",
        maxWidth: portrait ? 920 : 1500, textWrap: "balance" }}>
        {cues.map(({ word, at }, i) => {
          const p = rise(frame, at, 10);
          return <React.Fragment key={i}>
            <span style={{ display: "inline-block", whiteSpace: "nowrap", opacity: Math.min(1, p * 1.6), transform: p < 1 ? `scale(${(1.7 - 0.7 * p).toFixed(3)})` : undefined,
              filter: p < 1 ? `blur(${((1 - p) * 18).toFixed(2)}px)` : undefined,
              ...(mask[i] ? { fontFamily: auraSerif, fontStyle: "italic", fontWeight: 400, fontSize: "1.08em", letterSpacing: "-0.01em", color: A.blue } : {}) }}>{word}</span>
            {i < cues.length - 1 ? " " : ""}
          </React.Fragment>;
        })}
      </div> : <AuraType scene={scene} frame={frame} />}
    </AbsoluteFill>
  </AbsoluteFill>;
}
