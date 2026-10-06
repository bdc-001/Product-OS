import React from "react";
import { AbsoluteFill } from "remotion";
import { Hash, MicOff, Phone, UserPlus, Users, Video, Volume2, X } from "lucide-react";
import { linesOf, pickupFrame, type Line } from "./CallStage";
import { body, display, FPS, K, progress, ringShake, useLaunch, type LaunchScene, type Ringtone } from "./core";
import { KineticType } from "./Kinetic";

const DIALOGUE = new Set(["agent", "customer", "example"]);
const pad = (n: number) => String(Math.max(0, n)).padStart(2, "0");
const KEYS = [{ icon: MicOff, label: "mute" }, { icon: Hash, label: "keypad" }, { icon: Volume2, label: "audio" },
  { icon: UserPlus, label: "add call" }, { icon: Video, label: "FaceTime" }, { icon: Users, label: "contacts" }];

function Round({ color, size, children, ring = 0 }: { color: string; size: number; children: React.ReactNode; ring?: number }) {
  return <div style={{ width: size, height: size, borderRadius: size / 2, background: color, display: "grid", placeItems: "center",
    boxShadow: ring ? `0 0 0 ${ring * 26}px rgba(52,199,89,${0.28 - ring * 0.2})` : "none" }}>{children}</div>;
}

function Caption({ line, global, flagged, dim }: { line: Line; global: number; flagged: boolean; dim: boolean }) {
  const agent = line.scene.voice === "agent";
  const enter = progress(global, line.start - 4, 8);
  return <div style={{ opacity: enter * (dim ? 0.4 : 1), transform: `translateY(${(1 - enter) * 16}px)`, display: "flex", gap: 18 }}>
    <div style={{ width: 4, borderRadius: 2, background: agent ? K.blue : "#C5CEDB", flexShrink: 0 }} />
    <div>
      <div style={{ fontSize: 17, fontWeight: 700, letterSpacing: 1.6, color: agent ? K.blue : K.muted, marginBottom: 8, textTransform: "uppercase" }}>
        {line.scene.screen?.speaker || (agent ? "AI agent" : "Customer")}
      </div>
      <div style={{ fontSize: 30, lineHeight: 1.38, color: K.ink, padding: flagged ? "10px 16px" : 0, borderRadius: 14, border: flagged ? "2px solid #E11D48" : "none", background: flagged ? "#FFF1F3" : "none" }}>
        {line.words.map((w, i) => <React.Fragment key={i}><span style={{ opacity: progress(global, w.at - 2, 4) }}>{w.word}</span>{i < line.words.length - 1 ? " " : ""}</React.Fragment>)}
      </div>
    </div>
  </div>;
}

/** The call as the phone's own full-screen call view, no device frame: it rings, is answered, and runs live. */
export function FlatCall({ block, global, ring }: { block: LaunchScene[]; global: number; ring?: Ringtone }) {
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
  const enter = progress(global - start, 0, 16);
  const press = pickup !== null ? progress(global, pickup - 6, 6) * (1 - progress(global, pickup, 6)) : 0;
  const swap = pickup !== null ? progress(global, pickup, 10) : 1;
  const beat = ringing ? Math.abs(Math.sin((global - start) / 5)) : 0;
  const shown = lines.filter(l => global >= l.start - 4).slice(-3);
  const status = ended ? "Call ended" : ringing ? "incoming call" : `${pad(Math.floor(clock / 60))}:${pad(clock % 60)}`;
  const column: React.CSSProperties = portrait ? { left: 0, width: 1080, top: 150 } : { left: 140, width: 680, top: 110 };
  return <AbsoluteFill style={{ fontFamily: body }}>
    <div style={{ position: "absolute", ...column, display: "flex", flexDirection: "column", alignItems: "center", opacity: enter,
      transform: `translate(${ringShake(global - start, ringing, ring)}px, ${(1 - enter) * 30}px)` }}>
      <div style={{ width: 132, height: 132, borderRadius: 66, background: "linear-gradient(160deg,#A9B4C4,#7D8899)", color: "#FFFFFF", display: "grid", placeItems: "center", fontFamily: display, fontWeight: 600, fontSize: 52 }}>
        {caller.split(/\s+/).map(w => w[0]).join("").slice(0, 2).toUpperCase()}
      </div>
      <div data-film-text="label" style={{ fontFamily: display, fontSize: 56, fontWeight: 500, color: K.ink, marginTop: 26, whiteSpace: "nowrap" }}>{caller}</div>
      <div style={{ fontSize: 28, color: K.muted, marginTop: 8, fontVariantNumeric: "tabular-nums" }}>{status}</div>
      {ringing || swap < 1
        ? <div style={{ display: "flex", gap: portrait ? 300 : 220, marginTop: portrait ? 520 : 300, opacity: 1 - swap }}>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 14 }}>
            <Round color="#FF3B30" size={112}><Phone size={50} color="#FFFFFF" fill="#FFFFFF" style={{ transform: "rotate(135deg)" }} /></Round>
            <span style={{ fontSize: 24, color: K.ink }}>Decline</span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 14, transform: `scale(${1 - press * 0.12})` }}>
            <Round color="#34C759" size={112} ring={beat}><Phone size={50} color="#FFFFFF" fill="#FFFFFF" /></Round>
            <span style={{ fontSize: 24, color: K.ink }}>Accept</span>
          </div>
        </div>
        : <div style={{ display: "flex", flexDirection: "column", alignItems: "center", marginTop: portrait ? 120 : 64, opacity: ended ? 0.5 : swap }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 108px)", gap: portrait ? "44px 92px" : "30px 62px" }}>
            {KEYS.map(({ icon: Icon, label }) => <div key={label} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 10 }}>
              <Round color="#E9ECF1" size={92}><Icon size={38} color={K.ink} strokeWidth={1.8} /></Round>
              <span style={{ fontSize: 19, color: K.ink }}>{label}</span>
            </div>)}
          </div>
          <div style={{ marginTop: portrait ? 90 : 40 }}><Round color="#FF3B30" size={104}><Phone size={46} color="#FFFFFF" fill="#FFFFFF" style={{ transform: "rotate(135deg)" }} /></Round></div>
        </div>}
    </div>
    <div style={{ position: "absolute", display: "flex", flexDirection: "column", gap: 28,
      ...(portrait ? { left: 90, width: 900, top: 1330 } : { left: 960, width: 820, top: review ? 300 : 260 }) }}>
      {review && <div style={{ opacity: reviewIn, marginBottom: 4 }}>
        <KineticType scene={review} frame={global - review.from} field="light" size={portrait ? 58 : 56} align="left" maxWidth={portrait ? 900 : 820} />
      </div>}
      {shown.map(line => {
        const index = lines.indexOf(line);
        return <Caption key={index} line={line} global={global} flagged={!!review && index === flaggedIndex && reviewIn > 0.3} dim={!!review && index !== flaggedIndex && reviewIn > 0.3} />;
      })}
      {review && <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
        {(review.labels || []).map((label, i) => {
          const p = progress(global - review.from, review.labelFrames?.[i] ?? 10 + i * 12, 10);
          return <span key={i} data-film-text="label" style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "9px 15px", borderRadius: 999, background: "#FFE4E8", color: "#BE123C", fontSize: 21, fontWeight: 600, opacity: p, transform: `scale(${0.85 + p * 0.15})` }}>
            <X size={18} strokeWidth={3} />{label}
          </span>;
        })}
      </div>}
    </div>
  </AbsoluteFill>;
}
