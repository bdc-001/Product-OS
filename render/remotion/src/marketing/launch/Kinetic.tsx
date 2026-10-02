import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";
import { Activity } from "lucide-react";
import { body, display, emphasisMask, K, progress, seeded, useLaunch, wordCues, type Field, type LaunchScene } from "./core";

function sizeFor(count: number, portrait: boolean) {
  if (portrait) return count <= 3 ? 124 : count <= 5 ? 104 : 86;
  return count <= 3 ? 156 : count <= 5 ? 124 : 100;
}

/** The narration is the picture: each word rises out of a mask on the timestamp where it is spoken. */
export function KineticType({ scene, frame, field, text, size, align = "center", maxWidth }: {
  scene: LaunchScene; frame: number; field: Field; text?: string; size?: number; align?: "center" | "left"; maxWidth?: number;
}) {
  const { audioFrom, portrait } = useLaunch();
  const phrase = text ?? scene.headline;
  const cues = wordCues(scene, phrase, audioFrom);
  const mask = emphasisMask(phrase, scene.emphasis);
  const fontSize = size ?? sizeFor(cues.length, portrait);
  const short = cues.length <= 4;
  const light = field === "light" || field === "stage";
  const color = light ? K.ink : "#FFFFFF";
  const accent = field === "dark" ? K.sky : K.blue;
  const pills = field === "brand";
  // On the brand field an emphasized phrase shares one white pill instead of one pill per word.
  const runs: number[][] = [];
  cues.forEach((_, i) => {
    const last = runs.at(-1);
    if (pills && mask[i] && last && mask[last[0]] && last.at(-1) === i - 1) last.push(i);
    else runs.push([i]);
  });
  const word = (i: number) => {
    const { word: text, at } = cues[i];
    const p = progress(frame, at, 10);
    const lit = mask[i];
    const settle = lit && !pills ? 1 + (1 - progress(frame, at + 4, 12)) * 0.06 : 1;
    return <span key={i} style={{ display: "inline-block", overflow: "hidden", verticalAlign: "top", padding: "0.04em 0.02em 0.14em", margin: "0 -0.02em" }}>
      <span style={{
        display: "inline-block", transform: `translateY(${(1 - p) * 108}%) scale(${settle})`, transformOrigin: "50% 80%",
        color: lit ? (pills ? K.blue : accent) : undefined, opacity: p > 0.02 ? 1 : 0,
      }}>{text}</span>
    </span>;
  };
  return <div data-film-text="headline" style={{
    fontFamily: display, fontSize, lineHeight: 1.08, letterSpacing: -fontSize * 0.035, fontWeight: short ? 700 : 600,
    color, textAlign: align, maxWidth: maxWidth ?? (portrait ? 920 : 1560), overflowWrap: "break-word", textWrap: "balance",
  }}>
    {runs.map((run, r) => {
      const space = r < runs.length - 1 ? " " : "";
      if (!(pills && mask[run[0]])) return <React.Fragment key={r}>{word(run[0])}{space}</React.Fragment>;
      const radius = fontSize * 0.16;
      const p = progress(frame, cues[run[0]].at - 2, 8);
      const weight = run.reduce((sum, i) => sum + cues[i].word.length + 1, 0);
      // The pill sweeps rightward with the words as they are spoken, like a highlighter.
      const sweep = run.reduce((sum, i) => sum + (cues[i].word.length + 1) * progress(frame, cues[i].at - 2, 9), 0) / weight;
      const settle = 1 + (1 - progress(frame, cues[run.at(-1)!].at + 4, 12)) * 0.05;
      return <React.Fragment key={r}>
        <span style={{ position: "relative", display: "inline-block", verticalAlign: "top", padding: `0 ${fontSize * 0.14}px`, transform: `scale(${settle})`, transformOrigin: "0% 60%" }}>
          <span style={{
            position: "absolute", left: 0, top: 0, bottom: 0, width: `max(${radius * 2}px, ${sweep * 100}%)`, borderRadius: radius,
            background: "#FFFFFF", boxShadow: "0 18px 40px rgba(6,34,120,0.35)", opacity: p,
          }} />
          <span style={{ position: "relative" }}>{run.map((i, k) => <React.Fragment key={i}>{word(i)}{k < run.length - 1 ? " " : ""}</React.Fragment>)}</span>
        </span>{space}
      </React.Fragment>;
    })}
  </div>;
}

export function Kinetic({ scene, frame, field }: { scene: LaunchScene; frame: number; field: Field }) {
  const { portrait } = useLaunch();
  const push = 1 + progress(frame, 0, Math.max(30, scene.frames)) * 0.035;
  return <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", padding: portrait ? "0 80px" : "0 150px" }}>
    <div style={{ transform: `scale(${push})` }}><KineticType scene={scene} frame={frame} field={field} /></div>
  </AbsoluteFill>;
}

/** Volume without a metric: interaction cards multiply outward while the camera pulls back. */
export function Volume({ scene, frame, global }: { scene: LaunchScene; frame: number; global: number }) {
  const { portrait } = useLaunch();
  const cols = portrait ? 5 : 9, rows = portrait ? 9 : 6;
  const w = portrait ? 188 : 196, h = portrait ? 150 : 128, gap = 18;
  const gridW = cols * w + (cols - 1) * gap, gridH = rows * h + (rows - 1) * gap;
  const pull = 1.55 - progress(frame, 0, Math.max(40, scene.frames * 0.8)) * 0.55;
  const cards = [];
  for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
    const i = r * cols + c;
    const d = Math.hypot(c - (cols - 1) / 2, r - (rows - 1) / 2);
    const at = 2 + d * 4.2;
    const p = progress(frame, at, 10);
    const flagged = seeded(i) > 0.72;
    const minutes = 1 + Math.floor(seeded(i + 9) * 4), seconds = Math.floor(seeded(i + 3) * 59);
    cards.push(<div key={i} style={{
      position: "absolute", left: c * (w + gap), top: r * (h + gap), width: w, height: h, borderRadius: 16,
      background: "linear-gradient(160deg, rgba(26,98,242,0.28), rgba(10,46,122,0.55))", border: "1px solid rgba(175,202,251,0.28)",
      padding: "14px 16px", opacity: p, transform: `scale(${0.7 + p * 0.3})`, boxShadow: "0 12px 30px rgba(3,6,15,0.4)",
      display: "flex", flexDirection: "column", justifyContent: "space-between", color: "#DCE7FF",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 15, fontFamily: body, opacity: 0.8 }}>
        <span>AI call</span><span>{`0${minutes}:${String(seconds).padStart(2, "0")}`}</span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 3, height: 40 }}>
        {Array.from({ length: 16 }, (_, b) => {
          const live = 0.35 + 0.65 * Math.abs(Math.sin(global * 0.08 + b * 0.7 + i));
          return <div key={b} style={{ width: 4, borderRadius: 2, height: 6 + seeded(i * 16 + b) * 28 * live, background: flagged ? "#FFB4A8" : K.line, opacity: 0.85 }} />;
        })}
      </div>
      <div style={{ height: 6, borderRadius: 3, width: `${40 + seeded(i + 5) * 50}%`, background: flagged ? "#FF8A7A" : "rgba(175,202,251,0.45)" }} />
    </div>);
  }
  return <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
    <div style={{ position: "relative", width: gridW, height: gridH, transform: `scale(${pull}) rotate(-4deg)`, transformOrigin: "center" }}>{cards}</div>
    <AbsoluteFill style={{ background: "radial-gradient(ellipse at 50% 50%, rgba(3,6,15,0.82) 0%, rgba(3,6,15,0.55) 38%, transparent 72%)" }} />
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", padding: portrait ? "0 70px" : "0 180px" }}>
      <KineticType scene={scene} frame={frame} field="dark" size={portrait ? 86 : 104} />
    </AbsoluteFill>
  </AbsoluteFill>;
}

/** A designed close: brand field, white lockup, the closing line, and the feature mark. */
export function EndCard({ scene, frame }: { scene: LaunchScene; frame: number }) {
  const { portrait, title } = useLaunch();
  const product = (title.split(":")[0] || title).trim();
  const logo = progress(frame, 0, 16);
  const cues = wordCues(scene, scene.headline, useLaunch().audioFrom);
  const badge = progress(frame, (cues.at(-1)?.at ?? 20) + 8, 14);
  return <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", flexDirection: "column", gap: portrait ? 56 : 46, padding: portrait ? "0 80px" : "0 160px" }}>
    <Img src={staticFile("brand-logo-dark.svg")} style={{ width: portrait ? 330 : 360, opacity: logo, transform: `translateY(${(1 - logo) * -24}px) scale(${0.92 + logo * 0.08})`, filter: "drop-shadow(0 12px 40px rgba(6,34,120,0.45))" }} />
    <KineticType scene={scene} frame={frame} field="brand" size={portrait ? 92 : 96} />
    <div style={{ display: "flex", alignItems: "center", gap: 18, padding: "16px 30px 16px 18px", borderRadius: 999, background: "rgba(255,255,255,0.14)", border: "1.5px solid rgba(255,255,255,0.45)", opacity: badge, transform: `translateY(${(1 - badge) * 20}px)`, boxShadow: "0 24px 60px rgba(6,34,120,0.35)" }}>
      <div style={{ width: 54, height: 54, borderRadius: 27, background: "#FFFFFF", color: K.blue, display: "grid", placeItems: "center" }}><Activity size={30} strokeWidth={2.2} /></div>
      <span data-film-text="badge" style={{ fontFamily: display, fontWeight: 700, fontSize: portrait ? 40 : 38, color: "#FFFFFF", letterSpacing: -0.5 }}>{product}</span>
    </div>
    {scene.body && <div data-film-text="body" style={{ fontFamily: body, fontSize: portrait ? 32 : 30, color: "#DCE7FF", opacity: progress(frame, (cues.at(-1)?.at ?? 20) + 16, 14), textAlign: "center" }}>{scene.body}</div>}
  </AbsoluteFill>;
}
