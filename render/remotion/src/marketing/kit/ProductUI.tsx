import React from "react";
import { moduleName } from "../brand";
import { Img, staticFile } from "remotion";
import { Check, CheckCircle2, ChevronDown, Folder, Info, Plus, SlidersHorizontal, X } from "lucide-react";
import { progress } from "../launch/core";

export type UiRow = { label: string; hint?: string; tag?: string };
export type UiStat = { label: string; value: string };
export type UiCard = { badge?: string; kicker?: string; title: string; text?: string; chips?: string[]; stats?: UiStat[] };
export type UiPane = { label: string; text: string };
export type UiControl = { label: string; value: string };
export type UiCondition = { field: string; operator: string; value: string };
export type UiRecord = { cells: string[]; keep?: boolean };
export type UiMetric = { label: string; value: string; note?: string; rate?: string; delta?: string; tone?: "up" | "down" | "neutral"; status?: "" | "sent" | "delivered" | "read" | "failed" };
export type UiBar = { label: string; value: string; share: number };
export type UiSeries = { label: string; value: string; points: number[] };
export type UiTile = { label: string; value: string; note?: string };
/** A recreation of one real product surface. Every string is copied from the product; values are illustrative. */
export type Screen = {
  view?: "checklist" | "cards" | "diff" | "compare" | "filters" | "metrics" | "table" | "chart" | "tiles";
  tiles?: UiTile[]; tab?: string;
  health?: string; metrics?: UiMetric[]; modal_title?: string; modal_subtitle?: string; bars?: UiBar[];
  series?: UiSeries[]; toggle?: string[]; titles?: string[]; granularity?: string; rows_label?: string;
  tabs?: string[]; controls?: UiControl[]; conditions?: UiCondition[]; columns?: string[]; records?: UiRecord[];
  meta_after?: string; pane_title?: string; pane_subtitle?: string; add_label?: string; joiner?: string; more_label?: string;
  crumb?: string; chip?: string; chip_after?: string;
  title?: string; subtitle?: string; meta?: string;
  rows?: UiRow[]; cards?: UiCard[];
  remove?: UiPane; add?: UiPane;
  before?: string[]; after?: string[]; changed?: number[]; left_label?: string; right_label?: string;
  action?: string; secondary?: string; done?: string; toast?: string; footer?: string; note?: string; speaker?: string;
};

export const WIN = { w: 1120, h: 740, bar: 64, pad: 36 };
const U = {
  ink: "#0A0F1F", muted: "#5B6B82", rule: "#E3E9F3", faint: "#F5F8FD", blue: "#1A62F2", pale: "#EEF4FF",
  rose: "#BE123C", roseBg: "#FFE4E8", roseLine: "#FECDD3", amber: "#B45309", amberBg: "#FEF3C7",
  sky: "#0369A1", skyBg: "#E0F2FE", green: "#15803D", greenBg: "#DCFCE7", greenLine: "#BBF7D0",
};
const sans = "Inter, 'Helvetica Neue', Arial, sans-serif";

function severity(badge = "") {
  const b = badge.toLowerCase();
  if (b.startsWith("high")) return { fg: U.rose, bg: U.roseBg };
  if (b.startsWith("medium")) return { fg: U.amber, bg: U.amberBg };
  if (b.startsWith("low")) return { fg: U.sky, bg: U.skyBg };
  if (b.startsWith("accept")) return { fg: U.green, bg: U.greenBg };
  return { fg: U.blue, bg: U.pale };
}

function Badge({ text, size = 16 }: { text: string; size?: number }) {
  const tone = severity(text);
  return <span style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "5px 12px", borderRadius: 999, background: tone.bg, color: tone.fg, fontSize: size, fontWeight: 600, whiteSpace: "nowrap" }}>
    <span style={{ width: 7, height: 7, borderRadius: 4, background: tone.fg }} />{text}
  </span>;
}

function Button({ label, primary, pressed = 0, done, width }: { label: string; primary?: boolean; pressed?: number; done?: boolean; width: number }) {
  const squash = 1 - pressed * 0.05;
  return <div style={{
    width, height: 48, borderRadius: 12, display: "grid", placeItems: "center", fontSize: 18, fontWeight: 600,
    background: done ? U.green : primary ? U.blue : "#FFFFFF", color: primary || done ? "#FFFFFF" : U.ink,
    border: primary || done ? "none" : `1.5px solid ${U.rule}`, transform: `scale(${squash})`,
    boxShadow: primary ? `0 ${8 - pressed * 6}px 20px rgba(26,98,242,${0.32 - pressed * 0.2})` : "none",
  }}>{label}</div>;
}

/** Circular tick drawn in, not faded in. */
function Tick({ on }: { on: number }) {
  return <div style={{ width: 28, height: 28, borderRadius: 8, flexShrink: 0, border: `2px solid ${on > 0.05 ? U.blue : "#C5D0E0"}`, background: on > 0.05 ? U.blue : "#FFFFFF", display: "grid", placeItems: "center" }}>
    <svg width="18" height="18" viewBox="0 0 18 18"><path d="M3.5 9.5l3.6 3.4L14.5 5" fill="none" stroke="#FFFFFF" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" strokeDasharray="20" strokeDashoffset={20 * (1 - on)} /></svg>
  </div>;
}

type ViewProps = { screen: Screen; frame: number; clickAt?: number; labelFrames?: number[]; labels?: string[]; frames: number };

function pressOf(frame: number, clickAt?: number) {
  if (clickAt === undefined) return { pressed: 0, clicked: false };
  const d = frame - clickAt;
  return { pressed: d >= 0 && d < 6 ? Math.sin((d / 6) * Math.PI) : 0, clicked: d >= 2 };
}

function Header({ screen, frame, right }: { screen: Screen; frame: number; right?: React.ReactNode }) {
  const p = progress(frame, 0, 12);
  return <div style={{ position: "absolute", left: WIN.pad, right: WIN.pad, top: WIN.bar + 26, display: "flex", justifyContent: "space-between", alignItems: "flex-start", opacity: p, transform: `translateY(${(1 - p) * 10}px)` }}>
    <div style={{ minWidth: 0 }}>
      <div style={{ fontSize: 30, fontWeight: 700, color: U.ink, letterSpacing: -0.4 }}>{screen.title}</div>
      {screen.subtitle && <div style={{ fontSize: 18, color: U.muted, marginTop: 6 }}>{screen.subtitle}</div>}
    </div>
    {right}
  </div>;
}

function Footer({ screen, frame, clickAt }: { screen: Screen; frame: number; clickAt?: number }) {
  const { pressed, clicked } = pressOf(frame, clickAt);
  return <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: 84, borderTop: `1.5px solid ${U.rule}`, background: "#FFFFFF", display: "flex", alignItems: "center", padding: `0 ${WIN.pad}px`, gap: 14 }}>
    <div style={{ flex: 1, minWidth: 0 }}>
      {screen.footer && <div style={{ fontSize: 19, fontWeight: 600, color: U.ink }}>{screen.footer}</div>}
      {screen.note && <div style={{ fontSize: 16, color: U.muted, marginTop: 3, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{screen.note}</div>}
    </div>
    {screen.secondary && <Button label={screen.secondary} width={150} />}
    {screen.action && <Button label={clicked && screen.done ? screen.done : screen.action} primary pressed={pressed} done={clicked && !!screen.done} width={200} />}
  </div>;
}

function Checklist({ screen, frame, clickAt, labelFrames }: ViewProps) {
  const rows = screen.rows || [];
  const customAt = labelFrames?.[0] ?? 30;
  const shown = rows.map((row, i) => row.tag ? progress(frame, customAt, 12) : progress(frame, 4 + i * 3, 10));
  const ticks = rows.map((row, i) => row.tag ? progress(frame, customAt + 8, 10) : progress(frame, 8 + i * 3, 10));
  const selected = ticks.filter(t => t > 0.5).length;
  const colW = (WIN.w - WIN.pad * 2 - 20) / 2;
  return <>
    <Header screen={screen} frame={frame} right={<div style={{ fontSize: 18, fontWeight: 600, color: U.blue, background: U.pale, padding: "8px 16px", borderRadius: 999, whiteSpace: "nowrap" }}>{screen.meta || `${selected} of ${rows.length} selected`}</div>} />
    {rows.map((row, i) => {
      const col = i % 2, line = Math.floor(i / 2);
      const p = shown[i];
      const custom = !!row.tag;
      return <div key={i} style={{
        position: "absolute", left: WIN.pad + col * (colW + 20), top: 178 + line * 106, width: colW, height: 92, borderRadius: 16,
        border: `1.5px solid ${custom ? "#A9C4FA" : U.rule}`, background: custom ? U.pale : "#FFFFFF", padding: "0 20px",
        display: "flex", alignItems: "center", gap: 16, opacity: p, transform: `translateY(${(1 - p) * 16}px) scale(${0.97 + p * 0.03})`,
        boxShadow: custom && p > 0.5 ? "0 10px 26px rgba(26,98,242,0.16)" : "0 2px 6px rgba(10,15,31,0.04)",
      }}>
        <Tick on={ticks[i]} />
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ fontSize: 20, fontWeight: 600, color: U.ink, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{row.label}</div>
          {row.hint && <div style={{ fontSize: 16, color: U.muted, marginTop: 3, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{row.hint}</div>}
        </div>
        {row.tag && <span style={{ fontSize: 15, fontWeight: 600, color: U.blue, border: `1.5px solid ${U.blue}`, borderRadius: 999, padding: "3px 10px" }}>{row.tag}</span>}
      </div>;
    })}
    <Footer screen={screen} frame={frame} clickAt={clickAt} />
  </>;
}

export const CARD = { top: 150, w: 336, h: 548, gap: 20 };

function Cards({ screen, frame, clickAt, labelFrames }: ViewProps) {
  const cards = (screen.cards || []).slice(0, 3);
  const hovered = clickAt !== undefined && frame >= clickAt - 8;
  return <>
    <Header screen={screen} frame={frame} right={screen.meta ? <div style={{ fontSize: 18, color: U.muted, fontWeight: 600, paddingTop: 8 }}>{screen.meta}</div> : undefined} />
    {cards.map((card, i) => {
      const p = progress(frame, labelFrames?.[i] ?? 6 + i * 8, 12);
      const lift = hovered && i === 0 ? 1 : 0;
      return <div key={i} style={{
        position: "absolute", left: WIN.pad + i * (CARD.w + CARD.gap), top: CARD.top, width: CARD.w, height: CARD.h, borderRadius: 18,
        border: `1.5px solid ${lift ? "#A9C4FA" : U.rule}`, background: "#FFFFFF", padding: 22, display: "flex", flexDirection: "column", gap: 14,
        opacity: p, transform: `translateY(${(1 - p) * 28 - lift * 6}px)`, boxShadow: lift ? "0 22px 44px rgba(26,98,242,0.18)" : "0 4px 14px rgba(10,15,31,0.06)",
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          {card.badge && <Badge text={card.badge} />}
          {card.kicker && <span style={{ fontSize: 15, color: U.muted, fontWeight: 600 }}>{card.kicker}</span>}
        </div>
        <div style={{ fontSize: 23, lineHeight: 1.25, fontWeight: 700, color: U.ink, display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical", overflow: "hidden" }}>{card.title}</div>
        {card.text && <div style={{ fontSize: 17, lineHeight: 1.4, color: U.muted, display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical", overflow: "hidden" }}>{card.text}</div>}
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {(card.chips || []).slice(0, 2).map(chip => <span key={chip} style={{ fontSize: 15, color: U.ink, background: U.faint, border: `1px solid ${U.rule}`, borderRadius: 999, padding: "4px 11px", whiteSpace: "nowrap" }}>{chip}</span>)}
          {(card.chips || []).length > 2 && <span style={{ fontSize: 15, color: U.muted, padding: "4px 6px" }}>+{(card.chips || []).length - 2} more</span>}
        </div>
        <div style={{ marginTop: "auto", display: "flex", gap: 18, borderTop: `1px solid ${U.rule}`, paddingTop: 14 }}>
          {(card.stats || []).map(stat => <div key={stat.label} style={{ flex: 1 }}>
            <div style={{ fontSize: 15, color: U.muted }}>{stat.label}</div>
            <div style={{ fontSize: 30, fontWeight: 700, color: U.ink, marginTop: 2 }}>{stat.value}</div>
          </div>)}
        </div>
        <div style={{ fontSize: 17, fontWeight: 600, color: U.blue, textDecoration: lift ? "underline" : "none" }}>View interactions →</div>
      </div>;
    })}
  </>;
}

export const PATCH = { top: 176, h: 520, button: { w: 150, gap: 12 } };

function Diff({ screen, frame, clickAt }: ViewProps) {
  const card = screen.cards?.[0];
  const { pressed, clicked } = pressOf(frame, clickAt);
  const p = progress(frame, 4, 14);
  const strike = progress(frame, 14, 14);
  const addText = screen.add?.text || "";
  const typed = Math.round(addText.length * progress(frame, 18, Math.max(20, Math.round(addText.length / 3))));
  const counts = clicked ? "1 accepted · 0 declined · 0 pending" : "0 accepted · 0 declined · 1 pending";
  const pane = (tone: "remove" | "add"): React.CSSProperties => ({
    flex: 1, borderRadius: 16, padding: "18px 22px", display: "flex", flexDirection: "column", gap: 12,
    background: tone === "remove" ? "#FFF5F6" : "#F3FCF6", border: `1.5px solid ${tone === "remove" ? U.roseLine : U.greenLine}`,
  });
  return <>
    <Header screen={screen} frame={frame} right={<div style={{ fontSize: 17, fontWeight: 600, color: U.muted, background: U.faint, border: `1px solid ${U.rule}`, padding: "8px 14px", borderRadius: 999, whiteSpace: "nowrap" }}>{screen.meta || counts}</div>} />
    <div style={{ position: "absolute", left: WIN.pad, right: WIN.pad, top: PATCH.top, height: PATCH.h, borderRadius: 20, border: `1.5px solid ${clicked ? U.greenLine : U.rule}`, background: "#FFFFFF", padding: 24, display: "flex", flexDirection: "column", gap: 18, opacity: p, transform: `translateY(${(1 - p) * 24}px)`, boxShadow: "0 8px 26px rgba(10,15,31,0.07)" }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 14, paddingRight: PATCH.button.w * 2 + PATCH.button.gap + 10 }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            {card?.badge && <Badge text={card.badge} />}
            <span style={{ fontSize: 23, fontWeight: 700, color: U.ink, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{card?.title}</span>
            <Info size={20} color={U.muted} />
          </div>
          {card?.text && <div style={{ fontSize: 17, color: U.muted, marginTop: 8 }}>{card.text}</div>}
        </div>
      </div>
      <div style={{ position: "absolute", top: 24, right: 24, display: "flex", gap: PATCH.button.gap, alignItems: "center" }}>
        {clicked ? <>
          <span style={{ fontSize: 17, fontWeight: 600, color: U.muted, width: PATCH.button.w, textAlign: "right" }}>Undo</span>
          <div style={{ width: PATCH.button.w, height: 48, borderRadius: 12, background: U.greenBg, color: U.green, display: "flex", alignItems: "center", justifyContent: "center", gap: 8, fontSize: 18, fontWeight: 700 }}><Check size={20} strokeWidth={3} />{screen.done || "Accepted"}</div>
        </> : <>
          {screen.secondary && <Button label={screen.secondary} width={PATCH.button.w} />}
          {screen.action && <Button label={screen.action} primary pressed={pressed} width={PATCH.button.w} />}
        </>}
      </div>
      <div style={{ flex: 1, display: "flex", gap: 20, minHeight: 0 }}>
        <div style={pane("remove")}>
          <div style={{ fontSize: 16, fontWeight: 700, color: U.rose, display: "flex", alignItems: "center", gap: 8 }}><X size={18} strokeWidth={3} />{screen.remove?.label}</div>
          <div style={{ fontSize: 22, lineHeight: 1.45, color: "#7F1D2D", textDecorationLine: strike > 0.5 ? "line-through" : "none", textDecorationColor: U.rose, textDecorationThickness: 2, opacity: 1 - strike * 0.25 }}>{screen.remove?.text}</div>
        </div>
        <div style={pane("add")}>
          <div style={{ fontSize: 16, fontWeight: 700, color: U.green, display: "flex", alignItems: "center", gap: 8 }}><Check size={18} strokeWidth={3} />{screen.add?.label}</div>
          <div style={{ fontSize: 22, lineHeight: 1.45, color: "#14532D" }}>
            {addText.slice(0, typed)}<span style={{ opacity: 0 }}>{addText.slice(typed)}</span>
          </div>
        </div>
      </div>
    </div>
  </>;
}

function Compare({ screen, frame, clickAt }: ViewProps) {
  const before = screen.before || [], after = screen.after || [];
  const changed = new Set(screen.changed || []);
  const glow = progress(frame, 16, 12);
  const column = (label: string, lines: string[], side: "left" | "right") => <div style={{ flex: 1, minWidth: 0, borderRadius: 16, border: `1.5px solid ${U.rule}`, background: "#FFFFFF", overflow: "hidden" }}>
    <div style={{ padding: "14px 20px", fontSize: 17, fontWeight: 700, color: side === "right" ? U.green : U.muted, background: U.faint, borderBottom: `1px solid ${U.rule}` }}>{label}</div>
    <div style={{ padding: "12px 0" }}>
      {lines.map((line, i) => {
        const hit = changed.has(i);
        const tone = side === "left" ? { bg: `rgba(255,228,232,${glow})`, fg: "#7F1D2D" } : { bg: `rgba(220,252,231,${glow})`, fg: "#14532D" };
        return <div key={i} style={{ display: "flex", gap: 14, padding: "7px 20px", background: hit ? tone.bg : "transparent", borderLeft: hit ? `4px solid ${side === "left" ? U.rose : U.green}` : "4px solid transparent" }}>
          <span style={{ fontSize: 16, color: "#9AA8BD", width: 20, textAlign: "right", flexShrink: 0, paddingTop: 2 }}>{i + 1}</span>
          <span style={{ fontSize: 19, lineHeight: 1.4, color: hit ? tone.fg : U.ink, textDecorationLine: hit && side === "left" && glow > 0.5 ? "line-through" : "none", textDecorationColor: U.rose }}>{line}</span>
        </div>;
      })}
    </div>
  </div>;
  const p = progress(frame, 4, 14);
  return <>
    <Header screen={screen} frame={frame} right={screen.meta ? <div style={{ fontSize: 17, fontWeight: 600, color: U.blue, background: U.pale, padding: "8px 14px", borderRadius: 999, whiteSpace: "nowrap" }}>{screen.meta}</div> : undefined} />
    <div style={{ position: "absolute", left: WIN.pad, right: WIN.pad, top: 176, bottom: 108, display: "flex", gap: 20, opacity: p, transform: `translateY(${(1 - p) * 20}px)` }}>
      {column(screen.left_label || "", before, "left")}
      {column(screen.right_label || "", after, "right")}
    </div>
    <Footer screen={screen} frame={frame} clickAt={clickAt} />
  </>;
}

export const FILTER = { bar: 166, chips: 226, table: 284, head: 48, row: 52, lead: 64, pane: 480, button: 150 };

function Select({ text, placeholder, width, filled = 1, strong }: { text: string; placeholder?: string; width?: number | string; filled?: number; strong?: boolean }) {
  const shown = filled > 0.5 || !placeholder;
  return <div style={{ width, height: 44, borderRadius: 10, border: `1.5px solid ${filled > 0.5 ? "#A9C4FA" : U.rule}`, background: "#FFFFFF", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 14px", gap: 8, minWidth: 0 }}>
    <span style={{ fontSize: 17, fontWeight: strong && shown ? 600 : 500, color: shown ? U.ink : "#9AA8BD", opacity: shown ? Math.max(0.35, filled) : 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{shown ? text : placeholder}</span>
    <ChevronDown size={18} color={U.muted} style={{ flexShrink: 0 }} />
  </div>;
}

/** A list page with its filter bar; the More Filters pane stacks conditions and Apply narrows the list. */
function Filters({ screen, frame, clickAt, labelFrames }: ViewProps) {
  const controls = (screen.controls || []).slice(0, 3), conditions = (screen.conditions || []).slice(0, 3);
  const columns = (screen.columns || []).slice(0, 5), records = (screen.records || []).slice(0, 7);
  const { pressed } = pressOf(frame, clickAt);
  const applied = clickAt === undefined ? 0 : progress(frame, clickAt + 4, 16);
  const opening = conditions.length ? progress(frame, 4, 14) : 0;
  const pane = opening * (1 - (clickAt === undefined ? 0 : progress(frame, clickAt + 2, 12)));
  const cues = conditions.map((_, i) => labelFrames?.[i] ?? 16 + i * 14);
  const kept = records.filter(r => r.keep !== false).length;
  const widths = columns.map((_, i) => i === 0 ? 1.4 : 1);
  const total = widths.reduce((a, b) => a + b, 0);
  const tableW = WIN.w - WIN.pad * 2;
  const p = progress(frame, 0, 12);
  return <>
    <Header screen={screen} frame={frame} right={screen.tabs?.length ? <div style={{ display: "flex", padding: 4, borderRadius: 12, background: "#EEF2F8", gap: 4 }}>
      {screen.tabs.slice(0, 4).map((tab, i) => <span key={tab} style={{ fontSize: 16, fontWeight: 600, padding: "8px 16px", borderRadius: 9, color: i === 0 ? U.ink : U.muted, background: i === 0 ? "#FFFFFF" : "transparent", boxShadow: i === 0 ? "0 2px 6px rgba(10,15,31,0.08)" : "none", whiteSpace: "nowrap" }}>{tab}</span>)}
    </div> : undefined} />
    <div style={{ position: "absolute", left: WIN.pad, right: WIN.pad, top: FILTER.bar, display: "flex", gap: 12, alignItems: "center", opacity: p }}>
      {controls.map(control => <div key={control.label} style={{ display: "flex", alignItems: "center", gap: 8, height: 44, padding: "0 14px", borderRadius: 10, border: `1.5px solid ${U.rule}`, background: "#FFFFFF", whiteSpace: "nowrap", minWidth: 0 }}>
        <span style={{ fontSize: 16, color: control.value ? U.muted : U.ink, fontWeight: control.value ? 400 : 500 }}>{control.value ? `${control.label}:` : control.label}</span>
        {control.value && <span style={{ fontSize: 16, fontWeight: 600, color: U.ink, overflow: "hidden", textOverflow: "ellipsis" }}>{control.value}</span>}
        <ChevronDown size={16} color={U.muted} />
      </div>)}
      {conditions.length > 0 && <div style={{ display: "flex", alignItems: "center", gap: 8, height: 44, padding: "0 14px", borderRadius: 10, border: `1.5px solid ${opening > 0.3 ? U.blue : U.rule}`, background: opening > 0.3 ? U.pale : "#FFFFFF", color: U.blue, fontSize: 16, fontWeight: 600, whiteSpace: "nowrap" }}>
        <SlidersHorizontal size={17} />{screen.more_label || "More Filters"}
        {applied > 0.5 && <span style={{ minWidth: 22, height: 22, borderRadius: 11, background: U.blue, color: "#FFFFFF", fontSize: 13, display: "grid", placeItems: "center", transform: `scale(${0.6 + applied * 0.4})` }}>{conditions.length}</span>}
      </div>}
    </div>
    <div style={{ position: "absolute", left: WIN.pad, right: WIN.pad, top: FILTER.chips, height: 36, display: "flex", gap: 10, alignItems: "center" }}>
      {conditions.map((c, i) => {
        const chip = clickAt === undefined ? 0 : progress(frame, clickAt + 8 + i * 4, 10);
        return <span key={i} style={{ display: "inline-flex", alignItems: "center", gap: 6, height: 34, padding: "0 12px", borderRadius: 999, background: U.pale, border: "1px solid #C9DAFB", fontSize: 15, color: U.ink, whiteSpace: "nowrap", opacity: chip, transform: `translateY(${(1 - chip) * 8}px) scale(${0.9 + chip * 0.1})` }}>
          <span style={{ fontWeight: 600 }}>{c.field}</span><span style={{ color: U.muted }}>{c.operator}</span><span style={{ fontWeight: 600 }}>{c.value}</span><X size={14} color={U.muted} />
        </span>;
      })}
      {conditions.length >= 2 && screen.secondary && <span style={{ fontSize: 15, fontWeight: 600, color: U.blue, opacity: clickAt === undefined ? 0 : progress(frame, clickAt + 16, 10) }}>{screen.secondary}</span>}
    </div>
    <div style={{ position: "absolute", left: WIN.pad, top: FILTER.table - 8, width: tableW, borderRadius: 14, border: `1.5px solid ${U.rule}`, background: "#FFFFFF", overflow: "hidden", opacity: p }}>
      <div style={{ display: "flex", height: FILTER.head, alignItems: "center", justifyContent: "space-between", padding: "0 18px", background: U.faint, borderBottom: `1px solid ${U.rule}` }}>
        {columns.length ? columns.map((col, i) => <span key={col} style={{ width: tableW * widths[i] / total - 18, fontSize: 15, fontWeight: 600, color: U.muted, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{col}</span>) : <>
          <span data-film-text="count" style={{ position: "relative", fontSize: 18, fontWeight: 700, color: U.ink, whiteSpace: "nowrap" }}>
            <span style={{ opacity: 1 - applied }}>{screen.meta}</span>
            <span style={{ position: "absolute", left: 0, top: 0, opacity: applied }}>{screen.meta_after}</span>
          </span>
          {conditions.length > 0 && <span style={{ fontSize: 14, fontWeight: 600, color: U.blue, background: U.pale, border: "1px solid #C9DAFB", borderRadius: 8, padding: "3px 9px", opacity: applied }}>{conditions.length} {conditions.length === 1 ? "filter" : "filters"}</span>}
        </>}
      </div>
      {records.map((record, r) => {
        const drop = record.keep === false ? applied : 0;
        const lit = record.keep !== false && kept < records.length ? applied : 0;
        const rowH = columns.length ? FILTER.row : FILTER.lead;
        if (!columns.length) {
          const [name, state, campaign, last] = record.cells;
          return <div key={r} style={{ height: rowH * (1 - drop), opacity: 1 - drop, overflow: "hidden", borderBottom: `1px solid ${U.rule}`, background: `rgba(238,244,255,${lit * 0.7})`, padding: "0 18px", display: "flex", alignItems: "center", gap: 18 }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span style={{ fontSize: 18, fontWeight: 600, color: U.ink, whiteSpace: "nowrap" }}>{name}</span>
                {state && <span style={{ fontSize: 13, fontWeight: 600, borderRadius: 6, padding: "2px 7px", ...(/active|completed/i.test(state) ? { color: U.green, background: U.greenBg } : /snooz|pause/i.test(state) ? { color: "#B45309", background: "#FEF3C7" } : { color: U.muted, background: "#EEF2F8" }) }}>{state}</span>}
              </div>
              {campaign && <div style={{ fontSize: 14, color: U.blue, marginTop: 4, display: "flex", alignItems: "center", gap: 5, whiteSpace: "nowrap" }}><Folder size={13} />{campaign}</div>}
            </div>
            {last && <span style={{ fontSize: 14, color: U.muted, whiteSpace: "nowrap" }}>{last}</span>}
          </div>;
        }
        return <div key={r} style={{ display: "flex", alignItems: "center", height: rowH * (1 - drop), opacity: 1 - drop, overflow: "hidden", borderBottom: `1px solid ${U.rule}`, background: `rgba(238,244,255,${lit * 0.7})` }}>
          {columns.map((_, i) => <span key={i} style={{ width: tableW * widths[i] / total, padding: "0 18px", fontSize: 17, fontWeight: i === 0 ? 600 : 400, color: i === 0 ? U.ink : "#334155", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{record.cells[i]}</span>)}
        </div>;
      })}
    </div>
    {pane > 0.001 && <>
      <div style={{ position: "absolute", left: 0, right: 0, top: WIN.bar, bottom: 0, background: `rgba(10,15,31,${0.22 * pane})` }} />
      <div style={{ position: "absolute", right: 0, top: WIN.bar, bottom: 0, width: FILTER.pane, background: "#FFFFFF", borderLeft: `1.5px solid ${U.rule}`, boxShadow: "-24px 0 60px rgba(10,15,31,0.16)", transform: `translateX(${(1 - pane) * (FILTER.pane + 40)}px)` }}>
        <div style={{ padding: "26px 28px 0" }}>
          <div style={{ fontSize: 26, fontWeight: 700, color: U.ink }}>{screen.pane_title || "More Filters"}</div>
          {screen.pane_subtitle && <div style={{ fontSize: 16, color: U.muted, marginTop: 6, lineHeight: 1.35 }}>{screen.pane_subtitle}</div>}
        </div>
        <div style={{ padding: "20px 28px 0", display: "flex", flexDirection: "column", gap: 10 }}>
          {conditions.map((c, i) => {
            const at = cues[i];
            const card = progress(frame, at - 6, 10);
            const fill = [progress(frame, at - 2, 6), progress(frame, at + 4, 6), progress(frame, at + 10, 6)];
            return <React.Fragment key={i}>
              {i > 0 && <span style={{ alignSelf: "flex-start", fontSize: 13, fontWeight: 700, letterSpacing: 1, color: U.blue, background: U.pale, borderRadius: 6, padding: "3px 8px", opacity: card }}>{screen.joiner || "AND"}</span>}
              <div style={{ borderRadius: 14, border: `1.5px solid ${fill[2] > 0.5 ? "#A9C4FA" : U.rule}`, background: U.faint, padding: 12, display: "flex", flexDirection: "column", gap: 8, opacity: card, transform: `translateY(${(1 - card) * 14}px)` }}>
                <span style={{ fontSize: 14, fontWeight: 600, color: U.muted }}>Condition {i + 1}</span>
                <Select text={c.field} placeholder="Select field" filled={fill[0]} strong />
                <div style={{ display: "flex", gap: 8 }}>
                  <Select text={c.operator} placeholder="Operator" width={140} filled={fill[1]} />
                  <div style={{ flex: 1, minWidth: 0 }}><Select text={c.value} placeholder="Select value" filled={fill[2]} strong /></div>
                </div>
              </div>
            </React.Fragment>;
          })}
          {screen.add_label && <div style={{ fontSize: 16, fontWeight: 600, color: U.blue, display: "flex", alignItems: "center", gap: 6, marginTop: 4, opacity: progress(frame, cues[0] ?? 16, 10) }}><Plus size={17} />{screen.add_label}</div>}
        </div>
        <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: 84, borderTop: `1.5px solid ${U.rule}`, display: "flex", alignItems: "center", justifyContent: screen.secondary ? "space-between" : "flex-end", gap: 12, padding: "0 28px" }}>
          {screen.secondary && <span style={{ fontSize: 17, fontWeight: 600, color: U.muted }}>{screen.secondary}</span>}
          {screen.action && <Button label={screen.action} primary pressed={pressed} width={FILTER.button} />}
        </div>
      </div>
    </>}
  </>;
}

/** WhatsApp's own delivery marks: one grey tick, two grey ticks, two blue ticks, or a red failure. */
export function StatusMark({ status, size = 18, at = 1 }: { status?: string; size?: number; at?: number }) {
  if (!status) return null;
  if (status === "failed") return <span style={{ width: size, height: size, borderRadius: size / 2, background: "#EF4444", display: "inline-grid", placeItems: "center", flexShrink: 0, transform: `scale(${0.6 + 0.4 * at})` }}><X size={size * 0.66} color="#FFFFFF" strokeWidth={3.2} /></span>;
  const color = status === "read" ? "#34B7F1" : "#8696A0";
  const double = status !== "sent";
  return <svg width={size * 1.35} height={size} viewBox="0 0 27 20" style={{ flexShrink: 0 }}>
    <path d="M2 10.5l4.6 4.4L15.5 5" fill="none" stroke={color} strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" strokeDasharray="20" strokeDashoffset={20 * (1 - at)} />
    {double && <path d="M10.5 14.2l0.9 0.8L20.5 5" fill="none" stroke={color} strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" strokeDasharray="20" strokeDashoffset={20 * (1 - at)} />}
  </svg>;
}

const PILL: Record<string, [string, string]> = {
  healthy: [U.green, U.greenBg], high: [U.green, U.greenBg], approved: [U.green, U.greenBg], reinstated: [U.green, U.greenBg], enabled: [U.green, U.greenBg],
  warning: [U.amber, U.amberBg], medium: [U.amber, U.amberBg], pending: [U.amber, U.amberBg], "in appeal": [U.amber, U.amberBg], locked: [U.amber, U.amberBg],
  critical: [U.rose, U.roseBg], low: [U.rose, U.roseBg], rejected: [U.rose, U.roseBg], deleted: [U.rose, U.roseBg], "limit exceeded": [U.rose, U.roseBg],
  unknown: [U.muted, "#EEF2F8"], paused: [U.muted, "#EEF2F8"], disabled: [U.muted, "#EEF2F8"], archived: [U.muted, "#EEF2F8"], "pending deletion": ["#C2410C", "#FFEDD5"],
};

function StatePill({ text, glow = 0 }: { text: string; glow?: number }) {
  const tone = PILL[text.toLowerCase()];
  if (!tone) return <>{text}</>;
  return <span style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "4px 11px", borderRadius: 999, background: tone[1], color: tone[0], fontSize: 15, fontWeight: 600, whiteSpace: "nowrap", boxShadow: glow ? `0 0 0 ${5 * glow}px ${tone[1]}` : "none" }}>
    <span style={{ width: 7, height: 7, borderRadius: 4, background: tone[0] }} />{text}
  </span>;
}

const rateTone = (rate: string, failed: boolean): [string, string] => {
  const v = parseFloat(rate);
  if (failed) return [U.rose, U.roseBg];
  return v > 40 ? [U.green, U.greenBg] : v >= 25 ? [U.amber, U.amberBg] : [U.rose, U.roseBg];
};

/** Counts an Indian-grouped number up as the card settles; non-numeric values appear whole. */
function countUp(value: string, p: number) {
  if (!/^[\d,]+$/.test(value)) return value;
  return Math.round(Number(value.replace(/,/g, "")) * p).toLocaleString("en-IN");
}

export const METRIC = { top: 168, h: 176, gap: 14, list: 34 };
const metricW = (n: number) => (WIN.w - WIN.pad * 2 - METRIC.gap * (n - 1)) / n;

function Metrics({ screen, frame, clickAt, labelFrames, labels = [] }: ViewProps) {
  const metrics = (screen.metrics || []).slice(0, 5);
  const cards = (screen.cards || []).slice(0, 3);
  const bars = (screen.bars || []).slice(0, 5);
  const w = metricW(metrics.length);
  const cueOf = (label: string) => { const i = labels.indexOf(label); return i >= 0 ? labelFrames?.[i] : undefined; };
  const opened = clickAt === undefined ? 0 : progress(frame, clickAt + 3, 12);
  const breakdownW = (WIN.w - WIN.pad * 2 - 28) / 3;
  return <>
    <Header screen={screen} frame={frame} right={screen.health ? <span style={{
      display: "inline-flex", alignItems: "center", gap: 8, padding: "7px 14px", borderRadius: 999, fontSize: 16, fontWeight: 700, whiteSpace: "nowrap", opacity: progress(frame, 6, 12),
      ...(/critical/i.test(screen.health) ? { color: U.rose, background: U.roseBg } : /warning/i.test(screen.health) ? { color: U.amber, background: U.amberBg } : /unknown/i.test(screen.health) ? { color: U.muted, background: "#EEF2F8" } : { color: U.green, background: U.greenBg }),
    }}>
      <span style={{ width: 9, height: 9, borderRadius: 5, background: "currentColor" }} />{screen.health}
    </span> : undefined} />
    {metrics.map((m, i) => {
      const p = progress(frame, 4 + i * 4, 12);
      const count = progress(frame, 6 + i * 4, 26);
      const cue = cueOf(m.label);
      const lit = cue === undefined ? 0 : progress(frame, cue, 8) * (1 - 0.6 * progress(frame, cue + 30, 20));
      const failed = m.status === "failed";
      const top = /attempted|sent/i.test(m.label) ? "#94A3B8" : U.blue;
      const pill = m.tone === "up" ? [U.green, U.greenBg] : m.tone === "down" ? [U.rose, U.roseBg] : [U.muted, "#EEF2F8"];
      return <div key={m.label} style={{
        position: "absolute", left: WIN.pad + i * (w + METRIC.gap), top: METRIC.top, width: w, height: METRIC.h, borderRadius: 16, background: "#FFFFFF",
        border: `1.5px solid ${lit > 0.1 ? "#A9C4FA" : U.rule}`, borderTop: `4px solid ${top}`, padding: "14px 16px", display: "flex", flexDirection: "column", gap: 8,
        opacity: p, transform: `translateY(${(1 - p) * 18 - lit * 6}px)`, boxShadow: lit > 0.1 ? `0 14px 30px rgba(26,98,242,${0.2 * lit})` : "0 2px 8px rgba(10,15,31,0.05)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 7, minWidth: 0 }}>
          <StatusMark status={m.status} size={15} at={progress(frame, 10 + i * 4, 10)} />
          <span style={{ fontSize: 13, fontWeight: 700, letterSpacing: 0.8, color: U.muted, textTransform: "uppercase", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", flex: 1 }}>{m.label}</span>
          {failed && screen.action && <span style={{ width: METRIC.list - 6, height: METRIC.list - 6, borderRadius: 8, border: `1.5px solid ${U.rule}`, display: "grid", placeItems: "center", color: U.muted, background: opened > 0.1 ? U.pale : "#FFFFFF" }}><ListIcon /></span>}
        </div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
          <span style={{ fontSize: 32, fontWeight: 700, color: U.ink, letterSpacing: -0.6, fontVariantNumeric: "tabular-nums" }}>{countUp(m.value, count)}</span>
          {m.rate && <span style={{ fontSize: 14, fontWeight: 700, padding: "2px 8px", borderRadius: 7, color: m.status === "sent" ? U.muted : rateTone(m.rate, failed)[0], background: m.status === "sent" ? "#EEF2F8" : rateTone(m.rate, failed)[1] }}>{m.rate}</span>}
        </div>
        {m.note && <div style={{ fontSize: 14, color: U.muted, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{m.note}</div>}
        {m.delta && <span style={{ alignSelf: "flex-start", fontSize: 13, fontWeight: 700, padding: "3px 9px", borderRadius: 999, color: pill[0], background: pill[1], opacity: progress(frame, 22 + i * 4, 10) }}>{m.delta}</span>}
      </div>;
    })}
    {cards.length > 0 && <>
      <div style={{ position: "absolute", left: WIN.pad, top: METRIC.top + METRIC.h + 26, fontSize: 19, fontWeight: 700, color: U.ink, opacity: progress(frame, 18, 12) }}>{screen.rows_label || "Message Breakdown"}</div>
      {cards.map((card, i) => {
        const p = progress(frame, 22 + i * 5, 12);
        return <div key={card.title} style={{ position: "absolute", left: WIN.pad + i * (breakdownW + 14), top: METRIC.top + METRIC.h + 64, width: breakdownW, borderRadius: 16, background: "#FFFFFF", border: `1.5px solid ${U.rule}`, padding: "16px 18px", opacity: p, transform: `translateY(${(1 - p) * 16}px)` }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 10 }}>
            <span style={{ fontSize: 17, fontWeight: 700, color: U.ink, whiteSpace: "nowrap" }}>{card.title}</span>
            {card.kicker && <span style={{ fontSize: 14, color: U.muted, whiteSpace: "nowrap" }}>{card.kicker}</span>}
          </div>
          {(card.stats || []).map((stat, s) => {
            const fill = progress(frame, 30 + i * 5 + s * 4, 18) * Math.min(100, parseFloat(stat.value) || 0);
            return <div key={stat.label} style={{ marginTop: 14 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 15, color: "#334155" }}>
                <StatusMark status={stat.label.toLowerCase()} size={13} />
                <span style={{ flex: 1 }}>{stat.label}</span><span style={{ fontWeight: 700, color: U.ink }}>{stat.value}</span>
              </div>
              <div style={{ marginTop: 6, height: 7, borderRadius: 4, background: "#EEF2F8", overflow: "hidden" }}>
                <div style={{ width: `${fill}%`, height: "100%", borderRadius: 4, background: SERIES_COLOR[stat.label.toLowerCase()] || "#10B981" }} />
              </div>
            </div>;
          })}
        </div>;
      })}
    </>}
    {screen.modal_title && clickAt !== undefined && opened > 0 && <>
      <div style={{ position: "absolute", inset: 0, top: WIN.bar, background: `rgba(10,15,31,${0.38 * opened})` }} />
      <div style={{ position: "absolute", left: (WIN.w - 660) / 2, top: 120, width: 660, borderRadius: 20, background: "#FFFFFF", boxShadow: "0 40px 90px rgba(3,10,40,0.4)", padding: "26px 28px", opacity: opened, transform: `translateY(${(1 - opened) * 30}px) scale(${0.96 + opened * 0.04})` }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <div style={{ fontSize: 26, fontWeight: 700, color: U.ink }}>{screen.modal_title}</div>
            {screen.modal_subtitle && <div style={{ fontSize: 16, color: U.muted, marginTop: 6 }}>{screen.modal_subtitle}</div>}
          </div>
          <X size={22} color={U.muted} />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 20 }}>
          {bars.map((bar, i) => {
            const p = progress(frame, clickAt + 10 + i * 5, 12);
            const grow = progress(frame, clickAt + 14 + i * 5, 20);
            return <div key={bar.label} style={{ borderRadius: 14, border: `1.5px solid ${U.rule}`, padding: "12px 16px", opacity: p, transform: `translateX(${(1 - p) * 24}px)` }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <StatusMark status="failed" size={20} />
                <span style={{ flex: 1, fontSize: 17, fontWeight: 600, color: U.ink, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{bar.label}</span>
                <span style={{ fontSize: 17, fontWeight: 700, color: U.ink }}>{bar.value}</span>
                <span style={{ fontSize: 15, color: U.muted, width: 56, textAlign: "right" }}>{bar.share.toFixed(1)}%</span>
              </div>
              <div style={{ marginTop: 9, height: 8, borderRadius: 4, background: "#FEE2E2", overflow: "hidden" }}>
                <div style={{ width: `${bar.share * grow}%`, height: "100%", borderRadius: 4, background: "#EF4444" }} />
              </div>
            </div>;
          })}
        </div>
      </div>
    </>}
  </>;
}

function ListIcon() {
  return <svg width="16" height="16" viewBox="0 0 16 16"><g stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M5.5 4h8M5.5 8h8M5.5 12h8" /><circle cx="2.4" cy="4" r="0.6" /><circle cx="2.4" cy="8" r="0.6" /><circle cx="2.4" cy="12" r="0.6" /></g></svg>;
}

export const TABLE = { top: 168, head: 46, maxRow: 80, cellPad: 12 };

/** Column geometry and the hovered Health cell, shared by the table and the cursor that hovers it. */
function tableGeometry(screen: Screen, labels: string[] = []) {
  const columns = (screen.columns || []).slice(0, 7), records = (screen.records || []).slice(0, 7);
  const weights = columns.map((_, i) => i === 0 ? 1.7 : 1);
  const total = weights.reduce((a, b) => a + b, 0) || 1;
  const tableW = WIN.w - WIN.pad * 2;
  const row = Math.min(TABLE.maxRow, (WIN.h - TABLE.top - TABLE.head - 64) / Math.max(1, records.length));
  const healthCol = columns.findIndex(c => /^health$/i.test(c));
  const lastLit = labels.length ? records.findIndex(r => r.cells[0] === labels[labels.length - 1]) : -1;
  const colX = (i: number) => WIN.pad + tableW * weights.slice(0, i).reduce((a, b) => a + b, 0) / total;
  const rowTop = (r: number) => TABLE.top + TABLE.head + r * row;
  const hover = lastLit >= 0 && healthCol >= 0 ? { x: colX(healthCol) + TABLE.cellPad + 34, y: rowTop(lastLit) + row / 2 + 4 } : undefined;
  return { columns, records, weights, total, tableW, row, healthCol, lastLit, colX, rowTop, hover };
}

function Table({ screen, frame, labelFrames, labels = [] }: ViewProps) {
  const { columns, records, weights, total, tableW, row, healthCol, lastLit, colX, rowTop } = tableGeometry(screen, labels);
  const tip = lastLit >= 0 && screen.note ? progress(frame, (labelFrames?.[labels.length - 1] ?? 30) + 6, 10) : 0;
  return <>
    <Header screen={screen} frame={frame} right={screen.meta ? <div style={{ fontSize: 17, fontWeight: 600, color: U.muted, background: "#EEF2F8", padding: "8px 14px", borderRadius: 999, whiteSpace: "nowrap" }}>{screen.meta}</div> : undefined} />
    <div style={{ position: "absolute", left: WIN.pad, top: TABLE.top, width: tableW, borderRadius: 16, border: `1.5px solid ${U.rule}`, background: "#FFFFFF", overflow: "hidden", opacity: progress(frame, 2, 12) }}>
      <div style={{ display: "flex", alignItems: "center", height: TABLE.head, background: U.faint, borderBottom: `1px solid ${U.rule}` }}>
        {columns.map((col, i) => <span key={col + i} style={{ width: tableW * weights[i] / total, padding: `0 ${TABLE.cellPad}px`, fontSize: 13, fontWeight: 700, letterSpacing: 0.7, textTransform: "uppercase", color: U.muted, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{col}</span>)}
      </div>
      {records.map((record, r) => {
        const p = progress(frame, 6 + r * 4, 12);
        const li = labels.indexOf(record.cells[0]);
        const cue = li >= 0 ? labelFrames?.[li] ?? 24 + li * 18 : undefined;
        const lit = cue === undefined ? 0 : progress(frame, cue, 8);
        const pulse = cue === undefined ? 0 : bumpOf(frame, cue + 4, 14);
        return <div key={r} style={{ position: "relative", display: "flex", alignItems: "center", height: row, borderBottom: `1px solid ${U.rule}`, background: `rgba(238,244,255,${lit * 0.9})`, opacity: p, transform: `translateY(${(1 - p) * 10}px)` }}>
          <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 4, background: U.blue, opacity: lit }} />
          {columns.map((col, i) => <span key={i} style={{ width: tableW * weights[i] / total, padding: `0 ${TABLE.cellPad}px`, fontSize: 18, fontWeight: i === 0 || rated(col, record.cells[i]) ? 600 : 500, color: rated(col, record.cells[i]) ? rateTone(record.cells[i], false)[0] : i === 0 ? U.ink : "#334155", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", fontVariantNumeric: "tabular-nums" }}>
            <StatePill text={record.cells[i] ?? ""} glow={i === healthCol ? pulse : 0} />
          </span>)}
        </div>;
      })}
    </div>
    {tip > 0 && healthCol >= 0 && <div style={{
      position: "absolute", top: rowTop(lastLit + 1) - 6, left: colX(healthCol) + TABLE.cellPad - 8,
      padding: "9px 14px", borderRadius: 10, background: "#0F172A", color: "#FFFFFF", fontSize: 15, fontWeight: 500, whiteSpace: "nowrap",
      opacity: tip, transform: `translateY(${(1 - tip) * -8}px)`, boxShadow: "0 12px 30px rgba(3,10,40,0.3)", zIndex: 3,
    }}>
      <span style={{ position: "absolute", left: 30, top: -6, width: 12, height: 12, background: "#0F172A", transform: "rotate(45deg)" }} />
      <span style={{ position: "relative" }}>{screen.note}</span>
    </div>}
  </>;
}

const rated = (column: string, cell = "") => /^(delivery|read)( %)?$/i.test(column) && /%$/.test(cell);

function bumpOf(frame: number, at: number, duration: number) {
  return frame < at || frame > at + duration ? 0 : Math.sin(((frame - at) / duration) * Math.PI);
}

export const SERIES_COLOR: Record<string, string> = {
  attempted: "#3B82F6", sent: "#94A3B8", delivered: "#10B981", read: "#8B5CF6", responded: "#F59E0B", failed: "#EF4444",
};
export const CHART = { top: 172, toggleW: 104, toggleY: 92, plotTop: 220, plotH: 380 };

function Chart({ screen, frame, clickAt, labelFrames, labels = [] }: ViewProps) {
  const series = (screen.series || []).slice(0, 6);
  const [first, second] = screen.toggle || ["Funnel", "Trend"];
  const [titleA, titleB] = screen.titles || ["", ""];
  const flipped = clickAt === undefined ? 0 : progress(frame, clickAt + 3, 12);
  const focus = labels.length ? progress(frame, labelFrames?.[0] ?? 40, 10) : 0;
  const plotL = WIN.pad + 54, plotR = WIN.w - WIN.pad - 10, plotW = plotR - plotL;
  const plotTop = CHART.plotTop, plotH = CHART.plotH, base = plotTop + plotH;
  const values = series.map(s => Number(s.value.replace(/,/g, "")) || 0);
  const peak = Math.max(1, ...values);
  const allPoints = series.flatMap(s => s.points);
  const top = Math.max(1, ...allPoints) * 1.12;
  const count = series[0]?.points.length || 0;
  const weekly = /week/i.test(screen.granularity || "");
  const axis = Array.from({ length: count }, (_, i) => {
    const d = new Date(Date.UTC(2026, 8, 30));
    d.setUTCDate(d.getUTCDate() - (count - 1 - i) * (weekly ? 7 : 1) - (weekly ? 2 : 0));
    return `${String(d.getUTCMonth() + 1).padStart(2, "0")}-${String(d.getUTCDate()).padStart(2, "0")}`;
  });
  const x = (i: number) => plotL + (count <= 1 ? 0 : (i / (count - 1)) * plotW);
  const y = (v: number) => base - (v / top) * plotH;
  const draw = clickAt === undefined ? 0 : progress(frame, clickAt + 8, 30);
  const tabX = (i: number) => WIN.w - WIN.pad - CHART.toggleW * (2 - i) - 4;
  return <>
    <div style={{ position: "absolute", left: WIN.pad, top: WIN.bar + 26, opacity: progress(frame, 0, 12) }}>
      <div style={{ position: "relative", height: 38 }}>
        <span style={{ position: "absolute", whiteSpace: "nowrap", fontSize: 30, fontWeight: 700, color: U.ink, letterSpacing: -0.4, opacity: 1 - flipped }}>{titleA}</span>
        <span style={{ position: "absolute", whiteSpace: "nowrap", fontSize: 30, fontWeight: 700, color: U.ink, letterSpacing: -0.4, opacity: flipped }}>{titleB}</span>
      </div>
      {screen.subtitle && <div style={{ fontSize: 18, color: U.muted, marginTop: 6 }}>{screen.subtitle}</div>}
    </div>
    <div style={{ position: "absolute", left: tabX(0) - 4, top: CHART.toggleY - 4, width: CHART.toggleW * 2 + 8, height: 48, borderRadius: 12, background: "#EEF2F8", opacity: progress(frame, 4, 12) }} />
    <div style={{ position: "absolute", left: tabX(0) + flipped * CHART.toggleW, top: CHART.toggleY, width: CHART.toggleW, height: 40, borderRadius: 9, background: "#FFFFFF", boxShadow: "0 2px 6px rgba(10,15,31,0.1)", opacity: progress(frame, 4, 12) }} />
    {[first, second].map((label, i) => <span key={label} style={{ position: "absolute", left: tabX(i), top: CHART.toggleY, width: CHART.toggleW, height: 40, display: "grid", placeItems: "center", fontSize: 17, fontWeight: 600, color: (i === 1 ? flipped : 1 - flipped) > 0.5 ? U.ink : U.muted, opacity: progress(frame, 4, 12) }}>{label}</span>)}
    {screen.granularity && <div style={{ position: "absolute", left: tabX(0) - 150, top: CHART.toggleY, width: 132, height: 40, borderRadius: 10, border: `1.5px solid ${U.rule}`, background: "#FFFFFF", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 12px", fontSize: 16, fontWeight: 600, color: U.ink, opacity: flipped }}>{screen.granularity}<ChevronDown size={16} color={U.muted} /></div>}
    <svg width={WIN.w} height={WIN.h} style={{ position: "absolute", left: 0, top: 0, overflow: "visible" }}>
      {[0, 0.25, 0.5, 0.75, 1].map(g => <line key={g} x1={plotL} x2={plotR} y1={base - g * plotH} y2={base - g * plotH} stroke={U.rule} strokeWidth={1} />)}
      {series.map((s, i) => {
        const slot = plotW / series.length;
        const grow = progress(frame, 3 + i * 2, 12) * (1 - flipped);
        const h = (values[i] / peak) * plotH * 0.92 * grow;
        const color = SERIES_COLOR[s.label.toLowerCase()] || U.blue;
        return <g key={`b${i}`} opacity={1 - flipped}>
          <rect x={plotL + i * slot + slot * 0.2} y={base - h} width={slot * 0.6} height={h} rx={8} fill={color} />
          <text x={plotL + i * slot + slot / 2} y={base - h - 12} textAnchor="middle" fontSize={17} fontWeight={700} fill={U.ink} opacity={grow}>{countUp(s.value, grow)}</text>
          <text x={plotL + i * slot + slot / 2} y={base + 28} textAnchor="middle" fontSize={16} fill={U.muted}>{s.label}</text>
        </g>;
      })}
      {flipped > 0 && series.map((s, i) => {
        const color = SERIES_COLOR[s.label.toLowerCase()] || U.blue;
        const d = s.points.map((v, k) => `${k ? "L" : "M"}${x(k).toFixed(1)} ${y(v).toFixed(1)}`).join(" ");
        const lit = labels.includes(s.label);
        const dim = labels.length && !lit ? 1 - focus * 0.75 : 1;
        const len = plotW * 1.6;
        return <g key={`l${i}`} opacity={flipped * dim}>
          {lit && <path d={d} fill="none" stroke={color} strokeWidth={14} strokeOpacity={0.18 * focus} strokeLinecap="round" strokeLinejoin="round" />}
          <path d={d} fill="none" stroke={color} strokeWidth={lit ? 3.5 + focus * 1.5 : 3} strokeLinecap="round" strokeLinejoin="round" strokeDasharray={len} strokeDashoffset={len * (1 - draw)} />
          {lit && draw > 0.98 && <circle cx={x(count - 1)} cy={y(s.points[count - 1])} r={6 + bumpOf(frame, (labelFrames?.[0] ?? 40) + 2, 16) * 6} fill={color} />}
        </g>;
      })}
      {flipped > 0 && axis.map((t, i) => (i % Math.ceil(count / 7) === 0 || i === count - 1) ? <text key={t} x={x(i)} y={base + 28} textAnchor="middle" fontSize={15} fill={U.muted} opacity={flipped}>{t}</text> : null)}
    </svg>
    <div style={{ position: "absolute", left: plotL, right: WIN.pad, top: base + 56, display: "flex", gap: 22, flexWrap: "wrap", opacity: flipped }}>
      {series.map(s => {
        const lit = labels.includes(s.label);
        return <span key={s.label} style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 16, fontWeight: lit ? 700 : 500, color: labels.length && !lit ? "#9AA8BD" : U.ink }}>
          <span style={{ width: 12, height: 12, borderRadius: 6, background: SERIES_COLOR[s.label.toLowerCase()] || U.blue }} />{s.label}
        </span>;
      })}
    </div>
  </>;
}

export const TILES = { tabs: WIN.bar + 20, card: 86, tileH: 150, block: 74 };

/** Vertical layout of a collapsible analytics section, shared by the view and the cursor that expands it. */
function tilesGeometry(screen: Screen) {
  const cards = (screen.metrics || []).slice(0, 4);
  const cardsTop = TILES.tabs + 58;
  const headTop = cards.length ? cardsTop + TILES.card + 26 : TILES.tabs + 62;
  const gridTop = headTop + 76;
  const rows = Math.ceil(Math.min(6, (screen.tiles || []).length) / 3);
  const gridH = rows * TILES.tileH + (rows - 1);
  return { cards, cardsTop, headTop, gridTop, gridH };
}

/** Counts a decimal average or an "Xm Ys" duration up as the tile settles. */
function countAverage(value: string, p: number) {
  const time = value.match(/^(?:(\d+)m )?(\d+)s$/);
  if (time) {
    const total = Math.round((Number(time[1] || 0) * 60 + Number(time[2])) * p);
    return total >= 60 ? `${Math.floor(total / 60)}m ${total % 60}s` : `${total}s`;
  }
  if (!/^\d+(\.\d+)?$/.test(value)) return value;
  const places = (value.split(".")[1] || "").length;
  return (Number(value) * p).toFixed(places);
}

function SectionHeading({ title, subtitle, open, top, opacity = 1 }: { title: string; subtitle?: string; open: number; top: number; opacity?: number }) {
  return <div style={{ position: "absolute", left: WIN.pad, right: WIN.pad, top, opacity }}>
    <div style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 15, fontWeight: 600, letterSpacing: 1.4, textTransform: "uppercase", color: "#334155", whiteSpace: "nowrap" }}>
      <ChevronDown size={18} color="#334155" style={{ transform: `rotate(${-90 + 90 * open}deg)` }} />{title}
    </div>
    {subtitle && <div style={{ fontSize: 15, color: U.muted, marginTop: 7, paddingLeft: 28, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{subtitle}</div>}
    <div style={{ marginTop: 14, height: 1, background: U.rule }} />
  </div>;
}

function Tiles({ screen, frame, clickAt, labelFrames, labels = [] }: ViewProps) {
  const { cards, cardsTop, headTop, gridTop, gridH } = tilesGeometry(screen);
  const tiles = (screen.tiles || []).slice(0, 6);
  const open = clickAt === undefined ? 1 : progress(frame, clickAt + 3, 14);
  const reveal = clickAt === undefined ? 6 : clickAt + 8;
  const focus = labels.length ? progress(frame, labelFrames?.[0] ?? 40, 10) : 0;
  const tabs = screen.tabs || [];
  const cardW = (WIN.w - WIN.pad * 2 - 14 * (Math.max(1, cards.length) - 1)) / Math.max(1, cards.length);
  const tileW = (WIN.w - WIN.pad * 2 - 2) / 3;
  return <>
    <div style={{ position: "absolute", left: WIN.pad, right: WIN.pad, top: TILES.tabs, height: 44, display: "flex", gap: 30, borderBottom: `1.5px solid ${U.rule}`, opacity: progress(frame, 0, 10) }}>
      {tabs.map(t => <span key={t} style={{ fontSize: 17, fontWeight: 600, color: t === screen.tab ? U.ink : U.muted, borderBottom: t === screen.tab ? `3px solid ${U.blue}` : "3px solid transparent", paddingTop: 8, marginBottom: -1.5 }}>{t}</span>)}
    </div>
    {cards.map((m, i) => {
      const p = progress(frame, 3 + i * 3, 12);
      return <div key={m.label} style={{ position: "absolute", left: WIN.pad + i * (cardW + 14), top: cardsTop, width: cardW, height: TILES.card, borderRadius: 16, background: "#FFFFFF", border: `1.5px solid ${U.rule}`, padding: "13px 18px", opacity: p, transform: `translateY(${(1 - p) * 12}px)` }}>
        <div style={{ fontSize: 14, fontWeight: 500, color: U.muted, whiteSpace: "nowrap" }}>{m.label}</div>
        <div style={{ fontSize: 27, fontWeight: 700, color: "#334155", marginTop: 4, letterSpacing: -0.5, fontVariantNumeric: "tabular-nums" }}>{countUp(m.value, progress(frame, 5 + i * 3, 22))}</div>
      </div>;
    })}
    <SectionHeading title={screen.title || ""} subtitle={screen.subtitle} open={open} top={headTop} opacity={progress(frame, 6, 12)} />
    <div style={{ position: "absolute", left: WIN.pad, top: gridTop, width: WIN.w - WIN.pad * 2, height: gridH * open, overflow: "hidden", borderRadius: 18, border: open > 0.02 ? `1.5px solid ${U.rule}` : "none", background: U.rule, boxShadow: "0 2px 10px rgba(10,15,31,0.05)" }}>
      <div style={{ display: "grid", gridTemplateColumns: `repeat(3, ${tileW}px)`, gap: 1 }}>
        {tiles.map((t, i) => {
          const p = progress(frame, reveal + i * 3, 10);
          const count = progress(frame, reveal + 2 + i * 3, 24);
          const li = labels.indexOf(t.label);
          const cue = li >= 0 ? labelFrames?.[li] ?? 30 + li * 18 : undefined;
          const lit = cue === undefined ? 0 : progress(frame, cue, 8);
          const pulse = cue === undefined ? 0 : bumpOf(frame, cue + 3, 16);
          const dim = labels.length && li < 0 ? 1 - focus * 0.5 : 1;
          return <div key={t.label} style={{ position: "relative", height: TILES.tileH, padding: "22px 24px", background: lit > 0.02 ? `rgba(238,244,255,${0.4 + lit * 0.6})` : "#FFFFFF", boxShadow: lit > 0.02 ? `inset 0 0 0 ${2 + pulse * 2}px rgba(26,98,242,${lit})` : "none" }}>
            <div style={{ opacity: p * dim, transform: `translateY(${(1 - p) * 10}px)` }}>
              <div style={{ fontSize: 12.5, fontWeight: 600, letterSpacing: 0.6, textTransform: "uppercase", color: lit > 0.5 ? U.blue : U.muted, whiteSpace: "nowrap" }}>{t.label}</div>
              <div style={{ fontSize: 40, fontWeight: 700, color: lit > 0.5 ? U.blue : "#1E293B", marginTop: 10, letterSpacing: -0.8, fontVariantNumeric: "tabular-nums", transform: `scale(${1 + pulse * 0.06})`, transformOrigin: "left center" }}>{countAverage(t.value, count)}</div>
              {t.note && <div style={{ fontSize: 15, color: U.muted, marginTop: 8, whiteSpace: "nowrap" }}>{t.note}</div>}
            </div>
          </div>;
        })}
      </div>
    </div>
    {(screen.rows || []).map((row, i) => <SectionHeading key={row.label} title={row.label} subtitle={row.hint} open={0} top={gridTop + i * TILES.block + (gridH + 30) * open} opacity={progress(frame, 8 + i * 2, 12)} />)}
  </>;
}

/** Where the cursor lands for each view, in window coordinates. */
export function cursorTarget(screen: Screen) {
  if (screen.view === "tiles") return { x: WIN.pad + 28 + 70, y: tilesGeometry(screen).headTop + 10 };
  if (screen.view === "metrics") {
    const n = Math.min(5, screen.metrics?.length || 5), w = metricW(n), i = Math.max(0, (screen.metrics || []).findIndex(m => m.status === "failed"));
    return { x: WIN.pad + i * (w + METRIC.gap) + w - 16 - (METRIC.list - 6) / 2, y: METRIC.top + 4 + 14 + (METRIC.list - 6) / 2 };
  }
  if (screen.view === "chart") return { x: WIN.w - WIN.pad - 4 - CHART.toggleW / 2, y: CHART.toggleY + 20 };
  if (screen.view === "filters") return { x: WIN.w - 28 - FILTER.button / 2, y: WIN.h - 42 };
  if (screen.view === "cards") return { x: WIN.pad + 110, y: CARD.top + CARD.h - 34 };
  if (screen.view === "diff") return { x: WIN.w - WIN.pad - 24 - PATCH.button.w / 2, y: PATCH.top + 24 + 24 };
  return { x: WIN.w - WIN.pad - 100, y: WIN.h - 42 };
}

export function Cursor({ frame, clickAt, target, frames, hoverAt, leaveAt }: { frame: number; clickAt?: number; target: { x: number; y: number }; frames: number; hoverAt?: number; leaveAt?: number }) {
  const at = clickAt ?? hoverAt ?? Math.round(frames * 0.62);
  const start = { x: WIN.w * 0.58, y: WIN.h + 90 };
  const travel = progress(frame, at - 26, 20);
  const settle = hoverAt !== undefined && clickAt === undefined ? 0 : progress(frame, at + 8, 24);
  const x = start.x + (target.x - start.x) * travel + settle * 26;
  const y = start.y + (target.y - start.y) * travel + settle * 18 + Math.sin(frame / 9) * 1.5 * (1 - travel);
  const down = clickAt !== undefined && frame >= clickAt && frame < clickAt + 6;
  const ripple = clickAt === undefined ? 0 : progress(frame, clickAt, 16);
  const visible = progress(frame, at - 34, 8) * (leaveAt === undefined ? 1 : 1 - progress(frame, leaveAt, 10));
  return <>
    {clickAt !== undefined && frame >= clickAt && <div style={{ position: "absolute", left: target.x - 40, top: target.y - 40, width: 80, height: 80, borderRadius: 40, border: `3px solid rgba(26,98,242,${0.6 * (1 - ripple)})`, transform: `scale(${0.3 + ripple * 0.9})`, pointerEvents: "none" }} />}
    <svg width="34" height="40" viewBox="0 0 34 40" style={{ position: "absolute", left: x - 4, top: y - 3, opacity: visible, transform: `scale(${down ? 0.86 : 1})`, transformOrigin: "4px 3px", filter: "drop-shadow(0 6px 10px rgba(10,15,31,0.35))", pointerEvents: "none" }}>
      <path d="M4 3 L4 32 L11.5 25 L16.5 36.5 L21.5 34.3 L16.6 23 L27 23 Z" fill="#0A0F1F" stroke="#FFFFFF" strokeWidth="2.2" strokeLinejoin="round" />
    </svg>
  </>;
}

function Toast({ text, frame, clickAt }: { text: string; frame: number; clickAt: number }) {
  const p = progress(frame, clickAt + 4, 12);
  return <div style={{ position: "absolute", right: 28, top: WIN.bar + 18, display: "flex", alignItems: "center", gap: 12, padding: "14px 20px", borderRadius: 14, background: "#FFFFFF", border: `1.5px solid ${U.greenLine}`, boxShadow: "0 18px 40px rgba(10,15,31,0.18)", opacity: p, transform: `translateY(${(1 - p) * -18}px)`, zIndex: 5 }}>
    <CheckCircle2 size={24} color={U.green} strokeWidth={2.4} />
    <span style={{ fontSize: 19, fontWeight: 600, color: U.ink }}>{text}</span>
  </div>;
}

/** Illustrative product window: real labels and flows, fictional values, one cursor action. */
const VIEWS = { cards: Cards, diff: Diff, compare: Compare, filters: Filters, metrics: Metrics, table: Table, chart: Chart, checklist: Checklist, tiles: Tiles };

export function ProductWindow({ screen, frame, clickAt, labelFrames, labels, frames, surface = "dark" }: ViewProps & { surface?: "light" | "dark" }) {
  const clicked = clickAt !== undefined && frame >= clickAt + 2;
  const chip = clicked && screen.chip_after ? screen.chip_after : screen.chip;
  const flash = clicked && screen.chip_after ? 1 - progress(frame, clickAt! + 2, 18) : 0;
  const View = VIEWS[screen.view || "checklist"];
  return <div style={{ position: "relative", width: WIN.w, height: WIN.h, borderRadius: 26, overflow: "hidden", background: "#FBFCFE", fontFamily: sans, color: U.ink, boxShadow: surface === "light" ? "0 40px 110px rgba(26,98,242,0.24), 0 0 0 1.5px rgba(175,202,251,0.9)" : "0 50px 120px rgba(3,10,40,0.45), 0 0 0 1px rgba(255,255,255,0.6)" }}>
    <div style={{ position: "absolute", left: 0, right: 0, top: 0, height: WIN.bar, background: "#FFFFFF", borderBottom: `1.5px solid ${U.rule}`, display: "flex", alignItems: "center", padding: "0 28px", gap: 14 }}>
      <Img src={staticFile("brand-mark.svg")} style={{ width: 30, height: 30 }} />
      <span style={{ fontSize: 19, fontWeight: 700 }}>{moduleName()}</span>
      <span style={{ fontSize: 18, color: "#9AA8BD" }}>/</span>
      <span style={{ fontSize: 18, color: U.muted, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", flex: 1, minWidth: 0 }}>{screen.crumb}</span>
      {chip && <span style={{ fontSize: 16, fontWeight: 600, color: U.blue, background: `rgba(238,244,255,1)`, boxShadow: flash ? `0 0 0 ${4 * flash}px rgba(26,98,242,${0.35 * flash})` : "none", padding: "6px 12px", borderRadius: 999, whiteSpace: "nowrap" }}>{chip}</span>}
      <span style={{ fontSize: 14, fontWeight: 700, letterSpacing: 1.2, color: U.muted, border: `1.5px solid ${U.rule}`, padding: "5px 10px", borderRadius: 999 }}>ILLUSTRATIVE</span>
    </div>
    <View screen={screen} frame={frame} clickAt={clickAt} labelFrames={labelFrames} labels={labels} frames={frames} />
    {screen.toast && clickAt !== undefined && <Toast text={screen.toast} frame={frame} clickAt={clickAt} />}
    {(() => {
      // An expanded section is read, not clicked again; the pointer leaves so it never sits on the tiles.
      if (clickAt !== undefined) return <Cursor frame={frame} clickAt={clickAt} target={cursorTarget(screen)} frames={frames} leaveAt={screen.view === "tiles" ? clickAt + 28 : undefined} />;
      const hover = screen.view === "table" ? tableGeometry(screen, labels).hover : undefined;
      const cue = labelFrames?.[(labels?.length || 1) - 1];
      if (hover && cue !== undefined) return <Cursor frame={frame} target={hover} frames={frames} hoverAt={cue + 4} />;
      if (screen.view === "table" || screen.view === "metrics" || screen.view === "chart" || screen.view === "tiles") return null;
      return <Cursor frame={frame} clickAt={clickAt} target={cursorTarget(screen)} frames={frames} />;
    })()}
  </div>;
}
