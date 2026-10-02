import React, { createContext, useContext, useMemo } from "react";
import { moduleName } from "./brand";
import { AbsoluteFill, Audio, Easing, Img, interpolate, Sequence, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import type { FilmProps, Scene } from "./Film";

export const CROSS_FRAMES = 26;
export const C = { blue: "#1A62F2", navy: "#0A2E7A", dark: "#151515", ink: "#050505", pale: "#EEF4FF", line: "#AFCAFB", inverse: "#F1F1F1" };
export const ease = Easing.bezier(0.22, 1, 0.36, 1);
export const display = "'Helvetica Neue', Helvetica, Arial, sans-serif";

export type Luma = "dark" | "light";
export type TransitionKind = "cross-dissolve" | "matched-element" | "masked-wipe" | "camera-push";
export type SceneCraft = { luma: Luma; treatment: string; transition: TransitionKind; plate?: string | null };
type WorldValue = { craft: SceneCraft[]; luma: Luma; camera: { x: number; y: number; scale: number }; frame: number; fps: number };

const WorldCtx = createContext<WorldValue | null>(null);
const SceneIndexCtx = createContext(0);
export const useWorld = () => {
  const value = useContext(WorldCtx);
  if (!value) throw new Error("Film content must render inside PersistentWorld");
  return value;
};
export const useSceneCraft = (): SceneCraft => {
  const { craft } = useWorld();
  return craft[useContext(SceneIndexCtx)] ?? { luma: "dark", treatment: "centre-dark", transition: "cross-dissolve" };
};

const TRANSITIONS: TransitionKind[] = ["cross-dissolve", "matched-element", "masked-wipe", "camera-push"];
const STATEMENT = ["centre-dark", "left-light", "emphasis-dark"];
const CONTRAST = ["split-dark", "split-light"];
const HUB = ["hub-dark", "hub-light"];
const DEVICE = new Set(["call", "conversation"]);

export function craftForScenes(scenes: Pick<Scene, "visual" | "kind">[]): SceneCraft[] {
  const counts: Record<string, number> = {};
  const out: SceneCraft[] = [];
  let prevLuma: Luma | null = null;
  let prevVisual: string | null = null;
  scenes.forEach((scene, i) => {
    const visual = scene.visual || "statement";
    counts[visual] = visual === prevVisual ? (counts[visual] || 0) + 1 : 0;
    const idx = counts[visual];
    let treatment: string;
    let luma: Luma;
    if (DEVICE.has(visual)) {
      treatment = "stage-light";
      luma = "light";
    } else if (visual === "statement" || !scene.visual) {
      treatment = STATEMENT[idx % STATEMENT.length];
      luma = treatment.includes("light") ? "light" : "dark";
    } else if (visual === "contrast") {
      treatment = CONTRAST[idx % CONTRAST.length];
      luma = treatment.includes("light") ? "light" : "dark";
    } else if (visual === "orchestration" || visual === "stack") {
      treatment = HUB[idx % HUB.length];
      luma = treatment.includes("light") ? "light" : "dark";
    } else {
      luma = prevLuma === "light" ? "dark" : "light";
      treatment = `${visual}-${luma}`;
    }
    if (prevLuma === luma && !DEVICE.has(visual) && visual !== "statement" && visual !== "contrast") {
      luma = luma === "dark" ? "light" : "dark";
      treatment = luma === "light" ? treatment.replace("dark", "light") : treatment.replace("light", "dark");
    }
    out.push({ luma, treatment, transition: TRANSITIONS[i % 4], plate: null });
    prevLuma = luma;
    prevVisual = visual;
  });
  return out;
}

export const progress = (frame: number, start = 0, duration = 14) =>
  interpolate(frame, [start, start + duration], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });

export function buildSpan(scene: Scene) {
  const words = scene.wordTimings;
  if (words?.length) {
    const span = Math.round((words[words.length - 1].end - words[0].start) * 30);
    return Math.max(24, Math.min(scene.frames - 10, span || Math.round(scene.frames * 0.7)));
  }
  const last = scene.captions?.at(-1)?.to;
  return Math.max(24, Math.min(scene.frames - 10, last ?? Math.round(scene.frames * 0.7)));
}

/** Next element starts before the previous settles. */
export function overlapStagger(index: number, count: number, span: number) {
  const n = Math.max(1, count);
  const duration = span / (1 + (n - 1) * 0.55);
  return { start: index * duration * 0.55, duration: Math.max(10, duration) };
}

export function sceneLayerStyle(frame: number, scene: Scene, overlap: number, transition: TransitionKind): React.CSSProperties {
  const fadeIn = progress(frame, 0, Math.min(CROSS_FRAMES, Math.floor(scene.frames / 3)));
  const fadeOut = overlap ? interpolate(frame, [scene.frames - 1, scene.frames + overlap], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease }) : 1;
  if (transition === "masked-wipe" && frame >= scene.frames - 1) {
    const wipe = interpolate(frame, [scene.frames - 1, scene.frames + overlap], [0, 100], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
    return { opacity: fadeIn, clipPath: `inset(0 0 0 ${wipe}%)` };
  }
  return { opacity: fadeIn * fadeOut };
}

export function Elevated({ children, z = 1, dark = false, radius = 20, style, ...rest }: { children: React.ReactNode; z?: number; dark?: boolean; radius?: number; style?: React.CSSProperties } & React.HTMLAttributes<HTMLDivElement>) {
  const lift = 1 + z * 0.012;
  return <div {...rest} style={{
    transform: `scale(${lift}) translateZ(0)`,
    borderRadius: radius,
    boxShadow: dark
      ? `0 ${16 + z * 10}px ${48 + z * 24}px rgba(5,12,32,0.55), 0 0 ${28 + z * 10}px rgba(26,98,242,0.28), inset 0 1px 0 rgba(175,202,251,0.25)`
      : `0 ${14 + z * 8}px ${40 + z * 18}px rgba(10,46,122,0.18), 0 0 ${20 + z * 8}px rgba(26,98,242,0.12), inset 0 1px 0 rgba(255,255,255,0.85)`,
    background: dark
      ? "linear-gradient(165deg, rgba(26,98,242,0.28) 0%, rgba(10,46,122,0.72) 48%, rgba(21,21,21,0.92) 100%)"
      : "linear-gradient(165deg, #F7FAFF 0%, #EEF4FF 46%, #D4E4FF 100%)",
    ...style,
  }}>{children}</div>;
}

const snap = (n: number) => Math.round(n * 2) / 2;

function cameraAt(frame: number, scenes: Scene[], craft: SceneCraft[], fps: number) {
  const index = Math.max(0, scenes.findIndex((_, i) => frame < (scenes[i + 1]?.from ?? 1e9)));
  const scene = scenes[index] ?? scenes[0];
  const local = scene ? frame - scene.from : frame;
  const t = scene ? Math.min(1, Math.max(0, local / Math.max(1, scene.frames))) : 0;
  const eased = interpolate(t, [0, 1], [0, 1], { easing: ease });
  const stage = (craft[index]?.treatment || "").startsWith("stage");
  const drift = frame / fps;
  if (stage) {
    return { x: snap(Math.sin(drift * 0.14) * 3), y: snap(Math.cos(drift * 0.11) * 2), scale: 1 };
  }
  const push = craft[index]?.transition === "camera-push" ? eased * 0.03 : 0;
  return {
    x: snap(Math.sin(drift * 0.22 + index) * 8 + (index % 2 ? 6 : -6) * (1 - eased)),
    y: snap(Math.cos(drift * 0.18) * 5),
    scale: 1.02 + Math.sin(drift * 0.16) * 0.005 + push,
  };
}

function Bloom({ luma, frame }: { luma: Luma; frame: number }) {
  const pulse = 0.42 + Math.sin(frame / 34) * 0.12;
  const orbs = [
    { x: 12 + Math.sin(frame / 90) * 6, y: 18 + Math.cos(frame / 110) * 4, s: 52, c: C.blue },
    { x: 78 + Math.cos(frame / 100) * 5, y: 62 + Math.sin(frame / 80) * 6, s: 44, c: C.navy },
    { x: 58 + Math.sin(frame / 70) * 8, y: 8 + Math.cos(frame / 95) * 5, s: 36, c: C.line },
  ];
  return <AbsoluteFill style={{ pointerEvents: "none", mixBlendMode: luma === "dark" ? "screen" : "multiply", opacity: luma === "dark" ? 0.85 : 0.4 }}>
    {orbs.map((orb, i) => <div key={i} style={{
      position: "absolute", left: `${orb.x}%`, top: `${orb.y}%`, width: `${orb.s}%`, height: `${orb.s * 0.7}%`,
      transform: "translate(-50%, -50%)", borderRadius: "50%",
      background: `radial-gradient(circle, ${orb.c}${Math.round(50 + pulse * 90).toString(16).padStart(2, "0")} 0%, transparent 68%)`,
      filter: "blur(28px)",
    }} />)}
  </AbsoluteFill>;
}

function WorldField({ luma, camera, plate, frame, stage }: { luma: Luma; camera: { x: number; y: number; scale: number }; plate?: string | null; frame: number; stage?: boolean }) {
  const dark = luma === "dark";
  const grain = stage ? 0.02 : 0.045 + Math.sin(frame / 50) * 0.01;
  return <AbsoluteFill style={{ overflow: "hidden" }}>
    <AbsoluteFill style={{
      background: stage
        ? "linear-gradient(180deg, #F7FAFF 0%, #EEF4FF 46%, #E4EEFF 100%)"
        : dark
          ? "linear-gradient(128deg, #1A62F2 0%, #0A2E7A 42%, #151515 78%, #050505 100%)"
          : "linear-gradient(128deg, #F4F8FF 0%, #EEF4FF 38%, #C9DCFF 72%, #AFCAFB 100%)",
      transform: `translate(${camera.x * 0.35}px, ${camera.y * 0.35}px) scale(${1.08 + (camera.scale - 1) * 0.4})`,
    }} />
    {plate && !stage && <Img src={staticFile(plate)} style={{
      position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover",
      opacity: dark ? 0.28 : 0.16, filter: "saturate(1.1) blur(14px)",
      transform: `scale(${1.12 + Math.sin(frame / 96) * 0.012}) translate(${camera.x * 0.4}px, ${camera.y * 0.4}px)`,
    }} />}
    {!stage && <Bloom luma={luma} frame={frame} />}
    <AbsoluteFill style={{
      opacity: grain, mixBlendMode: dark ? "overlay" : "multiply",
      backgroundImage: "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='80' height='80'><filter id='n'><feTurbulence baseFrequency='.8' numOctaves='2' stitchTiles='stitch'/></filter><rect width='100%' height='100%' filter='url(%23n)' opacity='.55'/></svg>\")",
    }} />
  </AbsoluteFill>;
}

function FilmChrome({ portrait, preview }: { portrait: boolean; preview?: boolean }) {
  const frame = useCurrentFrame();
  const { luma } = useWorld();
  const dark = luma === "dark";
  const glow = 0.55 + Math.sin(frame / 32) * 0.2;
  return <>
    <Img src={staticFile(dark ? "brand-logo-dark.svg" : "brand-logo-light.svg")} style={{
      position: "absolute", top: portrait ? 120 : 64, left: portrait ? 88 : 100, width: portrait ? 195 : 210, height: 48, objectFit: "contain", objectPosition: "left",
      filter: `drop-shadow(0 0 ${18 + glow * 12}px rgba(26,98,242,${0.35 + glow * 0.2}))`,
    }} />
    <span style={{ position: "absolute", top: portrait ? 132 : 76, right: portrait ? 130 : 100, fontSize: 22, color: dark ? C.line : "#3A5A96", letterSpacing: 1.4 }}>{preview ? "DESIGN PREVIEW" : moduleName().toUpperCase()}</span>
  </>;
}

export function PersistentWorld({ scenes, craft, children, photographic, portrait, preview, chrome = true }: { scenes: Scene[]; craft: SceneCraft[]; children: React.ReactNode; photographic?: string | null; portrait: boolean; preview?: boolean; chrome?: boolean }) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const index = Math.max(0, scenes.findIndex((_, i) => frame < (scenes[i + 1]?.from ?? 1e9)));
  const luma = craft[index]?.luma ?? "dark";
  const stage = (craft[index]?.treatment || "").startsWith("stage");
  const camera = cameraAt(frame, scenes, craft, fps);
  // Reference artwork can contain unrelated claims/UI. Only an explicitly
  // authored film may choose a photographic plate; generic campaigns cannot.
  const plate = stage ? null : photographic;
  const value = useMemo(() => ({ craft, luma, camera, frame, fps }), [craft, luma, camera.x, camera.y, camera.scale, frame, fps]);
  return <WorldCtx.Provider value={value}>
    <AbsoluteFill style={{ overflow: "hidden" }}>
      <WorldField luma={luma} camera={camera} plate={plate} frame={frame} stage={stage} />
      {chrome && <FilmChrome portrait={portrait} preview={preview} />}
      <AbsoluteFill style={{ transform: `translate(${camera.x}px, ${camera.y}px) scale(${camera.scale})`, transformOrigin: "center center" }}>
        {children}
      </AbsoluteFill>
    </AbsoluteFill>
  </WorldCtx.Provider>;
}

function SceneBody({ scene, overlap, transition, children }: { scene: Scene; overlap: number; transition: TransitionKind; children: React.ReactNode }) {
  const frame = useCurrentFrame();
  return <AbsoluteFill style={sceneLayerStyle(frame, scene, overlap, transition)}>{children}</AbsoluteFill>;
}

export function overlappingDuration(scene: Scene, index: number, total: number) {
  return scene.frames + (index < total - 1 ? CROSS_FRAMES : 0);
}

export function SceneLayer({ index, scene, total, children }: { index: number; scene: Scene; total: number; children: React.ReactNode }) {
  const overlap = index < total - 1 ? CROSS_FRAMES : 0;
  const transition = useWorld().craft[index]?.transition ?? "cross-dissolve";
  return <Sequence from={scene.from} durationInFrames={overlappingDuration(scene, index, total)}>
    <SceneIndexCtx.Provider value={index}>
      <SceneBody scene={scene} overlap={overlap} transition={transition}>{children}</SceneBody>
    </SceneIndexCtx.Provider>
  </Sequence>;
}

export function FilmRoot({ scenes, portrait, preview, audio, audioFrom = 3, craft, children, photographic, chrome = true }: FilmProps & { children: React.ReactNode; photographic?: string | null; chrome?: boolean }) {
  const resolved = craft?.length ? craft : craftForScenes(scenes);
  return <AbsoluteFill style={{ fontFamily: "Inter, Arial, sans-serif" }}>
    <style>{`@font-face{font-family:Inter;src:url('${staticFile("Inter.ttf")}') format('truetype');font-weight:400;font-display:block}@font-face{font-family:Inter;src:url('${staticFile("Inter-Medium.ttf")}') format('truetype');font-weight:500 800;font-display:block}*{box-sizing:border-box}`}</style>
    <PersistentWorld scenes={scenes} craft={resolved} photographic={photographic} portrait={portrait} preview={preview} chrome={chrome}>
      {audio && <Sequence from={audioFrom}><Audio src={staticFile(audio)} /></Sequence>}
      {children}
    </PersistentWorld>
  </AbsoluteFill>;
}
