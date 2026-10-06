import React from "react";
import { AbsoluteFill } from "remotion";
import { AudioLines, X } from "lucide-react";
import { linesOf, pickupFrame, type Line } from "./CallStage";
import { body, display, FPS, K, progress, ringShake, useLaunch, type LaunchScene, type Ringtone } from "./core";
import { KineticType } from "./Kinetic";

const DIALOGUE = new Set(["agent", "customer", "example"]);
const pad = (n: number) => String(Math.max(0, n)).padStart(2, "0");
const initials = (name: string) => name.split(/\s+/).map(w => w[0]).join("").slice(0, 2).toUpperCase();

/** One participant as a disc: it swells and rings while that side is speaking, and ripples while the phone rings. */
function Person({ x, y, size, name, role, agent, speaking, ringing, global, enter }: {
  x: number; y: number; size: number; name: string; role: string; agent: boolean; speaking: boolean; ringing: boolean; global: number; enter: number;
}) {
  const swell = speaking ? 1.06 + 0.02 * Math.sin(global / 3) : 1;
  return <div style={{ position: "absolute", left: x - size / 2, top: y - size / 2, width: size, opacity: enter, transform: `translateY(${(1 - enter) * 40}px)` }}>
    <div style={{ position: "relative", width: size, height: size }}>
      {(speaking || ringing) && [0, 1, 2].map(k => {
        const t = ((global + k * 12) % 36) / 36;
        return <div key={k} style={{ position: "absolute", left: "50%", top: "50%", width: size * (1 + t * 0.7), height: size * (1 + t * 0.7), borderRadius: "50%", transform: "translate(-50%, -50%)",
          border: `3px solid ${ringing ? "rgba(52,199,89,0.7)" : agent ? "rgba(26,98,242,0.55)" : "rgba(10,15,31,0.28)"}`, opacity: 1 - t }} />;
      })}
      <div style={{ position: "absolute", inset: 0, borderRadius: "50%", display: "grid", placeItems: "center", transform: `scale(${swell})`,
        background: agent ? "radial-gradient(circle at 30% 25%, #6EA2FF 0%, #1A62F2 55%, #0C3BB0 100%)" : "linear-gradient(150deg, #FFFFFF 0%, #E4EAF5 100%)",
        border: agent ? "none" : "2px solid #D5DEEC", boxShadow: speaking ? `0 30px 80px ${agent ? "rgba(26,98,242,0.45)" : "rgba(10,15,31,0.22)"}` : "0 18px 44px rgba(10,15,31,0.12)" }}>
        {agent ? <AudioLines size={size * 0.38} color="#FFFFFF" strokeWidth={2} />
          : <span style={{ fontFamily: display, fontWeight: 700, fontSize: size * 0.32, color: K.navy }}>{initials(name)}</span>}
      </div>
    </div>
    <div data-film-text="label" style={{ marginTop: 26, textAlign: "center", fontFamily: display, fontWeight: 700, fontSize: 30, color: K.ink, whiteSpace: "nowrap" }}>{name}</div>
    <div style={{ textAlign: "center", fontFamily: body, fontSize: 20, color: K.muted, marginTop: 4, letterSpacing: 1.4, textTransform: "uppercase" }}>{role}</div>
  </div>;
}

/** The voice travelling between the two: a dotted line whose pulses run from whoever is talking. */
function Wire({ from, to, y, global, direction, live }: { from: number; to: number; y: number; global: number; direction: 1 | -1 | 0; live: boolean }) {
  const dots = 22;
  return <div style={{ position: "absolute", left: from, top: y - 4, width: to - from, height: 8, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
    {Array.from({ length: dots }, (_, i) => {
      const phase = direction === 0 ? 0 : ((direction === 1 ? i : dots - 1 - i) - global * 0.45) / 4;
      const pulse = live && direction !== 0 ? 0.5 + 0.5 * Math.cos(phase) : 0;
      return <div key={i} style={{ width: 8, height: 8, borderRadius: 4, background: pulse > 0.75 ? K.blue : "#C9D6EC", transform: `scale(${1 + pulse * 0.5})` }} />;
    })}
  </div>;
}

function Subtitle({ line, global, flagged, size }: { line: Line; global: number; flagged: boolean; size: number }) {
  const agent = line.scene.voice === "agent";
  return <div style={{ textAlign: "center" }}>
    <div style={{ fontFamily: body, fontSize: 19, fontWeight: 700, letterSpacing: 2, textTransform: "uppercase", color: agent ? K.blue : K.muted, marginBottom: 14 }}>
      {line.scene.screen?.speaker || (agent ? "AI agent" : "Customer")}
    </div>
    <div data-film-text="caption" style={{ display: "inline", fontFamily: display, fontWeight: 600, fontSize: size, lineHeight: 1.22, letterSpacing: -size * 0.015, color: K.ink,
      textDecoration: flagged ? "underline" : "none", textDecorationColor: "#FF4D67", textDecorationThickness: 5, textUnderlineOffset: 12 }}>
      {line.words.map((w, i) => <React.Fragment key={i}><span style={{ opacity: 0.18 + 0.82 * progress(global, w.at - 2, 4) }}>{w.word}</span>{i < line.words.length - 1 ? " " : ""}</React.Fragment>)}
    </div>
  </div>;
}

/** The live call without a device: agent and customer face each other, the voice runs between them, and each turn
 *  lands as a large subtitle. A following narrator scene reviews the call in place. */
export function DuetCall({ block, global, ring }: { block: LaunchScene[]; global: number; ring?: Ringtone }) {
  const { audioFrom, portrait } = useLaunch();
  const lines = linesOf(block, audioFrom);
  const start = block[0].from;
  const active = [...block].reverse().find(s => global >= s.from) ?? block[0];
  const lastEnd = lines.length ? lines[lines.length - 1].end : start + 30;
  const hangupAt = block.find(s => s.hangupFrame !== undefined)?.hangupFrame ?? lastEnd + 8;
  const ended = global >= hangupAt;
  const pickup = pickupFrame(block, lines);
  const ringing = pickup !== null && global < pickup;
  const current = [...lines].reverse().find(l => global >= l.start - 4);
  const talking = lines.find(l => global >= l.start - 1 && global <= l.end + 2);
  const review = DIALOGUE.has(active.voice || "") ? null : active;
  const reviewIn = review ? progress(global - review.from, 0, 14) : 0;
  const flagged = review ? [...lines].reverse().find(l => l.scene.voice === "agent") : undefined;
  const context = block.find(s => s.screen)?.screen || {};
  const caller = context.title || "Customer";
  const answered = pickup ?? start - 3 * FPS;
  const clock = Math.max(0, Math.floor((Math.min(global, hangupAt) - answered) / FPS));
  const enter = progress(global - start, 0, 20);
  const shake = ringShake(global - start, ringing, ring);
  const W = portrait ? 1080 : 1920;
  const discY = portrait ? (review ? 470 : 560) : (review ? 330 : 380);
  const size = portrait ? 210 : 220;
  const agentX = portrait ? 270 : 620, customerX = portrait ? 810 : 1300;
  const direction = !talking || ended ? 0 : talking.scene.voice === "agent" ? 1 : -1;
  const status = ended ? "Call ended" : ringing ? "Ringing" : "Live";
  const shown = review ? flagged : current;
  return <AbsoluteFill style={{ background: "radial-gradient(90% 80% at 50% 38%, #FFFFFF 0%, #F2F6FD 55%, #E3ECFA 100%)", overflow: "hidden" }}>
    <div style={{ position: "absolute", left: W / 2 - 520, top: discY - 520, width: 1040, height: 1040, borderRadius: "50%", border: "1.5px solid rgba(26,98,242,0.08)" }} />
    {!review && <div style={{ position: "absolute", left: W / 2, top: portrait ? 260 : 150, transform: "translateX(-50%)", display: "flex", alignItems: "center", gap: 12, padding: "10px 22px", borderRadius: 999,
      background: ended ? "#E8EDF5" : ringing ? "rgba(52,199,89,0.14)" : "rgba(255,59,48,0.1)", color: ended ? K.muted : ringing ? "#1E8E3E" : "#D93025",
      fontFamily: body, fontWeight: 700, fontSize: 20, letterSpacing: 1.6, textTransform: "uppercase", opacity: enter }}>
      <span style={{ width: 10, height: 10, borderRadius: 5, background: "currentColor", opacity: ended ? 1 : 0.5 + 0.5 * Math.abs(Math.sin(global / 8)) }} />
      {status}{!ringing && <span style={{ fontVariantNumeric: "tabular-nums", fontWeight: 600, letterSpacing: 1 }}>{` ${pad(Math.floor(clock / 60))}:${pad(clock % 60)}`}</span>}
    </div>}
    {review && <div style={{ position: "absolute", left: portrait ? 70 : 200, right: portrait ? 70 : 200, top: portrait ? 210 : 96, display: "flex", justifyContent: "center", opacity: reviewIn }}>
      <KineticType scene={review} frame={global - review.from} field="light" size={portrait ? 64 : 62} />
    </div>}
    <div style={{ position: "absolute", inset: 0, transform: `translateX(${shake}px)` }}>
      <Wire from={agentX + size / 2 + 30} to={customerX - size / 2 - 30} y={discY} global={global} direction={direction} live={!ringing && !ended} />
      <Person x={agentX} y={discY} size={size} name={context.speaker && context.speaker !== caller ? context.speaker : "AI agent"} role="Voice agent" agent
        speaking={!ended && talking?.scene.voice === "agent"} ringing={false} global={global} enter={enter} />
      <Person x={customerX} y={discY} size={size} name={caller} role={context.subtitle || "Customer"} agent={false}
        speaking={!ended && !!talking && talking.scene.voice !== "agent"} ringing={ringing} global={global} enter={progress(global - start, 6, 20)} />
    </div>
    <div style={{ position: "absolute", left: portrait ? 70 : 220, right: portrait ? 70 : 220, top: discY + size / 2 + (portrait ? 150 : 130), opacity: ended && !review ? 0.5 : 1 }}>
      {shown && <Subtitle line={shown} global={review ? shown.end + 10 : global} flagged={!!review && reviewIn > 0.3} size={portrait ? 50 : 48} />}
      {review && <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", gap: 12, marginTop: 34 }}>
        {(review.labels || []).map((label, i) => {
          const p = progress(global - review.from, review.labelFrames?.[i] ?? 10 + i * 12, 10);
          return <span key={i} data-film-text="label" style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "10px 18px", borderRadius: 999, background: "#FFE8EC", border: "1.5px solid #FF8095", color: "#B3122E", fontFamily: body, fontSize: 22, fontWeight: 600, opacity: p, transform: `scale(${0.85 + p * 0.15})` }}>
            <X size={18} strokeWidth={3} />{label}
          </span>;
        })}
      </div>}
    </div>
  </AbsoluteFill>;
}
