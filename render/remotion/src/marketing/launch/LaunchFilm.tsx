import React, { useLayoutEffect, useMemo, useRef } from "react";
import { AbsoluteFill, Audio, Img, Sequence, staticFile, useCurrentFrame } from "remotion";
import type { FilmProps } from "../Film";
import { cursorTarget, ProductWindow, WIN } from "../kit/ProductUI";
import { CallStage } from "./CallStage";
import { DuetCall } from "./DuetCall";
import { FlatCall } from "./FlatCall";
import { GlassCall } from "./GlassCall";
import { IndiaMap } from "./IndiaMap";
import { NumberPool } from "./NumberPool";
import { EndCard, Kinetic, KineticType, Presenting } from "./Kinetic";
import { Orbit } from "./Orbit";
import { ScaleShot } from "./ScaleShots";
import { SplitCall } from "./SplitCall";
import { STYLE_FIELDS, STYLE_SHOTS } from "./StyleShots";
import { AuraCall } from "./aura/AuraCall";
import { AuraEndCard, AuraPresenting } from "./aura/AuraCards";
import { AuraKinetic } from "./aura/AuraKinetic";
import { AuraField } from "./aura/AuraField";
import { AURA_SHOT_FIELDS, AURA_SHOTS } from "./aura/AuraShots";
import { AuraUiShot } from "./aura/AuraUi";
import { morphIn, morphOut, MORPHS } from "./aura/motion";
import { along, auraSans, BEAT, glide, useAuraFonts } from "./aura/tokens";
import { body, FieldLayer, K, LaunchCtx, OVERLAP, progress, type Background, type Field, type LaunchCraft, type LaunchScene, type LaunchTransition, type Ringtone, type ScaleLayout } from "./core";

type Block = { family: "call" | "ui" | "single"; field: Field; bg?: Background; look?: LaunchCraft["look"]; ring?: Ringtone; transition: LaunchTransition; items: { scene: LaunchScene; index: number; layout?: ScaleLayout }[] };
type Exit = { kind: string; at: number };
const CALLS = { glass: GlassCall, flat: FlatCall, split: SplitCall, duet: DuetCall, rings: AuraCall } as const;

function fieldFor(scene: LaunchScene, index: number): Field {
  if (scene.visual && AURA_SHOT_FIELDS[scene.visual]) return AURA_SHOT_FIELDS[scene.visual];
  if (scene.visual && STYLE_FIELDS[scene.visual]) return STYLE_FIELDS[scene.visual];
  if (scene.visual === "call") return "stage";
  if (scene.visual === "volume" || scene.visual === "orbit" || scene.visual === "messages") return "dark";
  if (scene.visual === "endcard" || scene.visual === "presenting" || scene.visual === "india" || scene.visual === "pool") return "light";
  if (scene.visual === "ui") return "brand";
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
    blocks.push({ family, field, bg, look: craft?.[index]?.look, ring: craft?.[index]?.ring, transition: craft?.[index]?.transition ?? (family === "call" ? "fade" : family === "ui" ? "push" : "wipe"), items: [{ scene, index, layout }] });
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
    const range = document.createRange();
    for (const el of Array.from(root.current.querySelectorAll<HTMLElement>("[data-film-text]"))) {
      // A punch-in deliberately crops the surface it zooms into.
      if (el.closest("[data-film-zoom]")) continue;
      // The glyphs, not the box: a full-width caption row is fine while the camera pushes past its padding.
      range.selectNodeContents(el);
      const r = range.getBoundingClientRect();
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

/** The Aura language: its own renderers for the shared shots and its signature shots; any other shot keeps its
 *  classic design, drawn on the light grammar so its type stays dark on the white field. */
function AuraSingle({ scene, frame, global, layout, look }: { scene: LaunchScene; frame: number; global: number; layout?: ScaleLayout; look?: string }) {
  if (scene.visual === "presenting") return look && look !== "swarm" ? <Presenting scene={scene} frame={frame} look={look} /> : <AuraPresenting scene={scene} frame={frame} />;
  if (scene.visual === "endcard") return look && look !== "tagline" ? <EndCard scene={scene} frame={frame} look={look} /> : <AuraEndCard scene={scene} frame={frame} />;
  const Shot = scene.visual ? AURA_SHOTS[scene.visual] : undefined;
  if (Shot) return <Shot scene={scene} frame={frame} global={global} field="aura" />;
  if (!scene.visual || scene.visual === "kinetic") return <AuraKinetic scene={scene} frame={frame} />;
  return <Single scene={scene} frame={frame} global={global} field="light" layout={layout} look={look} />;
}

function Single({ scene, frame, global, field, layout, look }: { scene: LaunchScene; frame: number; global: number; field: Field; layout?: ScaleLayout; look?: string }) {
  if (scene.visual === "volume" || scene.visual === "messages") return <ScaleShot scene={scene} frame={frame} global={global} layout={layout} />;
  if (scene.visual === "orbit") return <Orbit scene={scene} frame={frame} global={global} />;
  if (scene.visual === "endcard") return <EndCard scene={scene} frame={frame} look={look} />;
  if (scene.visual === "presenting") return <Presenting scene={scene} frame={frame} look={look} />;
  if (scene.visual === "india") return <IndiaMap scene={scene} frame={frame} global={global} />;
  if (scene.visual === "pool" && scene.pool) return <NumberPool scene={scene} frame={frame} global={global} />;
  const Shot = scene.visual ? STYLE_SHOTS[scene.visual] : undefined;
  if (Shot) return <Shot scene={scene} frame={frame} global={global} field={field} />;
  return <Kinetic scene={scene} frame={frame} field={field} />;
}

function Lockup({ field, portrait }: { field: Field; portrait: boolean }) {
  const light = field === "light" || field === "stage";
  return <Img src={staticFile(light ? "brand-logo-light.svg" : "brand-logo-dark.svg")} style={{ position: "absolute", top: portrait ? 90 : 56, left: portrait ? 70 : 96, width: portrait ? 170 : 160, height: 40, objectFit: "contain", objectPosition: "left", opacity: 0.92 }} />;
}

function BlockLayer({ block, first, isLast, overlap, exit }: { block: Block; first: boolean; isLast: boolean; overlap: number; exit?: Exit }) {
  const local = useCurrentFrame();
  const start = block.items[0].scene.from;
  const global = start + local;
  const { portrait } = React.useContext(LaunchCtx);
  const root = useRef<HTMLDivElement>(null);
  const aura = block.field === "aura";
  const morph = MORPHS.has(block.transition);
  const p = morph ? glide(local, 0, overlap) : progress(local, 0, overlap);
  const active = [...block.items].reverse().find(item => global >= item.scene.from) ?? block.items[0];
  const settled = global - active.scene.from > Math.min(active.scene.frames - 3, Math.max(40, ...(active.scene.labelFrames || [0])) + 22) && global < active.scene.from + active.scene.frames;
  useBoundsGuard(root, local, settled, `Shot ${active.index + 1}`);
  const edge = block.transition === "wipe" && !first && p < 1;
  const leaving = exit && local >= exit.at ? morphOut(exit.kind, glide(local, exit.at, overlap)) : null;
  const entering = first ? {} : morph ? morphIn(block.transition, p) : enterStyle(block.transition, p, first);
  const span = block.items.reduce((sum, item) => sum + item.scene.frames, 0) + overlap;
  const camera: React.CSSProperties | undefined = aura
    ? { transform: `scale(${1 + 0.05 * along(local, span)}) translate(${(Math.sin(global / 70) * 10).toFixed(2)}px, ${(Math.cos(global / 85) * 6).toFixed(2)}px)` }
    : undefined;
  return <AbsoluteFill ref={root} style={{ overflow: "hidden", ...(leaving ?? entering) }}>
    {aura ? <AuraField global={global} portrait={portrait} /> : <FieldLayer field={block.field} bg={block.bg} global={global} portrait={portrait} />}
    <AbsoluteFill style={camera}>
    {block.family === "call" && (() => {
      const Call = CALLS[block.look as keyof typeof CALLS] ?? CallStage;
      return <Call block={block.items.map(i => i.scene)} global={global} ring={block.ring} />;
    })()}
    {block.family === "ui" && block.items.map(({ scene }, i) => <Sequence key={i} from={scene.from - start} durationInFrames={scene.frames + (i < block.items.length - 1 ? overlap : isLast ? 0 : overlap)}>
      <UiFrame scene={scene} first={i === 0} last={i === block.items.length - 1} field={block.field} overlap={overlap} />
    </Sequence>)}
    {block.family === "single" && (aura
      ? <AuraSingle scene={active.scene} frame={global - active.scene.from} global={global} layout={active.layout} look={block.look} />
      : <Single scene={active.scene} frame={global - active.scene.from} global={global} field={block.field} layout={active.layout} look={block.look} />)}
    </AbsoluteFill>
    {!aura && block.items[0].scene.visual !== "endcard" && block.items[0].scene.visual !== "presenting" && <Lockup field={block.field} portrait={portrait} />}
    {edge && <div style={{ position: "absolute", top: 0, bottom: 0, left: `${(1 - p) * 100}%`, width: 6, marginLeft: -3, background: "rgba(255,255,255,0.9)", boxShadow: "0 0 40px 14px rgba(160,195,255,0.7)" }} />}
  </AbsoluteFill>;
}

function UiFrame({ scene, first, last, field, overlap }: { scene: LaunchScene; first: boolean; last: boolean; field: Field; overlap: number }) {
  const frame = useCurrentFrame();
  if (field === "aura") return <AuraUiShot scene={scene} frame={frame} global={scene.from + frame} first={first} last={last} overlap={overlap} />;
  return <UiShot scene={scene} frame={frame} first={first} last={last} field={field} />;
}

/** Launch grammar: gradient worlds, narration-timed kinetic type, persistent calls and illustrative product screens.
 *  `language: "aura"` (or Aura craft) switches to the airy white field, blur-in phrases, floating cards and morphs. */
export const LaunchFilm: React.FC<FilmProps & { craft?: unknown; language?: string }> = ({ scenes, portrait, title, audio, audioFrom = 3, craft, product = "", module = "", language }) => {
  const launchScenes = scenes as unknown as LaunchScene[];
  const crafted = craft as LaunchCraft[] | undefined;
  const aura = language === "aura" || !!crafted?.some(c => c.field === "aura");
  useAuraFonts(aura);
  const overlap = aura ? BEAT.overlap : OVERLAP;
  const blocks = useMemo(() => blocksOf(launchScenes, crafted), [launchScenes, crafted]);
  const steps = useMemo(() => {
    const reveal = launchScenes.findIndex(s => s.visual === "presenting");
    return launchScenes.slice(reveal + 1).filter(s => s.visual !== "endcard" && s.visual !== "kinetic" && s.visual !== "call").map(s => s.headline).slice(0, 4);
  }, [launchScenes]);
  const kinetics = useMemo(() => launchScenes.filter(s => !s.visual || s.visual === "kinetic").map(s => s.from), [launchScenes]);
  const value = useMemo(() => ({ audioFrom, portrait, title, product, module, steps, kinetics }), [audioFrom, portrait, title, product, module, steps, kinetics]);
  return <LaunchCtx.Provider value={value}>
    <AbsoluteFill style={{ fontFamily: aura ? auraSans : body, background: aura ? "#FAFBFD" : "#03060F" }}>
      <style>{`@font-face{font-family:Inter;src:url('${staticFile("Inter.ttf")}') format('truetype');font-weight:400;font-display:block}@font-face{font-family:Inter;src:url('${staticFile("Inter-Medium.ttf")}') format('truetype');font-weight:500 800;font-display:block}*{box-sizing:border-box}`}</style>
      {blocks.map((block, i) => {
        const start = block.items[0].scene.from;
        const tail = block.items[block.items.length - 1].scene;
        const end = tail.from + tail.frames + (i < blocks.length - 1 ? overlap : 0);
        const next = blocks[i + 1];
        const exit = next && MORPHS.has(next.transition) ? { kind: next.transition, at: next.items[0].scene.from - start } : undefined;
        return <Sequence key={i} from={start} durationInFrames={end - start}>
          <BlockLayer block={block} first={i === 0} isLast={i === blocks.length - 1} overlap={overlap} exit={exit} />
        </Sequence>;
      })}
      {audio && <Sequence from={audioFrom}><Audio src={staticFile(audio)} /></Sequence>}
      {/* Local previews have no assembled narration track, only one system-voice take per scene. */}
      {!audio && launchScenes.map((s, i) => s.audio
        ? <Sequence key={`take-${i}`} from={s.from + (s.audioFrom ?? 3)}><Audio src={staticFile(s.audio)} /></Sequence>
        : null)}
    </AbsoluteFill>
  </LaunchCtx.Provider>;
};
