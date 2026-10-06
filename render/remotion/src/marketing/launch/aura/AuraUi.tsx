import React from "react";
import { AbsoluteFill } from "remotion";
import { cursorTarget, focusPoints, ProductWindow, WIN } from "../../kit/ProductUI";
import { useLaunch, type LaunchScene } from "../core";
import { AuraType, dissolveStyle, FloatCard } from "./motion";
import { punchAt, punchBlur, PunchLayer, surfaceKeys } from "./rig";
import { A, glide, rise } from "./tokens";

/** One product surface as an isolated floating card with no window chrome: the phrase above, the card below.
 *  The camera opens on a detail and pulls back, dives to each row the narrator names and punches into the
 *  click, so every zoom lands on a word. Consecutive screens cross-blur. */
export function AuraUiShot({ scene, frame, global, first, last, overlap }: { scene: LaunchScene; frame: number; global: number; first: boolean; last: boolean; overlap: number }) {
  const { portrait } = useLaunch();
  const screen = scene.screen || {};
  const clickAt = scene.clickAt !== undefined ? scene.clickAt - scene.from : undefined;
  const enter = rise(frame, first ? 2 : 0, first ? 14 : 10);
  const out = last ? 0 : glide(frame, scene.frames, overlap);
  const scale = portrait ? 0.86 : 0.9;
  const cardW = WIN.w * scale, cardH = WIN.h * scale;
  const left = ((portrait ? 1080 : 1920) - cardW) / 2;
  const top = portrait ? 700 : 286;
  const onScreen = (p: { x: number; y: number }) => ({ x: left + p.x * scale, y: top + p.y * scale });
  const rest = { x: (portrait ? 1080 : 1920) / 2, y: portrait ? 1180 : 640 };
  const click = clickAt === undefined ? undefined : onScreen(cursorTarget(screen));
  const focus = focusPoints(screen, scene.labels).map(onScreen);
  const keys = surfaceKeys({
    rest, focus, cues: scene.labelFrames || [], click, clickAt, frames: scene.frames,
    opener: focus[0] ?? click ?? onScreen({ x: WIN.w * 0.32, y: WIN.h * 0.3 }),
  });
  const view = punchAt(frame, keys);
  const veil = Math.min(1, Math.max(0, (view.zoom - 1.02) / 0.35));
  return <AbsoluteFill style={dissolveStyle(out)}>
    <PunchLayer view={view} anchor={rest} blur={punchBlur(frame, keys)}>
      <div style={{ position: "absolute", left, top, width: cardW, height: cardH }}>
        <div style={{ width: WIN.w, height: WIN.h, transform: `scale(${scale})`, transformOrigin: "top left" }}>
          <FloatCard width={WIN.w} height={WIN.h} enter={enter} global={global} seed={scene.from} radius={30} tilt={1 - veil * 0.7}>
            <ProductWindow screen={screen} frame={frame} clickAt={clickAt} labelFrames={scene.labelFrames} labels={scene.labels} frames={scene.frames} surface="light" chrome="card" />
          </FloatCard>
        </div>
      </div>
    </PunchLayer>
    <div style={{ position: "absolute", left: 0, right: 0, top: 0, height: portrait ? 720 : 330, opacity: veil,
      background: `linear-gradient(180deg, ${A.field} 0%, ${A.field} 62%, rgba(250,251,253,0) 100%)` }} />
    <div style={{ position: "absolute", left: 0, right: 0, top: portrait ? 250 : 74, height: portrait ? 380 : 180, display: "flex", alignItems: "center", justifyContent: "center", padding: portrait ? "0 70px" : "0 200px" }}>
      <AuraType scene={scene} frame={frame} size={portrait ? 74 : 64} />
    </div>
  </AbsoluteFill>;
}
