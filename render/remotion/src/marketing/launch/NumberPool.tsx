import React from "react";
import { AbsoluteFill } from "remotion";
import { body, display, FPS, K, progress, useLaunch, type LaunchScene } from "./core";
import { KineticType } from "./Kinetic";

type Deal = { contact: string; from: number; at: number };

/** Which number dials each contact. A capped number steps aside once it reaches its limit; the rest keep turns. */
function dealCalls(mode: string, numbers: string[], contacts: string[], limit: number, start: number, gap: number) {
  const counts = numbers.map((_, i) => (mode === "limit" && i === 0 ? Math.max(0, limit - 1) : 0));
  const deals: Deal[] = [];
  let turn = 0;
  contacts.forEach((contact, i) => {
    let from = 0;
    if (mode !== "single") {
      for (let k = 0; k < numbers.length; k++) {
        const candidate = (turn + k) % numbers.length;
        if (mode !== "limit" || counts[candidate] < limit) { from = candidate; break; }
      }
      turn = from + 1;
    }
    counts[from] += 1;
    deals.push({ contact, from, at: start + i * gap });
  });
  return deals;
}

function Handset({ size, color }: { size: number; color: string }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round">
    <path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2z" />
  </svg>;
}

/** Who places the calls, drawn literally: one caller number dialling everyone, or a pool taking turns with even
 *  counters, where a number that reaches its cap greys out and the others carry on. */
export function NumberPool({ scene, frame }: { scene: LaunchScene; frame: number; global: number }) {
  const { portrait } = useLaunch();
  const pool = scene.pool!;
  const numbers = pool.mode === "single" ? pool.numbers.slice(0, 1) : pool.numbers.slice(0, 4);
  const contacts = pool.contacts.slice(0, 6);
  const limit = pool.limit || 2;
  const start = 22;
  const gap = Math.max(12, Math.min(34, Math.floor((scene.frames - start - 30) / Math.max(1, contacts.length))));
  const deals = dealCalls(pool.mode, numbers, contacts, limit, start, gap);
  const single = pool.mode === "single";

  const cardGap = portrait ? 18 : 22;
  // Portrait stacks the pool two by two so each full number stays legible.
  const cardW = portrait ? (single ? 620 : (940 - cardGap) / 2) : single ? 440 : 360;
  const cardH = single ? 250 : portrait ? 132 : 128;
  const area = portrait ? { left: 70, top: 740, width: 940 } : { left: 790, top: 0, width: 1050 };
  const gridRows = portrait && !single ? Math.ceil(numbers.length / 2) : 1;
  const cardsTop = portrait ? area.top : (1080 - (numbers.length * cardH + (numbers.length - 1) * cardGap)) / 2;
  const cardPos = (i: number) => portrait
    ? single ? { x: area.left + (area.width - cardW) / 2, y: cardsTop } : { x: area.left + (i % 2) * (cardW + cardGap), y: cardsTop + Math.floor(i / 2) * (cardH + cardGap) }
    : { x: area.left, y: cardsTop + i * (cardH + cardGap) };
  const rowW = portrait ? 940 : 520;
  const rowH = portrait ? 104 : 96;
  const rowGap = 14;
  const rowsTop = portrait ? area.top + gridRows * cardH + (gridRows - 1) * cardGap + 80 : (1080 - (contacts.length * rowH + (contacts.length - 1) * rowGap)) / 2;
  const rowPos = (i: number) => portrait ? { x: area.left, y: rowsTop + i * (rowH + rowGap) } : { x: area.left + area.width - rowW, y: rowsTop + i * (rowH + rowGap) };

  const placed = numbers.map((_, i) => deals.filter(d => d.from === i && frame >= d.at + 10).length);
  const base = numbers.map((_, i) => (pool.mode === "limit" && i === 0 ? Math.max(0, limit - 1) : 0));
  const latest = [...deals].reverse().find(d => frame >= d.at);
  const capped = (i: number) => pool.mode === "limit" && base[i] + placed[i] >= limit;
  const t = frame / FPS;

  return <AbsoluteFill style={{ fontFamily: body, overflow: "hidden", background: "linear-gradient(160deg, #FFFFFF 0%, #F6F9FF 55%, #E8F0FF 100%)" }}>
    <AbsoluteFill style={{ opacity: 0.45, backgroundSize: "44px 44px", backgroundPosition: `${(t * 3) % 44}px 0px`,
      backgroundImage: "radial-gradient(circle, rgba(127,168,255,0.45) 1.2px, transparent 1.6px)",
      maskImage: "radial-gradient(ellipse at 70% 50%, black 0%, transparent 70%)", WebkitMaskImage: "radial-gradient(ellipse at 70% 50%, black 0%, transparent 70%)" }} />
    <div style={{ position: "absolute", ...(portrait ? { left: 70, width: 940, top: 230, height: 460 } : { left: 110, width: 600, top: 0, bottom: 0 }), display: "flex", alignItems: "center" }}>
      <KineticType scene={scene} frame={frame} field="light" size={portrait ? 80 : 72} align="left" maxWidth={portrait ? 940 : 600} />
    </div>
    <svg width={portrait ? 1080 : 1920} height={portrait ? 1920 : 1080} style={{ position: "absolute", left: 0, top: 0, overflow: "visible" }}>
      {deals.map((deal, i) => {
        const p = progress(frame, deal.at, 12);
        if (p <= 0) return null;
        const c = cardPos(deal.from), r = rowPos(i);
        const x1 = portrait ? c.x + cardW / 2 : c.x + cardW, y1 = portrait ? c.y + cardH : c.y + cardH / 2;
        const x2 = portrait ? r.x + 60 : r.x, y2 = portrait ? r.y : r.y + rowH / 2;
        const mx = portrait ? x1 : (x1 + x2) / 2, my = portrait ? (y1 + y2) / 2 : y1;
        const fade = deal === latest ? 1 : 0.28;
        const path = portrait ? `M${x1} ${y1} C${mx} ${my} ${x2} ${my} ${x2} ${y2}` : `M${x1} ${y1} C${mx} ${y1} ${mx} ${y2} ${x2} ${y2}`;
        return <path key={i} d={path} fill="none" stroke={K.blue} strokeWidth={deal === latest ? 3.2 : 2} strokeLinecap="round"
          pathLength={1} strokeDasharray="1" strokeDashoffset={1 - p} opacity={fade} />;
      })}
    </svg>
    {numbers.map((number, i) => {
      const pos = cardPos(i);
      const enter = progress(frame, 4 + i * 4, 16);
      const active = latest?.from === i && frame < (latest?.at ?? 0) + gap;
      const full = capped(i);
      const count = base[i] + placed[i];
      return <div key={i} style={{ position: "absolute", left: pos.x, top: pos.y, width: cardW, height: cardH, borderRadius: 26, padding: single ? "30px 34px" : "18px 22px",
        background: full ? "#F1F3F7" : "#FFFFFF", display: "flex", flexDirection: "column", justifyContent: "center", gap: single ? 14 : 6,
        boxShadow: active && !full ? "0 22px 50px rgba(26,98,242,0.28), 0 0 0 3px #1A62F2" : "0 16px 38px rgba(10,46,122,0.14), 0 0 0 1px rgba(175,202,251,0.8)",
        opacity: enter * (full ? 0.72 : 1), transform: `translateY(${(1 - enter) * 24}px) scale(${active && !full ? 1.03 : 1})` }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ width: single ? 54 : 38, height: single ? 54 : 38, borderRadius: 999, background: full ? "#CBD3E1" : K.blue, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Handset size={single ? 28 : 20} color="#FFFFFF" />
          </div>
          <span style={{ fontSize: single ? 24 : 18, fontWeight: 600, color: K.muted, letterSpacing: 0.4 }}>{single ? "Calling from" : `Number ${i + 1}`}</span>
        </div>
        <span data-film-text="label" style={{ fontFamily: display, fontWeight: 700, fontSize: single ? 50 : 32, color: full ? K.muted : K.ink, whiteSpace: "nowrap", letterSpacing: 0.5 }}>{number}</span>
        <div style={{ display: "flex", alignItems: "center", gap: 10, fontSize: single ? 24 : 18, fontWeight: 600, color: full ? "#B42318" : K.navy }}>
          <span>{pool.mode === "limit" ? `${count} / ${limit} calls` : `${count} ${count === 1 ? "call" : "calls"}`}</span>
          {full && <span style={{ padding: "3px 10px", borderRadius: 999, background: "#FDECEA", fontSize: single ? 20 : 15 }}>Limit reached</span>}
        </div>
      </div>;
    })}
    {deals.map((deal, i) => {
      const pos = rowPos(i);
      const enter = progress(frame, deal.at + 6, 12);
      const ringing = frame < deal.at + 28;
      const unanswered = single && !ringing;
      return <div key={i} style={{ position: "absolute", left: pos.x, top: pos.y, width: rowW, height: rowH, borderRadius: 20, background: "#FFFFFF", padding: "0 24px",
        display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, boxShadow: "0 12px 30px rgba(10,46,122,0.12), 0 0 0 1px rgba(175,202,251,0.7)",
        opacity: enter, transform: `translateX(${(1 - enter) * 30}px)` }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 0 }}>
          <span data-film-text="label" style={{ fontFamily: display, fontWeight: 700, fontSize: portrait ? 30 : 28, color: K.ink }}>{deal.contact}</span>
          <span style={{ fontSize: portrait ? 20 : 18, color: K.muted, fontWeight: 500, whiteSpace: "nowrap" }}>from <span style={{ color: K.blue, fontWeight: 700 }}>{numbers[deal.from]}</span></span>
        </div>
        <span style={{ padding: "8px 16px", borderRadius: 999, fontSize: portrait ? 20 : 18, fontWeight: 700, whiteSpace: "nowrap",
          background: ringing ? K.pale : unanswered ? "#F1F3F7" : "#E8F5EE", color: ringing ? K.blue : unanswered ? K.muted : "#1F7A4D",
          opacity: ringing ? 0.7 + 0.3 * Math.sin(frame / 3) : 1 }}>
          {ringing ? "Ringing" : unanswered ? "No answer" : "Called"}
        </span>
      </div>;
    })}
  </AbsoluteFill>;
}
