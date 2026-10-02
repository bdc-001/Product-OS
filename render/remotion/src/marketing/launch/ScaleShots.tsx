import React from "react";
import { AbsoluteFill, interpolate } from "remotion";
import { MessageCircle, Phone } from "lucide-react";
import { StatusMark } from "../kit/ProductUI";
import { KineticType, Volume } from "./Kinetic";
import { iconFor, liveStatus, Messages } from "./Messages";
import { body, display, K, progress, seeded, useLaunch, type LaunchScene, type ScaleLayout } from "./core";

type Shot = { scene: LaunchScene; frame: number; global: number };
type Row = { label: string; tag?: string; hint?: string };

/** Arrival cadence in scene frames: [first, every] or [first, lane stagger, round]. launch_sfx_cues mirrors these. */
export const CADENCE = { thread: [6, 20], phone: [10, 18], lanes: [8, 8, 84], dialer: [4, 12] } as const;

const push = (scene: LaunchScene, frame: number) => 1 + progress(frame, 0, Math.max(30, scene.frames)) * 0.03;

/** How many items have arrived, and how far the newest has settled; older items shift one slot as it lands. */
function arrivals(frame: number, first: number, every: number, total: number) {
  const n = Math.min(total, Math.max(0, Math.floor((frame - first) / every) + 1));
  return { n, settle: n ? progress(frame - (first + (n - 1) * every), 0, 10) : 0 };
}

const rowsOf = (scene: LaunchScene) => (scene.screen?.rows || []) as Row[];
const clockAt = (k: number) => `${9 + (k % 9)}:${String((k * 17) % 60).padStart(2, "0")}`;

/** Headline in the left column and one object on the right; stacked in portrait. */
function Split({ scene, frame, width, children }: { scene: LaunchScene; frame: number; width: number; children: React.ReactNode }) {
  const { portrait } = useLaunch();
  return <AbsoluteFill style={{ transform: `scale(${push(scene, frame)})` }}>
    <div style={{ position: "absolute", left: portrait ? 70 : 150, top: portrait ? 210 : 0, bottom: portrait ? undefined : 0, width: portrait ? 940 : width, display: "flex", flexDirection: "column", justifyContent: "center" }}>
      <KineticType scene={scene} frame={frame} field="dark" size={portrait ? 88 : 92} align="left" maxWidth={portrait ? 940 : width} />
    </div>
    {children}
  </AbsoluteFill>;
}

/** Every dot is a dial: the day's attempts light across one calm field and a few answer white. */
function VolumeDots({ scene, frame }: Shot) {
  const { portrait } = useLaunch();
  const cols = portrait ? 24 : 44, rows = portrait ? 20 : 11, pitch = portrait ? 36 : 33, dot = 10;
  const sweep = Math.max(50, Math.min(90, scene.frames * 0.45));
  const dots: React.ReactNode[] = [];
  for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
    const i = r * cols + c;
    const at = 4 + (c / cols) * sweep + seeded(i) * 16;
    const p = progress(frame, at, 8);
    const answered = seeded(i + 701) > 0.8 ? progress(frame, at + 12, 10) : 0;
    const shimmer = 0.78 + 0.22 * Math.sin(frame * 0.12 - c * 0.35);
    const pop = p > 0 && p < 1 ? Math.sin(p * Math.PI) * 0.6 : 0;
    dots.push(<div key={i} style={{
      position: "absolute", left: c * pitch + (pitch - dot) / 2, top: r * pitch + (pitch - dot) / 2, width: dot, height: dot, borderRadius: dot / 2,
      background: answered ? `rgba(241,241,241,${0.55 + 0.45 * answered})` : `rgba(74,132,245,${0.16 + 0.78 * p * shimmer})`,
      boxShadow: answered ? `0 0 ${14 * answered}px rgba(175,202,251,0.85)` : undefined, transform: `scale(${1 + pop})`,
    }} />);
  }
  const mask = "radial-gradient(ellipse at 50% 50%, black 58%, transparent 100%)";
  return <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", gap: portrait ? 96 : 70, transform: `scale(${push(scene, frame)})` }}>
    <KineticType scene={scene} frame={frame} field="dark" size={portrait ? 92 : 100} maxWidth={portrait ? 920 : 1500} />
    <div style={{ position: "relative", width: cols * pitch, height: rows * pitch, maskImage: mask, WebkitMaskImage: mask }}>{dots}</div>
  </AbsoluteFill>;
}

const HOURS = ["9 AM", "12 PM", "3 PM", "6 PM", "9 PM"];
function clock(fraction: number) {
  const minutes = 9 * 60 + Math.round(fraction * 12 * 60);
  const h = Math.floor(minutes / 60), m = minutes % 60;
  return `${((h + 11) % 12) + 1}:${String(m).padStart(2, "0")} ${h >= 12 ? "PM" : "AM"}`;
}

/** One working day on a single axis: call bars build behind a playhead that runs from 9 AM to 9 PM. */
function VolumeTimeline({ scene, frame, global }: Shot) {
  const { portrait } = useLaunch();
  const width = portrait ? 940 : 1620, count = portrait ? 92 : 160, tall = portrait ? 300 : 250;
  const pitch = width / count;
  const run = Math.max(60, Math.min(150, scene.frames * 0.7));
  const head = interpolate(frame, [6, 6 + run], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const day = (x: number) => 0.28 + 0.72 * Math.max(Math.exp(-((x - 0.28) ** 2) / 0.018), 0.88 * Math.exp(-((x - 0.72) ** 2) / 0.02));
  const fade = 1 - progress(frame, 6 + run, 14);
  const bars = Array.from({ length: count }, (_, i) => {
    const x = i / (count - 1);
    const grow = Math.min(1, Math.max(0, (head - x) * count / 5));
    const live = 0.82 + 0.18 * Math.abs(Math.sin(global * 0.07 + i * 0.6));
    const answered = seeded(i + 313) > 0.8;
    return <div key={i} style={{
      position: "absolute", left: i * pitch, bottom: 0, width: Math.max(3, pitch * 0.5), borderRadius: 2,
      height: (14 + tall * day(x) * (0.4 + 0.6 * seeded(i + 40))) * grow * live, background: answered ? "#F1F1F1" : "#4A84F5", opacity: answered ? 0.95 : 0.85,
    }} />;
  });
  return <AbsoluteFill style={{ padding: portrait ? "210px 70px 260px" : "150px 150px 130px", justifyContent: "space-between", transform: `scale(${push(scene, frame)})` }}>
    <KineticType scene={scene} frame={frame} field="dark" size={portrait ? 92 : 100} align="left" maxWidth={portrait ? 940 : 1400} />
    <div style={{ position: "relative", width, height: tall + 60 }}>
      <div style={{ position: "absolute", left: 0, right: 0, bottom: 60, height: tall }}>{bars}</div>
      <div style={{ position: "absolute", left: 0, right: 0, bottom: 58, height: 1.5, background: "rgba(175,202,251,0.35)" }} />
      {HOURS.map((hour, k) => <span key={hour} style={{
        position: "absolute", bottom: 14, left: `${k * 25}%`, transform: `translateX(${k === 0 ? 0 : k === HOURS.length - 1 ? -100 : -50}%)`,
        fontFamily: body, fontSize: portrait ? 26 : 22, color: "#AFCAFB", opacity: 0.85, whiteSpace: "nowrap",
      }}>{hour}</span>)}
      <div style={{ position: "absolute", left: head * width, bottom: 58, height: tall + 24, width: 2, marginLeft: -1, opacity: fade, background: "linear-gradient(180deg, rgba(241,241,241,0.95), rgba(175,202,251,0.2))", boxShadow: "0 0 18px 2px rgba(26,98,242,0.8)" }}>
        <span style={{ position: "absolute", bottom: "100%", left: "50%", transform: "translate(-50%, -10px)", whiteSpace: "nowrap", fontFamily: display, fontWeight: 700, fontSize: portrait ? 28 : 24, color: "#F1F1F1", padding: "6px 14px", borderRadius: 999, background: "rgba(26,98,242,0.92)" }}>{clock(head)}</span>
      </div>
    </div>
  </AbsoluteFill>;
}

const masked = (k: number) => `+91 9${Math.floor(seeded(k + 11) * 9)}•• ••• ${Math.floor(seeded(k + 23) * 90) + 10}`;

/** One live dialer: calls ring, connect or go unanswered, and the list keeps moving. */
function VolumeDialer({ scene, frame }: Shot) {
  const { portrait } = useLaunch();
  const sources = rowsOf(scene).length ? rowsOf(scene) : [{ label: "Outbound call" }];
  const [first, every] = CADENCE.dialer;
  const rowH = portrait ? 116 : 100, gap = 14, visible = portrait ? 7 : 6;
  const { n, settle } = arrivals(frame, first, every, Math.ceil(scene.frames / every) + 1);
  const items: React.ReactNode[] = [];
  for (let k = Math.max(0, n - visible - 1); k < n; k++) {
    const slot = n - 1 - k - (1 - settle);
    const age = frame - (first + k * every);
    const row = sources[k % sources.length];
    const ringing = age < 18;
    const answered = seeded(k + 5) > 0.42;
    const secs = Math.max(0, Math.floor((age - 18) / 30));
    const chip: React.CSSProperties = ringing ? { color: "#D1E1FD", border: "1.5px solid rgba(125,168,248,0.6)" } : answered ? { color: K.blue, background: "#F1F1F1" } : { color: "#959595", background: "rgba(255,255,255,0.06)" };
    items.push(<div key={k} style={{
      position: "absolute", left: 28, right: 28, top: 12 + slot * (rowH + gap), height: rowH, borderRadius: 20, padding: "0 24px",
      background: "rgba(255,255,255,0.05)", border: "1px solid rgba(175,202,251,0.16)", display: "flex", alignItems: "center", gap: 20, opacity: k === n - 1 ? settle : 1,
    }}>
      <div style={{ width: 52, height: 52, borderRadius: 26, flexShrink: 0, display: "grid", placeItems: "center", background: ringing ? "rgba(26,98,242,0.35)" : answered ? K.blue : "rgba(255,255,255,0.08)", boxShadow: ringing ? `0 0 0 ${6 + 6 * Math.abs(Math.sin(age * 0.25))}px rgba(26,98,242,0.18)` : undefined }}>
        <Phone size={24} color="#F1F1F1" strokeWidth={2.2} />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontFamily: display, fontWeight: 700, fontSize: portrait ? 30 : 27, color: "#F1F1F1", letterSpacing: 0.5 }}>{masked(k)}</div>
        <div style={{ fontFamily: body, fontSize: portrait ? 22 : 20, color: "#AFCAFB", marginTop: 4, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{row.tag ? `${row.tag} · ${row.label}` : row.label}</div>
      </div>
      <span style={{ fontFamily: body, fontWeight: 600, fontSize: portrait ? 22 : 20, padding: "8px 16px", borderRadius: 999, whiteSpace: "nowrap", ...chip }}>
        {ringing ? "Ringing" : answered ? `Connected · ${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, "0")}` : "No answer"}
      </span>
    </div>);
  }
  const mask = "linear-gradient(180deg, black 0%, black 78%, transparent 100%)";
  return <Split scene={scene} frame={frame} width={640}>
    <div style={{ position: "absolute", left: portrait ? 70 : 880, top: portrait ? 700 : 150, width: portrait ? 940 : 890, height: portrait ? 1000 : 780, borderRadius: 28, overflow: "hidden", background: "linear-gradient(180deg, rgba(26,98,242,0.16), rgba(10,46,122,0.12))", border: "1px solid rgba(175,202,251,0.22)", boxShadow: "0 40px 100px rgba(3,6,15,0.45)" }}>
      <div style={{ position: "absolute", top: 26, left: 32, display: "flex", alignItems: "center", gap: 10, fontFamily: body, fontWeight: 600, fontSize: 20, color: "#D1E1FD", letterSpacing: 1.2 }}>
        <span style={{ width: 10, height: 10, borderRadius: 5, background: "#7DA8F8", opacity: 0.55 + 0.45 * Math.abs(Math.sin(frame / 8)) }} />LIVE
      </div>
      <div style={{ position: "absolute", top: 72, left: 0, right: 0, bottom: 0, overflow: "hidden", maskImage: mask, WebkitMaskImage: mask }}>{items}</div>
    </div>
  </Split>;
}

function Bubble({ row, age, k, portrait, style }: { row: Row; age: number; k: number; portrait: boolean; style: React.CSSProperties }) {
  const { status, at } = liveStatus(row.hint || "read", age - 4);
  const failed = status === "failed";
  const Icon = iconFor(row.tag || "");
  return <div style={{
    borderRadius: "26px 26px 6px 26px", background: failed ? "#FFF1F2" : "#FFFFFF", border: failed ? "1.5px solid #F93739" : "1px solid rgba(255,255,255,0.7)",
    boxShadow: "0 18px 44px rgba(3,6,15,0.4)", fontFamily: body, ...style,
  }}>
    {row.tag && <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: portrait ? 20 : 18, fontWeight: 700, color: K.blue }}><Icon size={18} strokeWidth={2.4} />{row.tag}</div>}
    <div style={{ fontSize: portrait ? 30 : 28, fontWeight: 500, color: "#121212", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{row.label}</div>
    <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 8, fontSize: 17, color: "#6A6A6A" }}>{clockAt(k)}<StatusMark status={status} size={18} at={at} /></div>
  </div>;
}

/** One outbound thread: each audience's message lands in turn and settles on its real tick. */
function MessagesThread({ scene, frame }: Shot) {
  const { portrait } = useLaunch();
  const rows = rowsOf(scene);
  const [first, every] = CADENCE.thread;
  const bubbleH = portrait ? 150 : 138, gap = 18, visible = portrait ? 5 : 4;
  const { n, settle } = arrivals(frame, first, every, rows.length);
  const bubbles: React.ReactNode[] = [];
  for (let k = Math.max(0, n - visible - 1); k < n; k++) {
    const slot = n - 1 - k - (1 - settle);
    const p = k === n - 1 ? settle : 1;
    bubbles.push(<Bubble key={k} row={rows[k]} age={frame - (first + k * every)} k={k} portrait={portrait} style={{
      position: "absolute", right: 0, bottom: 20 + slot * (bubbleH + gap), width: portrait ? 860 : 720, height: bubbleH, padding: "16px 24px",
      display: "flex", flexDirection: "column", justifyContent: "space-between", opacity: p, transform: `translateY(${(1 - p) * 30}px) scale(${0.94 + 0.06 * p})`, transformOrigin: "100% 100%",
    }} />);
  }
  const mask = "linear-gradient(180deg, transparent 0%, black 16%, black 100%)";
  return <Split scene={scene} frame={frame} width={640}>
    <div style={{ position: "absolute", left: portrait ? 70 : 900, width: portrait ? 940 : 820, top: portrait ? 700 : 110, bottom: portrait ? 160 : 110, maskImage: mask, WebkitMaskImage: mask }}>{bubbles}</div>
  </Split>;
}

/** One clean lane per audience: a single message slides in, ticks through its status, and hands over to the next. */
function MessagesLanes({ scene, frame }: Shot) {
  const { portrait } = useLaunch();
  const rows = rowsOf(scene);
  const tags = [...new Set(rows.map(r => r.tag || ""))].slice(0, 4);
  const [first, stagger, round] = CADENCE.lanes;
  const laneH = portrait ? 230 : 128;
  return <AbsoluteFill style={{ padding: portrait ? "210px 70px 200px" : "140px 150px 110px", justifyContent: "space-between", transform: `scale(${push(scene, frame)})` }}>
    <KineticType scene={scene} frame={frame} field="dark" size={portrait ? 88 : 92} align="left" maxWidth={portrait ? 940 : 1500} />
    <div style={{ display: "flex", flexDirection: "column" }}>
      {tags.map((tag, l) => {
        const own = rows.filter(r => (r.tag || "") === tag);
        const start = first + l * stagger;
        const n = Math.max(0, Math.floor((frame - start) / round));
        const local = frame - start - n * round;
        const k = n % own.length;
        const final = start + (n + 1) * round > scene.frames;
        const p = frame < start ? 0 : progress(local, 0, 12);
        const out = final ? 0 : progress(local, round - 12, 10);
        const Icon = iconFor(tag);
        return <div key={tag} style={{ height: laneH, display: "flex", flexDirection: portrait ? "column" : "row", alignItems: portrait ? "flex-start" : "center", justifyContent: portrait ? "center" : "flex-start", gap: portrait ? 18 : 0, borderTop: l ? "1px solid rgba(175,202,251,0.18)" : undefined }}>
          <div style={{ width: portrait ? undefined : 360, flexShrink: 0, display: "flex", alignItems: "center", gap: 16, fontFamily: body, fontWeight: 600, fontSize: portrait ? 30 : 28, color: "#D1E1FD" }}>
            <span style={{ width: 46, height: 46, borderRadius: 23, display: "grid", placeItems: "center", background: "rgba(26,98,242,0.3)", border: "1px solid rgba(125,168,248,0.5)" }}><Icon size={22} color="#F1F1F1" strokeWidth={2.2} /></span>{tag}
          </div>
          <Bubble row={{ ...own[k], tag: "" }} age={local} k={l * 3 + n} portrait={portrait} style={{
            display: "flex", alignItems: "center", gap: 18, padding: "16px 24px", borderRadius: "22px 22px 6px 22px",
            opacity: p * (1 - out), transform: `translateX(${(1 - p) * 80 - out * 40}px)`,
          }} />
        </div>;
      })}
    </div>
  </AbsoluteFill>;
}

/** The customer's side: one phone on the lock screen, filling with the messages that actually landed. */
function MessagesPhone({ scene, frame }: Shot) {
  const { portrait } = useLaunch();
  const all = rowsOf(scene);
  const landed = all.filter(r => r.hint === "delivered" || r.hint === "read");
  const rows = landed.length ? landed : all;
  const [first, every] = CADENCE.phone;
  const W = portrait ? 560 : 470, H = portrait ? 1140 : 960;
  const cardH = portrait ? 118 : 104, gap = 12, visible = portrait ? 6 : 5;
  const { n, settle } = arrivals(frame, first, every, rows.length);
  const enter = progress(frame, 0, 18);
  const cards: React.ReactNode[] = [];
  for (let k = Math.max(0, n - visible - 1); k < n; k++) {
    const slot = n - 1 - k - (1 - settle);
    const row = rows[k];
    cards.push(<div key={k} style={{
      position: "absolute", left: 0, right: 0, top: slot * (cardH + gap), height: cardH, borderRadius: 26, padding: "14px 18px",
      background: "rgba(241,241,241,0.92)", display: "flex", alignItems: "center", gap: 14, fontFamily: body, opacity: k === n - 1 ? settle : 1,
    }}>
      <div style={{ width: 46, height: 46, borderRadius: 13, flexShrink: 0, display: "grid", placeItems: "center", background: "#1AC468" }}><MessageCircle size={26} color="#FFFFFF" strokeWidth={2.2} /></div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: portrait ? 21 : 19, fontWeight: 700, color: "#121212" }}><span>{row.tag || "WhatsApp"}</span><span style={{ fontWeight: 500, fontSize: 15, color: "#6A6A6A" }}>now</span></div>
        <div style={{ fontSize: portrait ? 20 : 18, color: "#3F3F3F", marginTop: 3, lineHeight: 1.3, display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>{row.label}</div>
      </div>
    </div>);
  }
  const mask = "linear-gradient(180deg, black 0%, black 80%, transparent 100%)";
  return <Split scene={scene} frame={frame} width={820}>
    <div style={{ position: "absolute", left: portrait ? (1080 - W) / 2 : 1160, top: portrait ? 700 : (1080 - H) / 2, width: W, height: H, borderRadius: 70, padding: 14, background: "#0F0F0F", boxShadow: "0 50px 120px rgba(3,6,15,0.6), 0 0 0 1.5px rgba(175,202,251,0.25)", opacity: enter, transform: `translateY(${(1 - enter) * 40}px)` }}>
      <div style={{ position: "relative", width: "100%", height: "100%", borderRadius: 58, overflow: "hidden", background: "linear-gradient(180deg, #1A62F2 0%, #151515 100%)" }}>
        <div style={{ position: "absolute", top: 18, left: "50%", width: 120, height: 34, marginLeft: -60, borderRadius: 17, background: "#050505" }} />
        <div style={{ position: "absolute", top: 96, left: 0, right: 0, textAlign: "center", fontFamily: display, fontWeight: 700, fontSize: portrait ? 128 : 108, color: "#F1F1F1", letterSpacing: -3 }}>9:41</div>
        <div style={{ position: "absolute", top: portrait ? 330 : 290, left: 14, right: 14, bottom: 0, maskImage: mask, WebkitMaskImage: mask }}>{cards}</div>
      </div>
    </div>
  </Split>;
}

/** Scale shots without the wall: one focal object per frame, chosen per film by launch_craft. */
export function ScaleShot({ layout, ...shot }: Shot & { layout?: ScaleLayout }) {
  if (shot.scene.visual === "volume") {
    if (layout === "dots") return <VolumeDots {...shot} />;
    if (layout === "timeline") return <VolumeTimeline {...shot} />;
    if (layout === "dialer") return <VolumeDialer {...shot} />;
    return <Volume {...shot} />;
  }
  if (layout === "thread") return <MessagesThread {...shot} />;
  if (layout === "lanes") return <MessagesLanes {...shot} />;
  if (layout === "phone") return <MessagesPhone {...shot} />;
  return <Messages scene={shot.scene} frame={shot.frame} />;
}
