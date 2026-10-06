import React from "react";
import { glide } from "./tokens";

export type View = { x: number; y: number; zoom: number };
export type PunchKey = View & { at: number; travel?: number };

/** The punch-in camera: it holds each key and snaps to the next over that key's travel, landing on its frame.
 *  Zoom moves geometrically, so a 1x to 2x dive reads as one even push. */
export function punchAt(frame: number, keys: PunchKey[]): View {
  let { x, y, zoom } = keys[0];
  for (const key of keys.slice(1)) {
    const travel = key.travel ?? 9;
    const p = glide(frame, key.at - travel, travel);
    x += (key.x - x) * p; y += (key.y - y) * p; zoom *= Math.pow(key.zoom / zoom, p);
  }
  return { x, y, zoom };
}

/** Motion blur from the camera's screen speed, capped so the type it lands on stays legible. */
export function punchBlur(frame: number, keys: PunchKey[], cap = 6) {
  const a = punchAt(frame - 1, keys), b = punchAt(frame, keys);
  const speed = Math.hypot((b.x - a.x) * b.zoom, (b.y - a.y) * b.zoom) + Math.abs(Math.log(b.zoom / a.zoom)) * 900;
  return Math.min(cap, Math.max(0, speed - 14) / 12);
}

/** A full-frame layer framed by `view`: the rest-layout point (x, y) lands on `anchor` at `zoom`.
 *  The rest view ({ ...anchor, zoom: 1 }) is the identity. */
export function PunchLayer({ view, anchor, blur = 0, children }: { view: View; anchor: { x: number; y: number }; blur?: number; children: React.ReactNode }) {
  return <div data-film-zoom="" style={{
    position: "absolute", inset: 0, transformOrigin: "0 0",
    transform: `translate(${anchor.x}px, ${anchor.y}px) scale(${view.zoom}) translate(${-view.x}px, ${-view.y}px)`,
    filter: blur > 0.3 ? `blur(${blur.toFixed(2)}px)` : undefined,
  }}>{children}</div>;
}

/** Keys that open on a detail and pull back to the whole surface, dive to each named point on its cue,
 *  pull back after the last one, then punch into the click and back out to show the result. */
export function surfaceKeys({ rest, opener, focus, cues, click, clickAt, frames, openZoom = 1.9, focusZoom = 1.6, clickZoom = 2.1 }: {
  rest: { x: number; y: number }; opener: { x: number; y: number }; focus: { x: number; y: number }[]; cues: number[];
  click?: { x: number; y: number }; clickAt?: number; frames: number; openZoom?: number; focusZoom?: number; clickZoom?: number;
}): PunchKey[] {
  // The pull-back runs past the incoming morph's blur so it reads as a camera move, not part of the cut.
  const keys: PunchKey[] = [{ at: 0, ...opener, zoom: openZoom }, { at: 24, ...rest, zoom: 1, travel: 16 }];
  const named = focus.map((p, i) => ({ p, at: cues[i] })).filter(f => f.at !== undefined && f.at > 20);
  named.forEach(({ p, at }) => keys.push({ at: at + 2, ...p, zoom: focusZoom, travel: 9 }));
  const lastNamed = named.at(-1)?.at;
  const end = frames - 6;
  if (lastNamed !== undefined && (clickAt === undefined || clickAt - lastNamed > 34)) keys.push({ at: Math.min(end, lastNamed + 24), ...rest, zoom: 1, travel: 11 });
  if (click && clickAt !== undefined && clickAt > 20) {
    keys.push({ at: clickAt - 1, ...click, zoom: clickZoom, travel: 10 });
    if (clickAt + 22 < end) keys.push({ at: clickAt + 22, ...rest, zoom: 1.04, travel: 12 });
  }
  return keys.sort((a, b) => a.at - b.at);
}
