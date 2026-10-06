import React from "react";
import { AbsoluteFill } from "remotion";
import { Phone } from "lucide-react";
import { linesOf, pickupFrame, type Line } from "../CallStage";
import { FPS, useLaunch, type LaunchScene, type Ringtone } from "../core";
import { AuraField } from "./AuraField";
import { AuraType, dissolveStyle } from "./motion";
import { Rings, strandY, Strands } from "./objects";
import { A, auraSans, glide, rise, springAt } from "./tokens";

const DIALOGUE = new Set(["agent", "customer", "example"]);
const pad = (n: number) => String(Math.max(0, n)).padStart(2, "0");

/** One turn as a floating caption: each word blurs in as it is heard. */
function Caption({ line, global, size, out }: { line: Line; global: number; size: number; out: number }) {
  const agent = line.scene.voice === "agent";
  const speaker = line.scene.screen?.speaker || (agent ? "AI agent" : line.scene.screen?.title || "Customer");
  return <div style={{ textAlign: "center", ...dissolveStyle(out) }}>
    <div style={{ fontFamily: auraSans, fontSize: 20, fontWeight: 500, letterSpacing: "0.24em", textTransform: "uppercase", color: agent ? A.blue : A.muted, marginBottom: 18,
      opacity: rise(global, line.start - 8, 10) }}>{speaker}</div>
    <div data-film-text="caption" style={{ fontFamily: auraSans, fontWeight: 300, fontSize: size, lineHeight: 1.2, letterSpacing: "-0.02em", color: A.ink, textWrap: "balance" }}>
      {line.words.map((w, i) => {
        const p = rise(global, w.at - 2, 6);
        return <React.Fragment key={i}><span style={{ display: "inline-block", opacity: 0.12 + 0.88 * p, filter: p < 1 ? `blur(${(1 - p) * 6}px)` : undefined }}>{w.word}</span>{i < line.words.length - 1 ? " " : ""}</React.Fragment>;
      })}
    </div>
  </div>;
}

/** The call without a device: strands carry a dot in while it rings, the dot grows into the call button with
 *  pulsing rings while the turns float in as captions, and on hang-up the button fills the frame white. */
export function AuraCall({ block, global }: { block: LaunchScene[]; global: number; ring?: Ringtone }) {
  const { audioFrom, portrait } = useLaunch();
  const W = portrait ? 1080 : 1920, H = portrait ? 1920 : 1080;
  const lines = linesOf(block, audioFrom);
  const start = block[0].from;
  const active = [...block].reverse().find(s => global >= s.from) ?? block[0];
  const lastEnd = lines.length ? lines[lines.length - 1].end : start + 30;
  const hangupAt = block.find(s => s.hangupFrame !== undefined)?.hangupFrame ?? lastEnd + 8;
  const ended = global >= hangupAt;
  const pickup = pickupFrame(block, lines);
  const answered = pickup ?? start + 6;
  const ringing = global < answered;
  const talking = lines.find(l => global >= l.start - 1 && global <= l.end + 2);
  const review = DIALOGUE.has(active.voice || "") ? null : active;
  const context = block.find(s => s.screen)?.screen || {};
  const caller = context.title || "Customer";
  const by = portrait ? 760 : 420;
  const dotX = W / 2 * glide(global - start, 0, Math.max(12, answered - start - 2));
  const dotY = strandY(dotX, 0, W, 320, global, 46) - 160 + by;
  const grow = springAt(global, answered - 4, { damping: 11 });
  const button = (portrait ? 176 : 164) * (0.14 + 0.86 * grow);
  const amp = ended ? 0 : ringing ? 46 : talking ? 64 + 26 * Math.abs(Math.sin(global / 5)) : 30;
  const fill = ended ? glide(global, hangupAt + 2, 12) : 0;
  const clock = Math.max(0, Math.floor((Math.min(global, hangupAt) - answered) / FPS));
  const current = [...lines].reverse().find(l => global >= l.start - 6);
  const enter = rise(global - start, 0, 10);
  const capSize = portrait ? 56 : 54;
  return <AbsoluteFill>
    <div style={{ position: "absolute", left: 0, top: by - 160, width: W, height: 320, opacity: enter * (1 - fill), transform: `scaleY(${0.6 + 0.4 * enter})` }}>
      <Strands width={W} height={320} global={global} amp={amp} />
    </div>
    {ringing && <div style={{ position: "absolute", left: dotX - 13, top: dotY - 13, width: 26, height: 26, borderRadius: "50%", background: "#FFFFFF",
      boxShadow: `0 0 0 6px rgba(127,168,255,0.35), 0 0 34px 10px rgba(26,98,242,0.45)`, opacity: enter }} />}
    {!ringing && <div style={{ position: "absolute", left: W / 2, top: by, width: 0, height: 0 }}>
      <Rings size={button} global={global} active={ended ? 0 : talking ? 1 : 0.35} />
      <div style={{ position: "absolute", left: -button / 2, top: -button / 2, width: button, height: button, borderRadius: "50%", display: "grid", placeItems: "center",
        background: `radial-gradient(circle at 34% 28%, #A7C3FF 0%, ${A.blue} 55%, #144ECF 100%)`,
        boxShadow: `inset 0 3px 0 rgba(255,255,255,0.45), 0 30px 70px rgba(26,98,242,${talking ? 0.45 : 0.3})`, transform: `scale(${talking && !ended ? 1 + 0.03 * Math.sin(global / 3) : 1})` }}>
        <Phone size={button * 0.36} color="#FFFFFF" strokeWidth={1.8} style={{ transform: ended ? "rotate(135deg)" : undefined }} />
      </div>
    </div>}
    <div style={{ position: "absolute", left: 0, right: 0, top: portrait ? 240 : 96, display: "flex", justifyContent: "center", opacity: enter * (1 - fill) }}>
      <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "10px 22px", borderRadius: 999, background: "rgba(255,255,255,0.8)", border: "1px solid rgba(214,228,255,0.9)",
        fontFamily: auraSans, fontSize: 20, fontWeight: 500, color: ended ? A.muted : ringing ? A.blue : "#D93025", boxShadow: "0 10px 30px rgba(26,98,242,0.1)" }}>
        <span style={{ width: 9, height: 9, borderRadius: 5, background: "currentColor", opacity: ended ? 1 : 0.5 + 0.5 * Math.abs(Math.sin(global / 8)) }} />
        <span style={{ letterSpacing: "0.12em", textTransform: "uppercase" }}>{ended ? "Call ended" : ringing ? `Incoming · ${caller}` : `Live ${pad(Math.floor(clock / 60))}:${pad(clock % 60)}`}</span>
        <span style={{ fontSize: 13, letterSpacing: "0.16em", color: A.muted, borderLeft: `1px solid ${A.rule}`, paddingLeft: 14 }}>ILLUSTRATIVE</span>
      </div>
    </div>
    <div style={{ position: "absolute", left: portrait ? 70 : 240, right: portrait ? 70 : 240, top: by + (portrait ? 240 : 190), display: "grid", justifyItems: "center", opacity: 1 - fill }}>
      {lines.map((line, i) => {
        const next = lines[i + 1];
        const shown = current === line || (current && lines.indexOf(current) === i + 1 && global < next!.start + 4);
        if (!shown) return null;
        const out = next ? glide(global, next.start - 6, 8) : 0;
        return <div key={i} style={{ gridArea: "1 / 1" }}><Caption line={line} global={global} size={capSize} out={out} /></div>;
      })}
    </div>
    {fill > 0 && <AbsoluteFill style={{ clipPath: `circle(${(fill * 74).toFixed(2)}% at 50% ${(by / H * 100).toFixed(1)}%)` }}>
      <AuraField global={global} portrait={portrait} />
      {review && <ReviewCard scene={review} global={global} />}
    </AbsoluteFill>}
  </AbsoluteFill>;
}

/** The narrator's review of the call, on the white the button filled: the point, then the failing results. */
function ReviewCard({ scene, global }: { scene: LaunchScene; global: number }) {
  const { portrait } = useLaunch();
  const frame = global - scene.from;
  return <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", flexDirection: "column", gap: portrait ? 60 : 48, padding: portrait ? "0 70px" : "0 200px" }}>
    <AuraType scene={scene} frame={frame} size={portrait ? 80 : 84} />
    <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", gap: 16 }}>
      {(scene.labels || []).map((label, i) => {
        const p = rise(frame, scene.labelFrames?.[i] ?? 10 + i * 12, 14);
        return <span key={i} data-film-text="label" style={{ display: "inline-flex", alignItems: "center", gap: 12, padding: "14px 24px", borderRadius: 999, background: "#FFFFFF",
          border: "1px solid rgba(254,205,211,0.9)", boxShadow: "0 14px 34px rgba(190,18,60,0.1)", fontFamily: auraSans, fontSize: portrait ? 28 : 26, color: A.ink,
          opacity: p, filter: p < 1 ? `blur(${(1 - p) * 8}px)` : undefined, transform: `translateY(${(1 - p) * 14}px)` }}>
          <span style={{ width: 10, height: 10, borderRadius: 5, background: "#E11D48" }} />{label}
        </span>;
      })}
    </div>
    {scene.body && <div data-film-text="body" style={{ fontFamily: auraSans, fontSize: portrait ? 28 : 24, color: A.muted, textAlign: "center", maxWidth: 1100,
      opacity: rise(frame, (scene.labelFrames?.at(-1) ?? 24) + 10, 14) }}>{scene.body}</div>}
  </AbsoluteFill>;
}
