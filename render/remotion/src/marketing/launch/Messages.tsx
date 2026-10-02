import React from "react";
import { AbsoluteFill } from "remotion";
import { Bell, CalendarClock, Info, MessageCircle, RefreshCw, Tag } from "lucide-react";
import { StatusMark } from "../kit/ProductUI";
import { KineticType } from "./Kinetic";
import { body, progress, useLaunch, type LaunchScene } from "./core";

/** Message rows are tagged by neutral type, never by industry. */
export function iconFor(tag: string) {
  const t = tag.toLowerCase();
  if (/remind|due/.test(t)) return Bell;
  if (/offer|promo|sale/.test(t)) return Tag;
  if (/follow|renew|re-?engag/.test(t)) return RefreshCw;
  if (/appoint|slot|book|schedul/.test(t)) return CalendarClock;
  if (/update|alert|notice/.test(t)) return Info;
  return MessageCircle;
}

/** Ticks advance sent → delivered → read on the film clock; a failed message turns red instead. */
export function liveStatus(final: string, age: number): { status: string; at: number } {
  if (age < 6) return { status: "sent", at: progress(age, 0, 6) };
  if (final === "sent") return { status: "sent", at: 1 };
  if (final === "failed") return age < 18 ? { status: "sent", at: 1 } : { status: "failed", at: progress(age, 18, 8) };
  if (age < 18 || final === "delivered") return { status: "delivered", at: progress(age, 6, 6) };
  return { status: "read", at: 1 };
}

/** Outbound WhatsApp messages from several audiences scroll at once, every tick settling on its real status. */
export function Messages({ scene, frame }: { scene: LaunchScene; frame: number }) {
  const { portrait } = useLaunch();
  const rows = scene.screen?.rows || [];
  const tags = [...new Set(rows.map(r => r.tag || ""))].slice(0, portrait ? 2 : 4);
  const colW = portrait ? 440 : 380, gap = portrait ? 36 : 40;
  const bubbleH = 124, bubbleGap = 20, perCol = portrait ? 12 : 8;
  const gridW = tags.length * colW + (tags.length - 1) * gap;
  const pull = 1.32 - progress(frame, 0, Math.max(40, scene.frames * 0.85)) * 0.3;
  const drift = frame * 1.4;
  return <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
    <div style={{ position: "relative", width: gridW, height: portrait ? 1800 : 1100, transform: `scale(${pull}) rotate(-3deg)`, transformOrigin: "center", fontFamily: body }}>
      {tags.map((tag, c) => {
        const own = rows.filter(r => (r.tag || "") === tag);
        const Icon = iconFor(tag);
        const offset = (c % 2 ? 60 : 0) - drift * (c % 2 ? 0.8 : 1);
        return <div key={tag} style={{ position: "absolute", left: c * (colW + gap), top: 0, width: colW, height: "100%" }}>
          {Array.from({ length: perCol }, (_, k) => {
            const row = own[k % own.length];
            const at = 4 + c * 3 + k * 5;
            const p = progress(frame, at, 10);
            const { status, at: tickAt } = liveStatus(row.hint || "read", frame - at - 4);
            const failed = status === "failed";
            const top = offset + 20 + k * (bubbleH + bubbleGap);
            const time = `${9 + ((c * 3 + k) % 9)}:${String((c * 17 + k * 7) % 60).padStart(2, "0")}`;
            return <div key={k} style={{
              position: "absolute", left: k % 2 ? 26 : 0, top, width: colW - 26, height: bubbleH, borderRadius: "18px 18px 4px 18px",
              background: failed ? "#FFF1F2" : "#D9FDD3", border: failed ? "1.5px solid #FDA4AF" : "1px solid rgba(255,255,255,0.6)",
              padding: "12px 18px", boxShadow: "0 16px 34px rgba(3,6,15,0.35)", opacity: p, transform: `translateY(${(1 - p) * 26}px) scale(${0.92 + p * 0.08})`,
              display: "flex", flexDirection: "column", justifyContent: "space-between",
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 15, fontWeight: 700, color: "#1A62F2", letterSpacing: 0.2 }}><Icon size={16} strokeWidth={2.4} />{tag}</div>
              <div style={{ fontSize: 18, lineHeight: 1.25, color: "#111B21", fontWeight: 500, overflow: "hidden", whiteSpace: "nowrap", textOverflow: "ellipsis" }}>{row.label}</div>
              <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 6, fontSize: 15, color: "#667781" }}>
                {time}<StatusMark status={status} size={16} at={tickAt} />
              </div>
            </div>;
          })}
        </div>;
      })}
    </div>
    <AbsoluteFill style={{ background: "radial-gradient(ellipse at 50% 50%, rgba(3,6,15,0.86) 0%, rgba(3,6,15,0.6) 36%, rgba(3,6,15,0.12) 74%), linear-gradient(180deg, rgba(3,6,15,0.7) 0%, rgba(3,6,15,0) 16%)" }} />
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", padding: portrait ? "0 70px" : "0 180px" }}>
      <KineticType scene={scene} frame={frame} field="dark" size={portrait ? 92 : 112} />
    </AbsoluteFill>
  </AbsoluteFill>;
}
