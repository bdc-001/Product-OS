import React from "react";
import { AbsoluteFill } from "remotion";
import { Mic, Phone, X } from "lucide-react";
import { linesOf, pickupFrame, type Line } from "./CallStage";
import { body, display, FPS, progress, ringShake, useLaunch, type LaunchScene, type Ringtone } from "./core";
import { KineticType } from "./Kinetic";

const DIALOGUE = new Set(["agent", "customer", "example"]);
const pad = (n: number) => String(Math.max(0, n)).padStart(2, "0");

/** Black field with slow glossy blue light, as in the reference call opening. */
function Gloss({ global }: { global: number }) {
  const drift = global / 90;
  const arc = (x: number, y: number, size: number, turn: number, o: number) => <div style={{
    position: "absolute", left: x, top: y, width: size, height: size, borderRadius: "50%", opacity: o,
    background: "conic-gradient(from 180deg, rgba(10,60,220,0) 0deg, #0B4BE0 50deg, #2F7BFF 110deg, #8EB8FF 140deg, #1A62F2 175deg, rgba(10,60,220,0) 230deg)",
    filter: "blur(10px)", transform: `rotate(${turn}deg)`,
    WebkitMaskImage: "radial-gradient(circle, transparent 38%, #000 42%, #000 68%, transparent 73%)",
  }} />;
  return <AbsoluteFill style={{ background: "#000000", overflow: "hidden" }}>
    {arc(-640, 60, 1400, 30 + drift * 14, 1)}
    {arc(900, -700, 1600, 150 - drift * 10, 1)}
    <AbsoluteFill style={{ background: "radial-gradient(ellipse at 40% 50%, rgba(0,0,0,0.35) 20%, rgba(0,0,0,0) 60%)" }} />
  </AbsoluteFill>;
}

function Bars({ global, live, width }: { global: number; live: boolean; width: number }) {
  const bars = 44;
  return <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 4, height: 56, width }}>
    {Array.from({ length: bars }, (_, i) => {
      const env = Math.sin((i / (bars - 1)) * Math.PI);
      const h = live ? 6 + env * (8 + 40 * Math.abs(Math.sin(global * 0.41 + i * 0.9) * Math.cos(global * 0.13 + i * 0.31))) : 4;
      return <div key={i} style={{ width: 4, height: h, borderRadius: 2, background: live ? "#DCE7FF" : "rgba(255,255,255,0.3)" }} />;
    })}
  </div>;
}

function Caption({ line, global, flagged, dim }: { line: Line; global: number; flagged: boolean; dim: boolean }) {
  const agent = line.scene.voice === "agent";
  const enter = progress(global, line.start - 4, 8);
  return <div style={{ opacity: enter * (dim ? 0.4 : 1), transform: `translateY(${(1 - enter) * 16}px)` }}>
    <div style={{ fontSize: 17, fontWeight: 700, letterSpacing: 1.6, color: agent ? "#8FB4FF" : "rgba(255,255,255,0.6)", marginBottom: 8, textTransform: "uppercase" }}>
      {line.scene.screen?.speaker || (agent ? "AI agent" : "Customer")}
    </div>
    <div style={{ fontSize: 30, lineHeight: 1.38, color: "#FFFFFF", padding: flagged ? "10px 16px" : 0, borderRadius: 14, border: flagged ? "2px solid #FF6B81" : "none", background: flagged ? "rgba(255,107,129,0.12)" : "none" }}>
      {line.words.map((w, i) => <React.Fragment key={i}><span style={{ opacity: progress(global, w.at - 2, 4) }}>{w.word}</span>{i < line.words.length - 1 ? " " : ""}</React.Fragment>)}
    </div>
  </div>;
}

/** The live call as a glass card: it rings, is answered, runs its timer and waveform, and carries a live transcript. */
export function GlassCall({ block, global, ring }: { block: LaunchScene[]; global: number; ring?: Ringtone }) {
  const { audioFrom, portrait } = useLaunch();
  const lines = linesOf(block, audioFrom);
  const start = block[0].from;
  const active = [...block].reverse().find(s => global >= s.from) ?? block[0];
  const lastEnd = lines.length ? lines[lines.length - 1].end : start + 30;
  const hangupAt = block.find(s => s.hangupFrame !== undefined)?.hangupFrame ?? lastEnd + 8;
  const ended = global >= hangupAt;
  const pickup = pickupFrame(block, lines);
  const ringing = pickup !== null && global < pickup;
  const speaking = lines.some(l => global >= l.start - 1 && global <= l.end + 2);
  const review = DIALOGUE.has(active.voice || "") ? null : active;
  const reviewIn = review ? progress(global - review.from, 0, 14) : 0;
  const flaggedIndex = review ? lines.map(l => l.scene.voice).lastIndexOf("agent") : -1;
  const context = block.find(s => s.screen)?.screen || {};
  const caller = context.title || "Customer";
  const answered = pickup ?? start - 3 * FPS;
  const clock = Math.max(0, Math.floor((Math.min(global, hangupAt) - answered) / FPS));
  const enter = progress(global - start, 0, 18);
  const beat = ringing ? Math.abs(Math.sin(global / 4.5)) : 0;
  const status = ended ? "Call ended" : ringing ? (global - start < 26 ? "Incoming call" : "Connecting…") : "Connected";
  const card: React.CSSProperties = portrait
    ? { left: 90, width: 900, top: 230, height: 560 }
    : { left: 150, width: 820, top: 250, height: 540 };
  const shown = lines.filter(l => global >= l.start - 4).slice(-3);
  return <AbsoluteFill>
    <Gloss global={global} />
    <div style={{ position: "absolute", ...card, borderRadius: 30, background: "rgba(255,255,255,0.07)", border: "1.5px solid rgba(255,255,255,0.32)",
      backdropFilter: "blur(26px)", boxShadow: "0 40px 120px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.25)",
      color: "#FFFFFF", fontFamily: body, opacity: enter, transform: `translate(${ringShake(global - start, ringing, ring)}px, ${(1 - enter) * 40}px) scale(${0.97 + enter * 0.03})`, padding: "34px 40px",
      display: "flex", flexDirection: "column", alignItems: "center" }}>
      <div style={{ alignSelf: "stretch", display: "flex", alignItems: "center", gap: 20 }}>
        <div style={{ width: 72, height: 72, borderRadius: 36, background: "linear-gradient(145deg,#E9EEF8,#B8C6E0)", color: "#0A2E7A", display: "grid", placeItems: "center", fontFamily: display, fontWeight: 700, fontSize: 28 }}>
          {caller.split(/\s+/).map(w => w[0]).join("").slice(0, 2).toUpperCase()}
        </div>
        <div style={{ minWidth: 0 }}>
          <div data-film-text="label" style={{ fontFamily: display, fontSize: 32, fontWeight: 600, whiteSpace: "nowrap" }}>{caller}</div>
          <div style={{ fontSize: 21, opacity: 0.6, marginTop: 4 }}>{context.subtitle || "Mobile"}</div>
        </div>
        <span style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8, fontSize: 15, fontWeight: 700, letterSpacing: 1.2, padding: "7px 13px", borderRadius: 999,
          background: ended ? "rgba(255,255,255,0.12)" : ringing ? "rgba(52,199,89,0.18)" : "rgba(255,59,48,0.2)", color: ended ? "rgba(255,255,255,0.7)" : ringing ? "#7DF29A" : "#FF8A80" }}>
          <span style={{ width: 9, height: 9, borderRadius: 5, background: "currentColor", opacity: ended ? 1 : 0.5 + 0.5 * Math.abs(Math.sin(global / 8)) }} />
          {ended ? "ENDED" : ringing ? "RINGING" : "LIVE"}
        </span>
      </div>
      <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 22 }}>
        {ringing
          ? <div style={{ position: "relative", width: 120, height: 120, display: "grid", placeItems: "center" }}>
            {[0, 1].map(k => {
              const t = ((global - start + k * 14) % 28) / 28;
              return <div key={k} style={{ position: "absolute", width: 120 + t * 110, height: 120 + t * 110, borderRadius: "50%", border: "2px solid rgba(52,199,89,0.8)", opacity: 1 - t }} />;
            })}
            <div style={{ width: 104, height: 104, borderRadius: 52, background: "#34C759", display: "grid", placeItems: "center", transform: `rotate(${Math.sin(global / 2.2) * beat * 12}deg)` }}>
              <Phone size={48} strokeWidth={2} color="#FFFFFF" />
            </div>
          </div>
          : <>
            <Bars global={global} live={speaking && !ended} width={portrait ? 600 : 520} />
            <div style={{ fontSize: 26, letterSpacing: 2, opacity: 0.8, fontVariantNumeric: "tabular-nums" }}>{`00:${pad(Math.floor(clock / 60))}:${pad(clock % 60)}`}</div>
            <div style={{ display: "flex", gap: 46, opacity: ended ? 0.4 : 1 }}>
              <div style={{ width: 70, height: 70, borderRadius: 35, background: "#1A62F2", display: "grid", placeItems: "center" }}><Mic size={32} color="#FFFFFF" /></div>
              <div style={{ width: 70, height: 70, borderRadius: 35, background: "#FF3B30", display: "grid", placeItems: "center" }}><Phone size={32} color="#FFFFFF" style={{ transform: "rotate(135deg)" }} /></div>
            </div>
          </>}
      </div>
      <div data-film-text="label" style={{ fontSize: 24, opacity: 0.85 }}>{status}</div>
    </div>
    <div style={{ position: "absolute", fontFamily: body, display: "flex", flexDirection: "column", gap: 26,
      ...(portrait ? { left: 90, width: 900, top: 860 } : { left: 1060, width: 720, top: review ? 360 : 280 }) }}>
      {review && <div style={{ opacity: reviewIn, marginBottom: 6 }}>
        <KineticType scene={review} frame={global - review.from} field="dark" size={portrait ? 60 : 56} align="left" maxWidth={portrait ? 900 : 720} />
      </div>}
      {shown.map(line => {
        const index = lines.indexOf(line);
        return <Caption key={index} line={line} global={global} flagged={!!review && index === flaggedIndex && reviewIn > 0.3} dim={!!review && index !== flaggedIndex && reviewIn > 0.3} />;
      })}
      {review && <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
        {(review.labels || []).map((label, i) => {
          const p = progress(global - review.from, review.labelFrames?.[i] ?? 10 + i * 12, 10);
          return <span key={i} data-film-text="label" style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "9px 15px", borderRadius: 999, background: "rgba(255,107,129,0.16)", border: "1.5px solid rgba(255,107,129,0.6)", color: "#FFD1D8", fontSize: 21, fontWeight: 600, opacity: p, transform: `scale(${0.85 + p * 0.15})` }}>
            <X size={18} strokeWidth={3} />{label}
          </span>;
        })}
      </div>}
    </div>
  </AbsoluteFill>;
}
