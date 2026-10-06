import React from "react";
import { AbsoluteFill } from "remotion";
import { Phone, X } from "lucide-react";
import { IOSCallButton, IPhone, IPHONE_OUTER } from "../kit";
import { body, display, FPS, K, progress, ringShake, useLaunch, type LaunchScene, type Ringtone } from "./core";
import { KineticType } from "./Kinetic";

const DIALOGUE = new Set(["agent", "customer", "example"]);
const pad = (n: number) => String(Math.max(0, n)).padStart(2, "0");

export type Line = { scene: LaunchScene; words: { word: string; at: number }[]; start: number; end: number };

/** Global frame the call is answered: just before the first turn, when the block opens on a ring long enough to read. */
export function pickupFrame(block: LaunchScene[], lines: Line[]): number | null {
  const first = lines[0];
  if (!first || first.scene !== block[0]) return null;
  const at = first.start - 10;
  return at - block[0].from >= 24 ? at : null;
}

/** Global frames at which each transcript word is heard; estimated evenly when a preview has no timestamps. */
export function linesOf(block: LaunchScene[], audioFrom: number): Line[] {
  return block.filter(s => DIALOGUE.has(s.voice || "")).map(scene => {
    const spoken = scene.wordTimings?.length ? scene.wordTimings : null;
    const tokens = scene.narration.split(/\s+/).filter(Boolean);
    const words = spoken
      ? spoken.map(w => ({ word: w.word, at: audioFrom + Math.round(w.start * FPS) }))
      : tokens.map((word, i) => ({ word, at: scene.from + 6 + Math.round((i / tokens.length) * (scene.frames - 20)) }));
    const end = spoken ? audioFrom + Math.ceil(spoken[spoken.length - 1].end * FPS) : scene.from + scene.frames - 10;
    return { scene, words, start: words[0]?.at ?? scene.from, end };
  });
}

function Waveform({ global, live, width }: { global: number; live: boolean; width: number }) {
  const bars = 30;
  return <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: width / bars * 0.38, height: 200, width }}>
    {Array.from({ length: bars }, (_, i) => {
      const env = Math.sin((i / (bars - 1)) * Math.PI);
      const h = live ? 18 + env * (40 + 130 * Math.abs(Math.sin(global * 0.33 + i * 0.8) * Math.cos(global * 0.11 + i * 0.37))) : 14;
      return <div key={i} style={{ width: width / bars * 0.62, height: h, borderRadius: 12, background: live ? "#7FA8FF" : "rgba(255,255,255,0.28)" }} />;
    })}
  </div>;
}

function Handset({ global, start, ended, hangupAt, speaking, caller, detail, scale, pickup }: {
  global: number; start: number; ended: boolean; hangupAt: number; speaking: boolean; caller: string; detail: string; scale: number; pickup: number | null;
}) {
  const ringing = pickup !== null && global < pickup;
  const answered = pickup ?? start - 4 * FPS;
  const clock = Math.max(0, Math.floor((Math.min(global, hangupAt) - answered) / FPS));
  const endPress = ended ? Math.max(0, 1 - (global - hangupAt) / 10) : 0;
  const beat = ringing ? Math.abs(Math.sin(global / 4.5)) : 0;
  const accept = pickup !== null ? Math.max(0, 1 - Math.abs(global - pickup + 4) / 6) : 0;
  return <IPhone scale={scale} appearance="dark" ringing={ringing} beat={beat}>
    <div style={{ width: 1179, height: 2556, padding: "300px 110px 210px", display: "flex", flexDirection: "column", alignItems: "center", color: "#FFFFFF", fontFamily: body, background: ended ? "linear-gradient(180deg,#1A1A1C 0%,#000 100%)" : "linear-gradient(180deg,#2C3A5C 0%,#10141F 45%,#000 100%)" }}>
      <div style={{ fontSize: 60, opacity: 0.72, letterSpacing: 1 }}>{ended ? "Call ended" : ringing ? "Incoming call…" : `${pad(Math.floor(clock / 60))}:${pad(clock % 60)}`}</div>
      <div style={{ width: 330, height: 330, borderRadius: 165, marginTop: 70, background: `linear-gradient(145deg, #5B8DFF, ${K.navy})`, display: "grid", placeItems: "center", fontFamily: display, fontWeight: 700, fontSize: 124, boxShadow: ringing ? `0 0 0 ${20 + beat * 40}px rgba(127,168,255,${0.3 - beat * 0.18})` : speaking ? "0 0 0 26px rgba(127,168,255,0.22), 0 0 0 52px rgba(127,168,255,0.1)" : "none", opacity: ended ? 0.55 : 1 }}>
        {caller.split(/\s+/).map(w => w[0]).join("").slice(0, 2).toUpperCase()}
      </div>
      <div style={{ fontFamily: display, fontSize: 104, fontWeight: 600, marginTop: 56, textAlign: "center", lineHeight: 1.1 }}>{caller}</div>
      <div style={{ fontSize: 56, opacity: 0.6, marginTop: 18 }}>{detail}</div>
      {ringing
        ? <div style={{ marginTop: "auto", width: "100%", display: "flex", justifyContent: "space-between", padding: "0 60px" }}>
          {["Decline", "Accept"].map(k => <div key={k} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 36 }}>
            <div style={{ width: 250, height: 250, borderRadius: 125, background: k === "Accept" ? "#34C759" : "#FF3B30", display: "grid", placeItems: "center", transform: k === "Accept" ? `scale(${1 + beat * 0.06 - accept * 0.1}) rotate(${Math.sin(global / 2.2) * beat * 8}deg)` : undefined }}>
              <Phone size={110} strokeWidth={1.75} color="#FFFFFF" style={{ transform: k === "Decline" ? "rotate(135deg)" : undefined }} />
            </div>
            <span style={{ fontSize: 52, opacity: 0.8 }}>{k}</span>
          </div>)}
        </div>
        : <>
          <div style={{ marginTop: 90, opacity: ended ? 0.4 : 1 }}><Waveform global={global} live={speaking && !ended} width={880} /></div>
          <div style={{ marginTop: "auto", display: "grid", gridTemplateColumns: "repeat(3, 240px)", gap: "70px 90px", opacity: ended ? 0.35 : 1 }}>
            {["Mute", "Keypad", "Speaker", "Add call", "FaceTime", "Contacts"].map(k => <IOSCallButton key={k} kind={k} size={240} active={k === "Speaker"} />)}
          </div>
          <div style={{ marginTop: 110, transform: `scale(${1 - endPress * 0.1})` }}><IOSCallButton kind="End" danger size={250} /></div>
        </>}
    </div>
  </IPhone>;
}

function Bubble({ line, global, dim, flagged, speaker }: { line: Line; global: number; dim: boolean; flagged: boolean; speaker: string }) {
  const agent = line.scene.voice === "agent";
  const enter = progress(global, line.start - 4, 8);
  return <div style={{ alignSelf: agent ? "flex-start" : "flex-end", maxWidth: "80%", opacity: enter * (dim ? 0.38 : 1), transform: `translateY(${(1 - enter) * 14}px)` }}>
    <div style={{ fontSize: 15, fontWeight: 700, letterSpacing: 1.3, color: agent ? K.blue : K.muted, marginBottom: 8, textAlign: agent ? "left" : "right", textTransform: "uppercase" }}>{speaker}</div>
    <div style={{
      padding: "16px 22px", borderRadius: agent ? "6px 22px 22px 22px" : "22px 6px 22px 22px", fontSize: 25, lineHeight: 1.4,
      background: agent ? "#EEF4FF" : "#FFFFFF", color: K.ink, border: flagged ? "2.5px solid #E11D48" : `1.5px solid ${agent ? "#D3E2FF" : "#E3E9F3"}`,
      boxShadow: flagged ? "0 0 0 6px rgba(225,29,72,0.14), 0 14px 30px rgba(225,29,72,0.16)" : "0 6px 16px rgba(10,15,31,0.05)",
    }}>
      {line.words.map((w, i) => <React.Fragment key={i}><span style={{ opacity: progress(global, w.at - 2, 4) }}>{w.word}</span>{i < line.words.length - 1 ? " " : ""}</React.Fragment>)}
    </div>
  </div>;
}

/** One persistent handset and live transcript across consecutive call scenes, then a post-call review. */
export function CallStage({ block, global, ring }: { block: LaunchScene[]; global: number; ring?: Ringtone }) {
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
  const flaggedIndex = review ? lines.map(l => l.scene.voice).lastIndexOf("agent") : -1;
  const context = block.find(s => s.screen)?.screen || {};
  const caller = context.title || "Nova Finance";
  const phoneScale = portrait ? 0.82 : 0.98;
  const phoneW = IPHONE_OUTER.width * phoneScale, phoneH = IPHONE_OUTER.height * phoneScale;
  const enter = progress(global - start, 0, 18);
  const reviewIn = review ? progress(global - review.from, 0, 14) : 0;
  const titleScene = review ? lines[lines.length - 1]?.scene ?? active : active;
  const panel: React.CSSProperties = portrait
    ? { left: 60, right: 60, top: 150 + phoneH * 0.62 + 40, bottom: 110 }
    : { left: 860, width: 920, top: review ? 300 : 150, bottom: review ? 96 : 150 };
  return <AbsoluteFill>
    <div style={{ position: "absolute", left: portrait ? (1080 - phoneW * 0.62) / 2 : 330, top: portrait ? 150 : (1080 - phoneH) / 2, transform: `translate(${ringShake(global - start, ringing, ring)}px, ${(1 - enter) * 60}px) ${portrait ? "scale(0.62)" : ""}`, transformOrigin: "top left", opacity: enter, filter: "drop-shadow(0 40px 60px rgba(10,46,122,0.3))" }}>
      <Handset global={global} start={start} ended={ended} hangupAt={hangupAt} speaking={speaking} caller={caller} detail={context.subtitle || "AI agent"} scale={phoneScale} pickup={pickup} />
    </div>
    {review && <div style={{ position: "absolute", left: portrait ? 60 : 860, width: portrait ? 960 : 920, top: portrait ? 90 : 110, opacity: reviewIn }}>
      <KineticType scene={review} frame={global - review.from} field="stage" size={portrait ? 64 : 66} align="left" maxWidth={portrait ? 960 : 920} />
    </div>}
    <div style={{ position: "absolute", ...panel, borderRadius: 32, background: "rgba(255,255,255,0.94)", boxShadow: "0 40px 90px rgba(10,46,122,0.18), 0 0 0 1px rgba(175,202,251,0.6)", padding: "30px 36px", display: "flex", flexDirection: "column", gap: 22, opacity: enter, transform: `translateX(${(1 - enter) * 40}px)`, fontFamily: body, overflow: "hidden" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16 }}>
        <div style={{ minWidth: 0 }}>
          <div data-film-text="label" style={{ fontFamily: display, fontSize: 32, fontWeight: 700, color: K.ink, letterSpacing: -0.5, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{titleScene.headline}</div>
          <div style={{ fontSize: 19, color: K.muted, marginTop: 6 }}>{[context.crumb, context.chip].filter(Boolean).join(" · ")}</div>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexShrink: 0 }}>
          <span style={{ fontSize: 14, fontWeight: 700, letterSpacing: 1.2, color: K.muted, border: "1.5px solid #E3E9F3", padding: "6px 12px", borderRadius: 999 }}>ILLUSTRATIVE CALL</span>
          <span style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 15, fontWeight: 700, color: ended ? K.muted : "#E11D48", background: ended ? "#F1F4F9" : "#FFE4E8", padding: "6px 12px", borderRadius: 999 }}>
            <span style={{ width: 9, height: 9, borderRadius: 5, background: ended ? K.muted : "#E11D48", opacity: ended ? 1 : 0.55 + 0.45 * Math.abs(Math.sin(global / 8)) }} />{ended ? "ENDED" : ringing ? "RINGING" : "LIVE"}
          </span>
        </div>
      </div>
      <div style={{ height: 1.5, background: "#E3E9F3" }} />
      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        {lines.map((line, i) => <Bubble key={i} line={line} global={global} dim={!!review && i !== flaggedIndex && reviewIn > 0.3} flagged={!!review && i === flaggedIndex && reviewIn > 0.3}
          speaker={line.scene.screen?.speaker || (line.scene.voice === "agent" ? "AI agent" : "Customer")} />)}
      </div>
      {review && <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
          {(review.labels || []).map((label, i) => {
            const p = progress(global - review.from, review.labelFrames?.[i] ?? 10 + i * 12, 10);
            return <span key={i} data-film-text="label" style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "8px 14px", borderRadius: 999, background: "#FFE4E8", color: "#BE123C", fontSize: 19, fontWeight: 600, opacity: p, transform: `scale(${0.85 + p * 0.15})` }}>
              <X size={18} strokeWidth={3} />{label}<span style={{ fontSize: 13, fontWeight: 800, letterSpacing: 1, background: "#BE123C", color: "#FFFFFF", borderRadius: 6, padding: "2px 6px" }}>FAIL</span>
            </span>;
          })}
        </div>
        {review.body && <div data-film-text="body" style={{ fontSize: 20, color: K.muted, lineHeight: 1.4, opacity: progress(global - review.from, (review.labelFrames?.at(-1) ?? 24) + 10, 12) }}>{review.body}</div>}
      </div>}
    </div>
  </AbsoluteFill>;
}
