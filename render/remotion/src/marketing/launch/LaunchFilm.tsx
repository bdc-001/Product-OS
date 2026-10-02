import React, { useLayoutEffect, useMemo, useRef } from "react";
import { AbsoluteFill, Audio, Img, Sequence, staticFile, useCurrentFrame } from "remotion";
import type { FilmProps } from "../Film";
import { cursorTarget, ProductWindow, WIN } from "../kit/ProductUI";
import { CallStage } from "./CallStage";
import { EndCard, Kinetic, KineticType } from "./Kinetic";
import { Orbit } from "./Orbit";
import { ScaleShot } from "./ScaleShots";
import { body, FieldLayer, K, LaunchCtx, OVERLAP, progress, type Background, type Field, type LaunchCraft, type LaunchScene, type LaunchTransition, type ScaleLayout } from "./core";

type Block = { family: "call" | "ui" | "single"; field: Field; bg?: Background; transition: LaunchTransition; items: { scene: LaunchScene; index: number; layout?: ScaleLayout }[] };

function fieldFor(scene: LaunchScene, index: number): Field {
  if (scene.visual === "call") return "stage";
  if (scene.visual === "volume" || scene.visual === "orbit" || scene.visual === "messages") return "dark";
  if (scene.visual === "ui" || scene.visual === "endcard") return "brand";
  return index === 0 || scene.kind === "problem" ? "light" : "brand";
}

/** Consecutive call scenes share one handset; consecutive product screens share one field and push between windows. */
function blocksOf(scenes: LaunchScene[], craft?: LaunchCraft[]): Block[] {
  const blocks: Block[] = [];
  scenes.forEach((scene, index) => {
    const field = craft?.[index]?.field ?? fieldFor(scene, index);
    const bg = craft?.[index]?.bg;
    const layout = craft?.[index]?.layout;
    const family = scene.visual === "call" ? "call" : scene.visual === "ui" ? "ui" : "single";
    const last = blocks[blocks.length - 1];
    if (last && family !== "single" && last.family === family && last.field === field && last.bg === bg) {
      last.items.push({ scene, index, layout });
      return;
    }
    blocks.push({ family, field, bg, transition: craft?.[index]?.transition ?? (family === "call" ? "fade" : family === "ui" ? "push" : "wipe"), items: [{ scene, index, layout }] });
  });
  return blocks;
}

function enterStyle(kind: LaunchTransition, p: number, first: boolean): React.CSSProperties {
  if (first) return {};
  if (kind === "wipe") return { clipPath: `inset(0 0 0 ${(1 - p) * 100}%)` };
  if (kind === "push") return { transform: `translateX(${(1 - p) * 100}%)` };
  if (kind === "slide") return { clipPath: `inset(${(1 - p) * 100}% 0 0 0)` };
  return { opacity: p };
}

/** Text that leaves the frame is a render failure, not a review note. */
function useBoundsGuard(root: React.RefObject<HTMLDivElement | null>, frame: number, settled: boolean, label: string) {
  useLayoutEffect(() => {
    if (!settled || !root.current) return;
    const bounds = root.current.getBoundingClientRect();
    if (bounds.width < 8) return;
    for (const el of Array.from(root.current.querySelectorAll<HTMLElement>("[data-film-text]"))) {
      const r = el.getBoundingClientRect();
      if (r.width && (r.left < bounds.left - 2 || r.right > bounds.right + 2 || r.top < bounds.top - 2 || r.bottom > bounds.bottom + 2)) {
        throw new Error(`${label} text exceeds the frame: ${el.textContent?.slice(0, 70)}`);
      }
    }
  }, [frame, settled, label, root]);
}

function UiShot({ scene, frame, first, last, field }: { scene: LaunchScene; frame: number; first: boolean; last: boolean; field: Field }) {
  const portrait = React.useContext(LaunchCtx).portrait;
  const light = field === "light" || field === "stage";
  const enter = progress(frame, 0, first ? 20 : 16);
  const exit = last ? 0 : progress(frame, scene.frames, OVERLAP);
  const clickAt = scene.clickAt !== undefined ? scene.clickAt - scene.from : undefined;
  const push = clickAt === undefined ? 0 : progress(frame, clickAt - 26, 22) * 0.045;
  const target = clickAt === undefined ? { x: WIN.w / 2, y: WIN.h / 2 } : cursorTarget(scene.screen || {});
  const scale = portrait ? 0.875 : 1;
  const winX = first ? 0 : (1 - enter) * 1300;
  const tilt = (1 - enter) * 10 + 3.5;
  return <AbsoluteFill>
    <div style={{ position: "absolute", left: portrait ? 70 : 110, top: portrait ? 190 : 0, bottom: portrait ? undefined : 0, width: portrait ? 940 : 560, display: "flex", flexDirection: "column", justifyContent: "center", gap: 26, opacity: 1 - exit, transform: `translateY(${-exit * 40}px)` }}>
      {scene.tag && <div data-film-text="tag" style={{ alignSelf: "flex-start", padding: "10px 20px", borderRadius: 999, background: light ? K.blue : "#FFFFFF", color: light ? "#FFFFFF" : K.blue, fontFamily: body, fontSize: portrait ? 28 : 24, fontWeight: 700, letterSpacing: 0.3, boxShadow: light ? "0 14px 34px rgba(26,98,242,0.28)" : "0 14px 34px rgba(6,34,120,0.35)", opacity: progress(frame, 2, 10), transform: `translateY(${(1 - progress(frame, 2, 12)) * 16}px)` }}>{scene.tag}</div>}
      <KineticType scene={scene} frame={frame} field={field} size={portrait ? 82 : 78} align="left" maxWidth={portrait ? 940 : 560} />
      {scene.body && <div data-film-text="body" style={{ fontFamily: body, fontSize: portrait ? 30 : 26, lineHeight: 1.4, color: light ? "#334155" : "#DCE7FF", opacity: progress(frame, 18, 14) }}>{scene.body}</div>}
    </div>
    <div style={{ position: "absolute", left: portrait ? (1080 - WIN.w * scale) / 2 : 730, top: portrait ? 760 : (1080 - WIN.h) / 2, width: WIN.w, height: WIN.h, perspective: 2400, transform: `scale(${scale})`, transformOrigin: "top left" }}>
      <div style={{
        width: WIN.w, height: WIN.h, transformOrigin: `${target.x}px ${target.y}px`,
        transform: `translateX(${winX - exit * 1400}px) translateY(${first ? (1 - enter) * 90 : 0}px) rotateY(${-tilt}deg) rotateX(${(1 - enter) * 4 + 1}deg) scale(${1 + push})`,
        opacity: first ? enter : 1,
      }}>
        <ProductWindow screen={scene.screen || {}} frame={frame} clickAt={clickAt} labelFrames={scene.labelFrames} labels={scene.labels} frames={scene.frames} surface={light ? "light" : "dark"} />
      </div>
    </div>
  </AbsoluteFill>;
}

function Single({ scene, frame, global, field, layout }: { scene: LaunchScene; frame: number; global: number; field: Field; layout?: ScaleLayout }) {
  if (scene.visual === "volume" || scene.visual === "messages") return <ScaleShot scene={scene} frame={frame} global={global} layout={layout} />;
  if (scene.visual === "orbit") return <Orbit scene={scene} frame={frame} global={global} />;
  if (scene.visual === "endcard") return <EndCard scene={scene} frame={frame} />;
  return <Kinetic scene={scene} frame={frame} field={field} />;
}

function Lockup({ field, portrait }: { field: Field; portrait: boolean }) {
  const light = field === "light" || field === "stage";
  return <Img src={staticFile(light ? "brand-logo-light.svg" : "brand-logo-dark.svg")} style={{ position: "absolute", top: portrait ? 90 : 56, left: portrait ? 70 : 96, width: portrait ? 170 : 160, height: 40, objectFit: "contain", objectPosition: "left", opacity: 0.92 }} />;
}

function BlockLayer({ block, first, isLast }: { block: Block; first: boolean; isLast: boolean }) {
  const local = useCurrentFrame();
  const start = block.items[0].scene.from;
  const global = start + local;
  const { portrait } = React.useContext(LaunchCtx);
  const root = useRef<HTMLDivElement>(null);
  const p = progress(local, 0, OVERLAP);
  const active = [...block.items].reverse().find(item => global >= item.scene.from) ?? block.items[0];
  const settled = global - active.scene.from > Math.min(active.scene.frames - 3, Math.max(40, ...(active.scene.labelFrames || [0])) + 22) && global < active.scene.from + active.scene.frames;
  useBoundsGuard(root, local, settled, `Shot ${active.index + 1}`);
  const edge = block.transition === "wipe" && !first && p < 1;
  return <AbsoluteFill ref={root} style={{ overflow: "hidden", ...enterStyle(block.transition, p, first) }}>
    <FieldLayer field={block.field} bg={block.bg} global={global} portrait={portrait} />
    {block.family === "call" && <CallStage block={block.items.map(i => i.scene)} global={global} />}
    {block.family === "ui" && block.items.map(({ scene }, i) => <Sequence key={i} from={scene.from - start} durationInFrames={scene.frames + (i < block.items.length - 1 ? OVERLAP : isLast ? 0 : OVERLAP)}>
      <UiFrame scene={scene} first={i === 0} last={i === block.items.length - 1} field={block.field} />
    </Sequence>)}
    {block.family === "single" && <Single scene={active.scene} frame={global - active.scene.from} global={global} field={block.field} layout={active.layout} />}
    {block.items[0].scene.visual !== "endcard" && <Lockup field={block.field} portrait={portrait} />}
    {edge && <div style={{ position: "absolute", top: 0, bottom: 0, left: `${(1 - p) * 100}%`, width: 6, marginLeft: -3, background: "rgba(255,255,255,0.9)", boxShadow: "0 0 40px 14px rgba(160,195,255,0.7)" }} />}
  </AbsoluteFill>;
}

function UiFrame({ scene, first, last, field }: { scene: LaunchScene; first: boolean; last: boolean; field: Field }) {
  return <UiShot scene={scene} frame={useCurrentFrame()} first={first} last={last} field={field} />;
}

/** Launch grammar: gradient worlds, narration-timed kinetic type, persistent calls and illustrative product screens. */
export const LaunchFilm: React.FC<FilmProps & { craft?: unknown }> = ({ scenes, portrait, title, audio, audioFrom = 3, craft }) => {
  const launchScenes = scenes as unknown as LaunchScene[];
  const blocks = useMemo(() => blocksOf(launchScenes, craft as LaunchCraft[] | undefined), [launchScenes, craft]);
  const value = useMemo(() => ({ audioFrom, portrait, title }), [audioFrom, portrait, title]);
  return <LaunchCtx.Provider value={value}>
    <AbsoluteFill style={{ fontFamily: body, background: "#03060F" }}>
      <style>{`@font-face{font-family:Inter;src:url('${staticFile("Inter.ttf")}') format('truetype');font-weight:400;font-display:block}@font-face{font-family:Inter;src:url('${staticFile("Inter-Medium.ttf")}') format('truetype');font-weight:500 800;font-display:block}*{box-sizing:border-box}`}</style>
      {blocks.map((block, i) => {
        const start = block.items[0].scene.from;
        const tail = block.items[block.items.length - 1].scene;
        const end = tail.from + tail.frames + (i < blocks.length - 1 ? OVERLAP : 0);
        return <Sequence key={i} from={start} durationInFrames={end - start}>
          <BlockLayer block={block} first={i === 0} isLast={i === blocks.length - 1} />
        </Sequence>;
      })}
      {audio && <Sequence from={audioFrom}><Audio src={staticFile(audio)} /></Sequence>}
    </AbsoluteFill>
  </LaunchCtx.Provider>;
};
