import React from "react";
import { AbsoluteFill } from "remotion";
import { FPS } from "../core";
import { A } from "./tokens";

function Glow({ x, y, w, h, color, blur }: { x: number; y: number; w: number; h: number; color: string; blur: number }) {
  return <div style={{
    position: "absolute", left: `${x}%`, top: `${y}%`, width: w, height: h, borderRadius: "50%", transform: "translate(-50%, -50%)",
    background: `radial-gradient(ellipse at center, ${color} 0%, transparent 70%)`, filter: `blur(${blur}px)`,
  }} />;
}

/** The airy field: off-white, with two or three large blue glows drifting slowly along the bottom edge on the
 *  film clock. No grain and no hard bands; `lift` raises the glow behind a centred object. */
export function AuraField({ global, portrait, lift = 0 }: { global: number; portrait: boolean; lift?: number }) {
  const t = global / FPS;
  const w = portrait ? 1500 : 2100;
  return <AbsoluteFill style={{ overflow: "hidden", background: `linear-gradient(180deg, #FFFFFF 0%, ${A.field} 55%, #F3F6FE 100%)` }}>
    <Glow x={24 + Math.sin(t * 0.42) * 14} y={106 - lift * 30 + Math.sin(t * 0.6) * 3} w={w * 0.7} h={portrait ? 760 : 620} color="rgba(127,168,255,0.62)" blur={90} />
    <Glow x={72 + Math.cos(t * 0.36) * 13} y={110 - lift * 26 + Math.cos(t * 0.5) * 3} w={w * 0.62} h={portrait ? 700 : 560} color="rgba(167,195,255,0.7)" blur={100} />
    <Glow x={50 + Math.sin(t * 0.3 + 1.3) * 20} y={118 - lift * 20} w={w * 0.5} h={portrait ? 560 : 420} color="rgba(26,98,242,0.28)" blur={110} />
    {lift > 0 && <Glow x={50} y={52} w={portrait ? 900 : 1100} h={portrait ? 900 : 760} color={`rgba(214,228,255,${0.75 * lift})`} blur={90} />}
    <Glow x={-6} y={-12} w={portrait ? 700 : 900} h={500} color="rgba(233,239,255,0.9)" blur={80} />
  </AbsoluteFill>;
}
