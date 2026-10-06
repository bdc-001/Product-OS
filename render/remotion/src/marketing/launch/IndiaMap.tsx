import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";
import { body, display, FPS, K, progress, useLaunch, type LaunchScene } from "./core";
import { INDIA_HUB, INDIA_PATH, INDIA_VIEW, PLACES } from "./indiaGeo";
import { KineticType } from "./Kinetic";

const bez = (a: number, c: number, b: number, t: number) => (1 - t) * (1 - t) * a + 2 * (1 - t) * t * c + t * t * b;

/** India draws itself, the agent's hub lights in the Bay of Bengal, and each language or city pins on its cue with an
 *  arc from the hub, as in the reference multilingual film. Labels resolve through PLACES; unknown ones are skipped. */
export function IndiaMap({ scene, frame, global }: { scene: LaunchScene; frame: number; global: number }) {
  const { portrait } = useLaunch();
  const scale = portrait ? 0.95 : 0.92;
  const box = portrait ? { left: (1080 - INDIA_VIEW.w * scale) / 2, top: 800 } : { left: 960, top: (1080 - INDIA_VIEW.h * scale) / 2 };
  const draw = progress(frame, 0, 40);
  const fill = progress(frame, 22, 26);
  const hubIn = progress(frame, 14, 14);
  const t = global / FPS;
  const pins = (scene.labels || []).map((label, i) => ({ label, at: scene.labelFrames?.[i] ?? 34 + i * 20, place: PLACES[label.trim().toLowerCase()] }))
    .filter(pin => pin.place);
  return <AbsoluteFill style={{ fontFamily: body, overflow: "hidden", background: "linear-gradient(160deg, #FFFFFF 0%, #F6F9FF 55%, #E8F0FF 100%)" }}>
    <AbsoluteFill style={{ opacity: 0.5, backgroundSize: "44px 44px", backgroundPosition: `${(t * 3) % 44}px 0px`,
      backgroundImage: "radial-gradient(circle, rgba(127,168,255,0.45) 1.2px, transparent 1.6px)",
      maskImage: "radial-gradient(ellipse at 70% 50%, black 0%, transparent 70%)", WebkitMaskImage: "radial-gradient(ellipse at 70% 50%, black 0%, transparent 70%)" }} />
    <div style={{ position: "absolute", ...(portrait ? { left: 70, width: 940, top: 230 } : { left: 140, width: 760, top: 0, bottom: 0 }), display: "flex", alignItems: "center" }}>
      <KineticType scene={scene} frame={frame} field="light" size={portrait ? 80 : 76} align="left" maxWidth={portrait ? 940 : 760} />
    </div>
    <div style={{ position: "absolute", ...box, width: INDIA_VIEW.w * scale, height: INDIA_VIEW.h * scale }}>
      <svg viewBox={`0 0 ${INDIA_VIEW.w} ${INDIA_VIEW.h}`} width="100%" height="100%" style={{ overflow: "visible" }}>
        <defs>
          <pattern id="india-dots" width="14" height="14" patternUnits="userSpaceOnUse">
            <circle cx="7" cy="7" r="2.6" fill="#7FA8FF" />
          </pattern>
          <linearGradient id="india-fill" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#EEF4FF" />
            <stop offset="100%" stopColor="#D1E1FD" />
          </linearGradient>
        </defs>
        <path d={INDIA_PATH} fill="url(#india-fill)" opacity={fill} />
        <path d={INDIA_PATH} fill="url(#india-dots)" opacity={fill * 0.55} />
        <path d={INDIA_PATH} fill="none" stroke={K.blue} strokeWidth={2.4} strokeLinejoin="round" pathLength={1} strokeDasharray="1" strokeDashoffset={1 - draw} />
        {pins.map(({ place, at }, i) => {
          const p = progress(frame, at - 6, 16);
          const cx = (INDIA_HUB.x + place.x) / 2 + (place.y - INDIA_HUB.y) * 0.25, cy = (INDIA_HUB.y + place.y) / 2 - (place.x - INDIA_HUB.x) * 0.25 - 60;
          const travel = ((global + i * 11) % 40) / 40;
          return <g key={i}>
            <path d={`M${INDIA_HUB.x} ${INDIA_HUB.y} Q${cx} ${cy} ${place.x} ${place.y}`} fill="none" stroke={K.blue} strokeWidth={2.6} strokeLinecap="round"
              pathLength={1} strokeDasharray="1" strokeDashoffset={1 - p} opacity={0.85} />
            {p >= 1 && <circle cx={bez(INDIA_HUB.x, cx, place.x, travel)} cy={bez(INDIA_HUB.y, cy, place.y, travel)} r={6} fill={K.blue} opacity={Math.sin(travel * Math.PI)} />}
          </g>;
        })}
        {pins.map(({ place, at }, i) => {
          const land = progress(frame, at + 4, 12);
          const ripple = ((frame - at - 4) % 36) / 36;
          return <g key={i} opacity={land}>
            {frame > at + 4 && <circle cx={place.x} cy={place.y} r={12 + ripple * 34} fill="none" stroke={K.blue} strokeWidth={2} opacity={1 - ripple} />}
            <circle cx={place.x} cy={place.y} r={11 * land} fill={K.blue} stroke="#FFFFFF" strokeWidth={4} />
          </g>;
        })}
        <g opacity={hubIn} transform={`translate(${INDIA_HUB.x} ${INDIA_HUB.y}) scale(${0.7 + hubIn * 0.3})`}>
          {[0, 1].map(k => {
            const r = ((frame + k * 20) % 40) / 40;
            return <circle key={k} r={40 + r * 40} fill="none" stroke={K.blue} strokeWidth={1.5} opacity={(1 - r) * 0.6} />;
          })}
          <circle r={40} fill={K.blue} />
        </g>
      </svg>
      <Img src={staticFile("brand-mark.svg")} style={{ position: "absolute", left: INDIA_HUB.x * scale - 22, top: INDIA_HUB.y * scale - 22, width: 44, filter: "brightness(0) invert(1)", opacity: hubIn }} />
      {pins.map(({ place, at }, i) => {
        const p = progress(frame, at + 6, 12);
        const right = place.x < 640;
        return <div key={i} style={{ position: "absolute", top: place.y * scale - 30, ...(right ? { left: place.x * scale + 24 } : { right: (INDIA_VIEW.w - place.x) * scale + 24 }),
          display: "flex", flexDirection: "column", alignItems: right ? "flex-start" : "flex-end", padding: "10px 18px", borderRadius: 16, background: "#FFFFFF",
          boxShadow: "0 14px 34px rgba(10,46,122,0.18), 0 0 0 1px rgba(175,202,251,0.7)", opacity: p, transform: `translateY(${(1 - p) * 12}px) scale(${0.9 + p * 0.1})`, whiteSpace: "nowrap" }}>
          <span data-film-text="label" style={{ fontFamily: display, fontWeight: 700, fontSize: 30, color: K.ink }}>{place.name}</span>
          {place.city && <span style={{ fontSize: 18, color: K.muted, fontWeight: 600, letterSpacing: 1.2, textTransform: "uppercase" }}>{place.city}</span>}
        </div>;
      })}
    </div>
  </AbsoluteFill>;
}
