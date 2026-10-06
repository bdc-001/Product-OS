import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";
import { Phone, X } from "lucide-react";
import { linesOf, pickupFrame, type Line } from "./CallStage";
import { body, display, FPS, K, progress, ringShake, useLaunch, type LaunchScene, type Ringtone } from "./core";
import { KineticType } from "./Kinetic";

const DIALOGUE = new Set(["agent", "customer", "example"]);
const pad = (n: number) => String(Math.max(0, n)).padStart(2, "0");

function Bars({ global, live, seed }: { global: number; live: boolean; seed: number }) {
  return <div style={{ display: "flex", alignItems: "center", gap: 5, height: 50 }}>
    {Array.from({ length: 22 }, (_, i) => {
      const env = Math.sin((i / 21) * Math.PI);
      const h = live ? 6 + env * (6 + 34 * Math.abs(Math.sin(global * 0.43 + i * 0.8 + seed) * Math.cos(global * 0.11 + i * 0.37))) : 4;
      return <div key={i} style={{ width: 5, height: h, borderRadius: 3, background: live ? K.blue : "#C9D6EE" }} />;
    })}
  </div>;
}

/** One side of the call: who it is, whether they are speaking, and the last thing they said. */
function Party({ agent, name, role, line, global, speaking, flagged, dim, width, height }: {
  agent: boolean; name: string; role: string; line?: Line; global: number; speaking: boolean; flagged: boolean; dim: boolean; width: number; height: number;
}) {
  return <div style={{ width, height, borderRadius: 34, background: "#FFFFFF", padding: "34px 36px", display: "flex", flexDirection: "column", gap: 18,
    boxShadow: speaking ? "0 0 0 3px rgba(26,98,242,0.55), 0 40px 90px rgba(10,46,122,0.2)" : "0 30px 80px rgba(10,46,122,0.14), 0 0 0 1px rgba(175,202,251,0.6)",
    border: flagged ? "3px solid #E11D48" : "3px solid transparent", opacity: dim ? 0.5 : 1 }}>
    <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
      <div style={{ width: 84, height: 84, borderRadius: 42, display: "grid", placeItems: "center", flexShrink: 0,
        background: agent ? `linear-gradient(145deg, #5B8DFF, ${K.navy})` : "linear-gradient(160deg,#E9EEF8,#B8C6E0)",
        boxShadow: speaking ? "0 0 0 10px rgba(26,98,242,0.14)" : "none" }}>
        {agent
          ? <Img src={staticFile("brand-mark.svg")} style={{ width: 46, filter: "brightness(0) invert(1)" }} />
          : <span style={{ fontFamily: display, fontWeight: 700, fontSize: 32, color: K.navy }}>{name.split(/\s+/).map(w => w[0]).join("").slice(0, 2).toUpperCase()}</span>}
      </div>
      <div style={{ minWidth: 0 }}>
        <div data-film-text="label" style={{ fontFamily: display, fontSize: 32, fontWeight: 650, color: K.ink, whiteSpace: "nowrap" }}>{name}</div>
        <div style={{ fontSize: 20, color: K.muted, marginTop: 4, letterSpacing: 1.2, textTransform: "uppercase", fontWeight: 600 }}>{role}</div>
      </div>
    </div>
    <Bars global={global} live={speaking} seed={agent ? 0 : 2.1} />
    <div style={{ flex: 1, fontSize: 29, lineHeight: 1.38, color: K.ink, overflow: "hidden" }}>
      {line?.words.map((w, i) => <React.Fragment key={i}><span style={{ opacity: progress(global, w.at - 2, 4) }}>{w.word}</span>{i < line.words.length - 1 ? " " : ""}</React.Fragment>)}
    </div>
  </div>;
}

/** The call as two people on one line: the AI agent and the customer face each other, the line between them pulses
 *  toward whoever is listening, and the badge in the middle rings, connects and counts. */
export function SplitCall({ block, global, ring }: { block: LaunchScene[]; global: number; ring?: Ringtone }) {
  const { audioFrom, portrait } = useLaunch();
  const lines = linesOf(block, audioFrom);
  const start = block[0].from;
  const active = [...block].reverse().find(s => global >= s.from) ?? block[0];
  const lastEnd = lines.length ? lines[lines.length - 1].end : start + 30;
  const hangupAt = block.find(s => s.hangupFrame !== undefined)?.hangupFrame ?? lastEnd + 8;
  const ended = global >= hangupAt;
  const pickup = pickupFrame(block, lines);
  const ringing = pickup !== null && global < pickup;
  const review = DIALOGUE.has(active.voice || "") ? null : active;
  const reviewIn = review ? progress(global - review.from, 0, 14) : 0;
  const flaggedIndex = review ? lines.map(l => l.scene.voice).lastIndexOf("agent") : -1;
  const context = block.find(s => s.screen)?.screen || {};
  const caller = context.title || "Customer";
  const answered = pickup ?? start - 3 * FPS;
  const clock = Math.max(0, Math.floor((Math.min(global, hangupAt) - answered) / FPS));
  const now = lines.find(l => global >= l.start - 1 && global <= l.end + 2);
  const heard = lines.filter(l => global >= l.start - 4);
  const lastOf = (agent: boolean) => [...heard].reverse().find(l => (l.scene.voice === "agent") === agent);
  const agentLine = lastOf(true), customerLine = lastOf(false);
  const flagged = review && reviewIn > 0.3 && lines[flaggedIndex] === agentLine;
  const enterA = progress(global - start, 0, 18), enterB = progress(global - start, 6, 18);
  const lift = reviewIn * (portrait ? 0 : 70);
  const cardW = portrait ? 900 : 600, cardH = portrait ? 470 : 470;
  const A: React.CSSProperties = portrait ? { left: 90, top: 330 } : { left: 140, top: 270 };
  const B: React.CSSProperties = portrait ? { left: 90, top: 1130 } : { left: 1180, top: 270 };
  const badge = portrait ? { x: 540, y: 965 } : { x: 960, y: 505 };
  const toward = now ? (now.scene.voice === "agent" ? 1 : -1) : 0;
  const beat = ringing ? Math.abs(Math.sin((global - start) / 5)) : 0;
  const shake = ringShake(global - start, ringing, ring);
  return <AbsoluteFill style={{ fontFamily: body }}>
    <svg width={portrait ? 1080 : 1920} height={portrait ? 1920 : 1080} style={{ position: "absolute", inset: 0 }}>
      {portrait
        ? <line x1={540} y1={800} x2={540} y2={1130} stroke="#AFCAFB" strokeWidth={3} strokeDasharray="2 12" strokeLinecap="round" />
        : <line x1={740} y1={505 + lift} x2={1180} y2={505 + lift} stroke="#AFCAFB" strokeWidth={3} strokeDasharray="2 12" strokeLinecap="round" />}
      {toward !== 0 && !ended && [0, 1, 2].map(k => {
        const t = (((global + k * 9) % 27) / 27);
        const p = toward > 0 ? t : 1 - t;
        const cx = portrait ? 540 : 740 + p * 440, cy = portrait ? 800 + p * 330 : 505 + lift;
        return <circle key={k} cx={cx} cy={cy} r={7} fill={K.blue} opacity={Math.sin(t * Math.PI)} />;
      })}
    </svg>
    <div style={{ position: "absolute", ...A, opacity: enterA, transform: `translate(${(1 - enterA) * -50}px, ${lift}px)` }}>
      <Party agent name={context.speaker || "AI agent"} role="Voice agent" line={agentLine} global={global} speaking={now?.scene.voice === "agent" && !ended}
        flagged={!!flagged} dim={!!review && reviewIn > 0.3 && !flagged} width={cardW} height={cardH} />
    </div>
    <div style={{ position: "absolute", ...B, opacity: enterB, transform: `translate(${(1 - enterB) * 50 + shake}px, ${lift}px)` }}>
      <Party agent={false} name={caller} role={context.subtitle || "Customer"} line={customerLine} global={global} speaking={!!now && now.scene.voice !== "agent" && !ended}
        flagged={false} dim={!!review && reviewIn > 0.3} width={cardW} height={cardH} />
    </div>
    <div style={{ position: "absolute", left: badge.x, top: badge.y + lift, transform: "translate(-50%, -50%)", display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
      <div style={{ width: 96, height: 96, borderRadius: 48, display: "grid", placeItems: "center",
        background: ended ? "#FF3B30" : ringing ? "#34C759" : K.blue,
        boxShadow: ringing ? `0 0 0 ${10 + beat * 26}px rgba(52,199,89,${0.3 - beat * 0.2})` : "0 18px 40px rgba(26,98,242,0.35)" }}>
        <Phone size={42} color="#FFFFFF" fill="#FFFFFF" style={{ transform: ended ? "rotate(135deg)" : `rotate(${ringing ? Math.sin(global / 2.2) * beat * 14 : 0}deg)` }} />
      </div>
      <div data-film-text="label" style={{ padding: "8px 16px", borderRadius: 999, background: "#FFFFFF", boxShadow: "0 8px 20px rgba(10,46,122,0.12)", fontSize: 20, fontWeight: 700, letterSpacing: 1, color: ended ? K.muted : ringing ? "#15803D" : K.ink, fontVariantNumeric: "tabular-nums", whiteSpace: "nowrap" }}>
        {ended ? "CALL ENDED" : ringing ? "RINGING" : `LIVE ${pad(Math.floor(clock / 60))}:${pad(clock % 60)}`}
      </div>
    </div>
    {review && <div style={{ position: "absolute", left: portrait ? 90 : 140, width: portrait ? 900 : 1640, top: portrait ? 160 : 120, opacity: reviewIn }}>
      <KineticType scene={review} frame={global - review.from} field="stage" size={portrait ? 56 : 54} align="left" maxWidth={portrait ? 900 : 1640} />
    </div>}
    {review && <div style={{ position: "absolute", left: portrait ? 90 : 140, top: portrait ? 1650 : 900, display: "flex", flexWrap: "wrap", gap: 10, width: portrait ? 900 : 1640 }}>
      {(review.labels || []).map((label, i) => {
        const p = progress(global - review.from, review.labelFrames?.[i] ?? 10 + i * 12, 10);
        return <span key={i} data-film-text="label" style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "9px 15px", borderRadius: 999, background: "#FFE4E8", color: "#BE123C", fontSize: 21, fontWeight: 600, opacity: p, transform: `scale(${0.85 + p * 0.15})` }}>
          <X size={18} strokeWidth={3} />{label}
        </span>;
      })}
    </div>}
  </AbsoluteFill>;
}
