import { Lottie, type LottieAnimationData } from "@remotion/lottie";
import { Trail } from "@remotion/motion-blur";
import { evolvePath, getLength, getPointAtLength } from "@remotion/paths";
import { makeArrow, makeCircle, makeRect, makeSpark } from "@remotion/shapes";
import React, { useMemo } from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import type { Scene } from "./Film";

const C = { blue: "#1A62F2", line: "#AFCAFB" };
const BLUE = [0.102, 0.384, 0.949, 1];
const LINE = [0.686, 0.792, 0.984, 1];
const PALE = [0.933, 0.957, 1, 1];
const WHITE = [1, 1, 1, 1];
const ease3 = { i: { x: [0.16, 0.16, 0.16], y: [1, 1, 1] }, o: { x: [0.3, 0.3, 0.3], y: [0, 0, 0] } };
const ease1 = { i: { x: [0.16], y: [1] }, o: { x: [0.3], y: [0] } };

function stroke(color: number[], width = 6) {
  return { ty: "st", c: { a: 0, k: color }, o: { a: 0, k: 100 }, w: { a: 0, k: width }, lc: 2, lj: 2, ml: 4, d: [] as never[] };
}
function fill(color: number[], opacity = 100) {
  return { ty: "fl", c: { a: 0, k: color }, o: { a: 0, k: opacity }, r: 1 };
}
function trim() {
  return { ty: "tm", s: { a: 0, k: 0 }, e: { a: 1, k: [{ t: 0, s: [0], ...ease1 }, { t: 16, s: [100] }] }, o: { a: 0, k: 0 }, m: 1 };
}
function transform() {
  return { ty: "tr", p: { a: 0, k: [0, 0] }, a: { a: 0, k: [0, 0] }, s: { a: 0, k: [100, 100] }, r: { a: 0, k: 0 }, o: { a: 0, k: 100 }, sk: { a: 0, k: 0 }, sa: { a: 0, k: 0 } };
}
function group(name: string, items: object[]) {
  return { ty: "gr", nm: name, it: [...items, transform()] };
}
function rect(x: number, y: number, w: number, h: number, r = 6) {
  return { ty: "rc", p: { a: 0, k: [x, y] }, s: { a: 0, k: [w, h] }, r: { a: 0, k: r } };
}
function ellipse(x: number, y: number, w: number, h: number) {
  return { ty: "el", p: { a: 0, k: [x, y] }, s: { a: 0, k: [w, h] } };
}
function path(points: number[][], closed = false) {
  return { ty: "sh", ks: { a: 0, k: { c: closed, v: points, i: points.map(() => [0, 0]), o: points.map(() => [0, 0]) } } };
}

function animation(name: string, shapes: object[]): LottieAnimationData {
  return {
    v: "5.7.4",
    fr: 30,
    ip: 0,
    op: 30,
    w: 120,
    h: 120,
    nm: name,
    ddd: 0,
    assets: [],
    layers: [{
      ddd: 0, ind: 1, ty: 4, nm: name, sr: 1, ao: 0, ip: 0, op: 30, st: 0, bm: 0,
      ks: {
        o: { a: 0, k: 100 },
        r: { a: 1, k: [{ t: 0, s: [-6], ...ease1 }, { t: 14, s: [0] }] },
        p: { a: 0, k: [60, 60, 0] },
        a: { a: 0, k: [0, 0, 0] },
        s: { a: 1, k: [{ t: 0, s: [82, 82, 100], ...ease3 }, { t: 16, s: [100, 100, 100] }] },
      },
      shapes,
    }],
  } as LottieAnimationData;
}

function motifData(visual: Scene["visual"] | undefined, dark: boolean): LottieAnimationData {
  const ink = dark ? LINE : BLUE;
  const paper = dark ? [0.039, 0.18, 0.478, 1] : PALE;
  if (visual === "call") {
    return animation("phone", [
      group("body", [rect(0, 4, 44, 68, 8), fill(paper), stroke(ink, 5)]),
      group("ear", [rect(0, -24, 16, 5, 2), fill(ink)]),
      group("btn", [ellipse(0, 28, 10, 10), stroke(ink, 3)]),
    ]);
  }
  if (visual === "mask" || visual === "split") {
    return animation("lock", [
      group("shackle", [path([[-14, 2], [-14, -18], [14, -18], [14, 2]]), stroke(ink, 6), trim()]),
      group("body", [rect(0, 14, 48, 34, 6), fill(paper), stroke(ink, 5)]),
    ]);
  }
  if (visual === "detect") {
    return animation("alert", [
      group("ring", [ellipse(0, 0, 78, 78), stroke(LINE, 3), fill(BLUE, 12)]),
      group("bang", [rect(0, -8, 8, 32, 4), fill(ink)]),
      group("dot", [ellipse(0, 22, 8, 8), fill(ink)]),
    ]);
  }
  if (visual === "collect" || visual === "stack") {
    return animation("doc", [
      group("page", [rect(0, 2, 46, 58, 6), fill(paper), stroke(ink, 5)]),
      group("l1", [rect(0, -10, 26, 4, 2), fill(ink)]),
      group("l2", [rect(0, 2, 20, 4, 2), fill(LINE)]),
      group("l3", [rect(0, 14, 16, 4, 2), fill(LINE)]),
    ]);
  }
  if (visual === "statement") {
    return animation("check", [
      group("disc", [ellipse(0, 0, 72, 72), fill(BLUE)]),
      group("mark", [path([[-16, 2], [-5, 14], [18, -12]]), stroke(WHITE, 8), trim()]),
    ]);
  }
  if (visual === "spread") {
    return animation("rings", [
      group("a", [ellipse(0, 0, 28, 28), fill(BLUE)]),
      group("b", [ellipse(0, 0, 52, 52), stroke(ink, 4)]),
      group("c", [ellipse(0, 0, 76, 76), stroke(LINE, 3)]),
    ]);
  }
  return animation("nodes", [
    group("a", [ellipse(-24, 0, 18, 18), fill(ink)]),
    group("b", [ellipse(0, 0, 22, 22), fill(BLUE)]),
    group("c", [ellipse(24, 0, 18, 18), fill(LINE)]),
  ]);
}

/** Primary motif plays once; ambient scale/glow continues on the film clock. */
export function Motif({ visual, dark = false, size = 64 }: { visual?: Scene["visual"]; dark?: boolean; size?: number }) {
  const frame = useCurrentFrame();
  const data = useMemo(() => motifData(visual, dark), [visual, dark]);
  const live = 1 + Math.sin(frame / 28) * 0.04;
  const glow = 10 + Math.sin(frame / 22) * 6;
  if (visual === "spotlight") {
    const spark = makeSpark({ width: size, height: size, edgeRoundness: 0.85 });
    return <svg width={size} height={size} viewBox={`0 0 ${spark.width} ${spark.height}`} style={{ flexShrink: 0, transform: `scale(${live})`, filter: `drop-shadow(0 0 ${glow}px ${C.blue})` }}><path d={spark.path} fill={dark ? C.line : C.blue} /></svg>;
  }
  return <div style={{ width: size, height: size, flexShrink: 0, transform: `scale(${live})`, filter: `drop-shadow(0 8px ${glow}px rgba(26,98,242,0.35))` }}>
    <Lottie animationData={data} loop={false} renderer="svg" style={{ width: size, height: size }} />
  </div>;
}

export function BrandArrow({ direction = "right", opacity = 1, dark = false, length }: { direction?: "right" | "down"; opacity?: number; dark?: boolean; length?: number }) {
  const vertical = direction === "down";
  const { path: d, width, height } = makeArrow({
    length: length ?? (vertical ? 40 : 56),
    direction,
    headWidth: 14,
    headLength: 12,
    shaftWidth: 4,
    cornerRadius: 1,
  });
  return <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{ flexShrink: 0, opacity }}><path d={d} fill={dark ? C.line : C.blue} /></svg>;
}

export function LockMark({ size = 22, on = true, dark = true }: { size?: number; on?: boolean; dark?: boolean }) {
  const color = dark ? C.line : C.blue;
  const hoop = makeCircle({ radius: size * 0.18 });
  const body = makeRect({ width: size * 0.62, height: size * 0.46, cornerRadius: 3 });
  return <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ opacity: on ? 1 : 0.35, flexShrink: 0 }}>
    <g transform={`translate(${size * 0.32}, ${size * 0.1})`} fill="none" stroke={color} strokeWidth="1.8"><path d={hoop.path} /></g>
    <g transform={`translate(${size * 0.19}, ${size * 0.42})`} fill="none" stroke={color} strokeWidth="1.8"><path d={body.path} /></g>
  </svg>;
}

export function WriteOnPath({ d, progress, color, width = 2 }: { d: string; progress: number; color: string; width?: number }) {
  const evolved = evolvePath(Math.max(0, Math.min(1, progress)), d);
  return <path d={d} fill="none" stroke={color} strokeWidth={width} strokeDasharray={evolved.strokeDasharray} strokeDashoffset={evolved.strokeDashoffset} />;
}

function SignalHead({ d, start, viewW, viewH, color, size }: { d: string; start: number; viewW: number; viewH: number; color: string; size: number }) {
  const frame = useCurrentFrame();
  const t = (Math.max(0, frame - start) % 36) / 36;
  const point = getPointAtLength(d, t * getLength(d));
  if (!point) return null;
  return <AbsoluteFill style={{ width: size + 4, height: size + 4, left: `${(point.x / viewW) * 100}%`, top: `${(point.y / viewH) * 100}%`, transform: `translate(${-size / 2}px,${-size / 2}px)`, pointerEvents: "none" }}>
    <div style={{ width: size, height: size, borderRadius: "50%", background: color, boxShadow: `0 0 ${size * 1.2}px ${color}` }} />
  </AbsoluteFill>;
}

/** Travelling signal with motion blur. Size is in composition pixels, not viewBox units. */
export function SignalTrail({ d, start, viewW, viewH, color, size = 10 }: { d: string; start: number; viewW: number; viewH: number; color: string; size?: number }) {
  return <Trail layers={7} lagInFrames={0.4} trailOpacity={0.48}><SignalHead d={d} start={start} viewW={viewW} viewH={viewH} color={color} size={size} /></Trail>;
}
