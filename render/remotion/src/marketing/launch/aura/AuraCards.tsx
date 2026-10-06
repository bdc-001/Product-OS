import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";
import { seeded, useLaunch, type LaunchScene } from "../core";
import { AuraType, BlurPhrase, phraseCues } from "./motion";
import { Gem, GEMS } from "./objects";
import { A, along, auraSans, glide, rise, springAt } from "./tokens";

/** Frame the gems collapse into the mark, before they burst back out. */
const CONVERGE = 13;

/** The reveal: a swarm of gems streams in and collapses into the brand mark, which lands with a shockwave and
 *  throws the swarm back out; then the feature name blurs in under it. */
export function AuraPresenting({ scene, frame }: { scene: LaunchScene; frame: number }) {
  const { portrait, product, module, audioFrom } = useLaunch();
  const cues = phraseCues(scene, scene.headline, audioFrom);
  const nameAt = Math.max(CONVERGE + 10, (cues[0]?.at ?? 18) - 4);
  const land = springAt(frame, CONVERGE - 2, { damping: 11 });
  const lift = glide(frame, nameAt - 8, 14);
  const cx = portrait ? 540 : 960, cy = portrait ? 900 : 520;
  const rx = portrait ? 380 : 760, ry = portrait ? 640 : 360;
  const gems = Array.from({ length: portrait ? 14 : 18 }, (_, i) => {
    const angle = seeded(i + 3) * Math.PI * 2;
    const reach = 0.72 + seeded(i + 41) * 0.55;
    const size = 46 + seeded(i + 13) * 96;
    const far = size < 70;
    const spin = seeded(i + 21) * 50 + frame * (seeded(i + 5) - 0.5) * (frame < CONVERGE ? 9 : 1.4);
    let x: number, y: number, scale: number, seen: number;
    if (frame < CONVERGE) {
      // Inbound along a curl, so the swarm swirls into the mark rather than sliding straight in.
      const c = glide(frame, -2 + seeded(i + 17) * 4, CONVERGE - 1);
      const a = angle + (1 - c) * 1.4, d = (1 - c) * (0.9 + seeded(i + 29) * 0.5);
      x = cx + Math.cos(a) * rx * d; y = cy + Math.sin(a) * ry * d;
      scale = 0.35 + 0.65 * (1 - c); seen = Math.min(1, (1 - c) * 12);
    } else {
      const burst = rise(frame, CONVERGE + seeded(i + 7) * 4, 16);
      const drift = (frame - CONVERGE) * 0.9 * (0.5 + seeded(i + 9));
      x = cx + Math.cos(angle) * (rx * reach + drift) * burst + Math.sin(frame / 30 + i) * 6;
      y = cy + Math.sin(angle) * (ry * reach + drift * 0.6) * burst + Math.cos(frame / 34 + i) * 6;
      scale = 0.3 + 0.7 * burst; seen = Math.min(1, burst * 2);
    }
    return <div key={i} style={{ position: "absolute", left: x - size / 2, top: y - size / 2, opacity: seen * (far ? 0.75 : 1),
      filter: far || frame < CONVERGE ? "blur(1.6px)" : undefined, transform: `scale(${scale})` }}>
      <Gem kind={GEMS[i % GEMS.length]} size={size} tint={i} spin={spin} />
    </div>;
  });
  const shock = rise(frame, CONVERGE - 1, 22);
  const markSize = portrait ? 230 : 210;
  return <AbsoluteFill>
    {shock > 0 && shock < 1 && <div style={{ position: "absolute", left: cx - 600, top: cy - 600, width: 1200, height: 1200, borderRadius: "50%",
      border: `2px solid rgba(26,98,242,${(0.4 * (1 - shock)).toFixed(3)})`, background: `radial-gradient(circle, rgba(127,168,255,${(0.28 * (1 - shock)).toFixed(3)}) 0%, rgba(127,168,255,0) 60%)`,
      transform: `scale(${0.1 + shock * 1.1})` }} />}
    {gems}
    <div style={{ position: "absolute", left: cx - markSize / 2, top: cy - markSize * 0.3, width: markSize, transform: `translateY(${-lift * (portrait ? 190 : 150)}px) scale(${(0.4 + 0.6 * land) * (1 - lift * 0.28)})`, opacity: Math.min(1, land * 1.5) }}>
      <Img src={staticFile("brand-mark.svg")} style={{ width: markSize, filter: "drop-shadow(0 18px 40px rgba(26,98,242,0.3))" }} />
    </div>
    <div style={{ position: "absolute", left: 0, right: 0, top: cy + (portrait ? 30 : 10), display: "flex", flexDirection: "column", alignItems: "center", gap: portrait ? 30 : 24, padding: portrait ? "0 70px" : "0 160px" }}>
      <BlurPhrase scene={scene} frame={frame} cues={cues} size={portrait ? 104 : 120} weight={300} />
      <div data-film-text="label" style={{ fontFamily: auraSans, fontSize: portrait ? 28 : 24, fontWeight: 500, letterSpacing: "0.32em", textTransform: "uppercase", color: A.muted,
        opacity: rise(frame, (cues.at(-1)?.at ?? nameAt) + 6, 10) }}>{product || module}</div>
    </div>
  </AbsoluteFill>;
}

/** The close on white: the mark, the wordmark sliding out of it, then the tagline blurring in underneath. */
export function AuraEndCard({ scene, frame }: { scene: LaunchScene; frame: number }) {
  const { portrait, title, audioFrom } = useLaunch();
  const product = (title.split(":")[0] || title).trim();
  const cues = phraseCues(scene, scene.headline, audioFrom);
  const width = portrait ? 500 : 540;
  const markFrac = 0.29;
  const land = springAt(frame, 0, { damping: 12 });
  const open = glide(frame, 7, 14);
  const badge = rise(frame, (cues.at(-1)?.at ?? 24) + 6, 10);
  const drift = 0.98 + 0.07 * along(frame, scene.frames);
  return <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", flexDirection: "column", gap: portrait ? 70 : 54, padding: portrait ? "0 80px" : "0 180px", transform: `scale(${drift})` }}>
    <div style={{ width, transform: `translateX(${(1 - open) * width * (0.5 - markFrac / 2)}px) scale(${0.6 + 0.4 * land})`, opacity: Math.min(1, land * 1.5),
      clipPath: `inset(-10% ${((1 - open) * (1 - markFrac) * 100).toFixed(2)}% -10% 0)` }}>
      <Img src={staticFile("brand-logo-light.svg")} style={{ width, display: "block" }} />
    </div>
    <AuraType scene={scene} frame={frame} size={portrait ? 84 : 80} maxWidth={portrait ? 920 : 1400} />
    <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "12px 26px 12px 14px", borderRadius: 999, background: "#FFFFFF",
      boxShadow: "0 14px 40px rgba(26,98,242,0.14), inset 0 1px 0 #FFFFFF", border: "1px solid rgba(214,228,255,0.9)", opacity: badge, filter: badge < 1 ? `blur(${(1 - badge) * 8}px)` : undefined }}>
      <Img src={staticFile("brand-mark.svg")} style={{ width: 44 }} />
      <span data-film-text="badge" style={{ fontFamily: auraSans, fontSize: portrait ? 32 : 28, fontWeight: 500, color: A.ink, letterSpacing: "-0.01em" }}>{product}</span>
    </div>
    {scene.body && <div data-film-text="body" style={{ fontFamily: auraSans, fontSize: portrait ? 28 : 24, fontWeight: 400, color: A.muted, textAlign: "center", opacity: rise(frame, (cues.at(-1)?.at ?? 24) + 12, 10) }}>{scene.body}</div>}
  </AbsoluteFill>;
}
