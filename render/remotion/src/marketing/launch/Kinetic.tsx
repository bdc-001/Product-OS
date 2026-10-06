import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";
import { Activity } from "lucide-react";
import { body, display, emphasisMask, FPS, K, progress, seeded, useLaunch, wordCues, type Field, type LaunchScene } from "./core";

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
  // A headline always completes before the cut, even when its last word is spoken at the very end of the shot.
  const cues = wordCues(scene, phrase, audioFrom).map(cue => ({ ...cue, at: Math.min(cue.at, Math.max(2, scene.frames - 16)) }));
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

/** The brand mark in black and white: two tones of grey, as on the reference title and close cards. */
const MONO = "grayscale(1) brightness(0.62) contrast(1.9)";

const WHITE = "brightness(0) invert(1)";

/** "Presenting <feature> by <company>" in one of four title-card designs from the reference films; the film log
 *  rotates them so consecutive films never open their reveal the same way. */
export function Presenting({ scene, frame, look }: { scene: LaunchScene; frame: number; look?: string }) {
  if (look === "lockup") return <PresentingLockup scene={scene} frame={frame} />;
  if (look === "bold") return <PresentingBold scene={scene} frame={frame} />;
  if (look === "hub") return <PresentingHub scene={scene} frame={frame} />;
  return <PresentingType scene={scene} frame={frame} />;
}

/** Full-bleed brand blue: the white lockup settles from oversize, a rule draws, the feature name rises under it. */
function PresentingLockup({ scene, frame }: { scene: LaunchScene; frame: number }) {
  const { portrait, product, module } = useLaunch();
  const logo = progress(frame, 0, 20);
  const rule = progress(frame, 16, 16);
  const feature = progress(frame, 24, 16);
  const kicker = progress(frame, 30, 14);
  return <AbsoluteFill style={{ background: "linear-gradient(135deg, #2F72FF 0%, #1A62F2 50%, #0C45C4 100%)", alignItems: "center", justifyContent: "center", flexDirection: "column" }}>
    <Img src={staticFile("brand-logo-dark.svg")} style={{ width: portrait ? 640 : 720, filter: WHITE, opacity: logo, transform: `scale(${1.25 - logo * 0.25})` }} />
    <div style={{ width: (portrait ? 640 : 720) * rule, height: 2, background: "rgba(255,255,255,0.65)", margin: portrait ? "54px 0 44px" : "46px 0 36px" }} />
    <div data-film-text="headline" style={{ fontFamily: display, fontWeight: 700, fontSize: portrait ? 76 : 84, color: "#FFFFFF", letterSpacing: -1, textAlign: "center", maxWidth: portrait ? 940 : 1500,
      opacity: feature, transform: `translateY(${(1 - feature) * 26}px)` }}>{scene.headline}</div>
    <div data-film-text="label" style={{ fontFamily: body, fontWeight: 600, fontSize: portrait ? 30 : 26, letterSpacing: 6, color: "rgba(255,255,255,0.72)", textTransform: "uppercase", marginTop: 22, opacity: kicker }}>
      {product || module}
    </div>
  </AbsoluteFill>;
}

/** White page with a blue gloss in the corner: the feature name in heavy blue type, revealed line by line from a mask. */
function PresentingBold({ scene, frame }: { scene: LaunchScene; frame: number }) {
  const { portrait, product, module } = useLaunch();
  const words = scene.headline.toUpperCase().split(/\s+/).filter(Boolean);
  const head = progress(frame, 0, 14);
  const size = portrait ? 120 : Math.min(150, 2400 / Math.max(8, scene.headline.length));
  const t = frame / FPS;
  return <AbsoluteFill style={{ background: "#FFFFFF", overflow: "hidden" }}>
    <div style={{ position: "absolute", right: -260 + Math.sin(t * 0.4) * 20, top: -300, width: 900, height: 900, borderRadius: "50%", filter: "blur(70px)",
      background: "radial-gradient(circle, rgba(26,98,242,0.85) 0%, rgba(127,168,255,0.5) 45%, transparent 70%)" }} />
    <div style={{ position: "absolute", left: -200, bottom: -380, width: 800, height: 800, borderRadius: "50%", filter: "blur(80px)",
      background: "radial-gradient(circle, rgba(175,202,251,0.8) 0%, transparent 70%)" }} />
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", flexDirection: "column", padding: portrait ? "0 70px" : "0 160px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 16, opacity: head, transform: `translateY(${(1 - head) * -16}px)`, marginBottom: portrait ? 40 : 34 }}>
        <Img src={staticFile("brand-mark.svg")} style={{ width: 44, filter: MONO }} />
        <span data-film-text="label" style={{ fontFamily: body, fontWeight: 600, fontSize: portrait ? 30 : 26, letterSpacing: 5, color: "#3D4450", textTransform: "uppercase" }}>{product || module}</span>
      </div>
      <div data-film-text="headline" style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", columnGap: size * 0.28, rowGap: 0, maxWidth: portrait ? 940 : 1600 }}>
        {words.map((word, i) => {
          const p = progress(frame, 8 + i * 6, 16);
          return <span key={i} style={{ display: "inline-block", overflow: "hidden", paddingBottom: size * 0.08 }}>
            <span style={{ display: "inline-block", fontFamily: display, fontWeight: 800, fontSize: size, lineHeight: 1.02, letterSpacing: -size * 0.03, color: K.blue, transform: `translateY(${(1 - p) * 110}%)` }}>{word}</span>
          </span>;
        })}
      </div>
    </AbsoluteFill>
  </AbsoluteFill>;
}

/** Dark field: the mark sits in turning rings, then slides aside as a glass card with the feature name joins it. */
function PresentingHub({ scene, frame }: { scene: LaunchScene; frame: number }) {
  const { portrait, product, module } = useLaunch();
  const land = progress(frame, 0, 18);
  const split = progress(frame, 18, 20);
  const card = progress(frame, 26, 18);
  const hubX = portrait ? 0 : -330 * split, hubY = portrait ? -260 * split : 0;
  return <AbsoluteFill style={{ background: "radial-gradient(120% 90% at 50% 50%, #0E2A78 0%, #07122F 45%, #000000 100%)", overflow: "hidden" }}>
    <AbsoluteFill style={{ opacity: 0.18, backgroundSize: "60px 60px", backgroundImage: "linear-gradient(rgba(127,168,255,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(127,168,255,0.5) 1px, transparent 1px)",
      maskImage: "radial-gradient(ellipse at 50% 50%, black 0%, transparent 65%)", WebkitMaskImage: "radial-gradient(ellipse at 50% 50%, black 0%, transparent 65%)" }} />
    <div style={{ position: "absolute", left: "50%", top: "50%", transform: `translate(calc(-50% + ${hubX}px), calc(-50% + ${hubY}px)) scale(${0.6 + land * 0.4})`, opacity: land }}>
      {[0, 1, 2].map(k => <div key={k} style={{ position: "absolute", left: "50%", top: "50%", width: 240 + k * 90, height: 240 + k * 90, marginLeft: -(120 + k * 45), marginTop: -(120 + k * 45), borderRadius: "50%",
        border: `1.5px ${k === 1 ? "dashed" : "solid"} rgba(127,168,255,${0.55 - k * 0.15})`, transform: `rotate(${frame * (k % 2 ? -0.8 : 0.6)}deg)` }} />)}
      <div style={{ width: 200, height: 200, borderRadius: 100, background: "rgba(255,255,255,0.06)", border: "1.5px solid rgba(255,255,255,0.35)", display: "grid", placeItems: "center", boxShadow: "0 0 80px rgba(26,98,242,0.55)" }}>
        <Img src={staticFile("brand-mark.svg")} style={{ width: 96, filter: WHITE }} />
      </div>
    </div>
    {!portrait && <div style={{ position: "absolute", left: 960 - 330 + 190, top: 538, width: 150 * split, height: 2, background: "linear-gradient(90deg, rgba(127,168,255,0.9), rgba(127,168,255,0.2))" }} />}
    <div style={{ position: "absolute", ...(portrait ? { left: 90, width: 900, top: 900 } : { left: 980, width: 720, top: 380 }), padding: "40px 44px", borderRadius: 28,
      background: "rgba(255,255,255,0.08)", border: "1.5px solid rgba(255,255,255,0.3)", backdropFilter: "blur(24px)", boxShadow: "0 40px 100px rgba(0,0,0,0.5)",
      opacity: card, transform: `translateX(${(1 - card) * 60}px)` }}>
      <div data-film-text="label" style={{ fontFamily: body, fontWeight: 600, fontSize: 24, letterSpacing: 5, color: "#8FB4FF", textTransform: "uppercase" }}>{product || module}</div>
      <div data-film-text="headline" style={{ fontFamily: display, fontWeight: 700, fontSize: portrait ? 84 : 76, lineHeight: 1.04, color: "#FFFFFF", letterSpacing: -1.5, marginTop: 16 }}>{scene.headline}</div>
    </div>
  </AbsoluteFill>;
}

/** The mark spins in from full frame, the product wordmark types on, the feature settles under it. */
function PresentingType({ scene, frame }: { scene: LaunchScene; frame: number }) {
  const { portrait, product, module } = useLaunch();
  const words = (product || module || "").toUpperCase().split(/\s+/).filter(Boolean);
  const lead = words.length > 1 ? words.slice(0, -1).join(" ") : words[0] || "";
  const typed = words.length > 1 ? words.at(-1)! : "";
  const land = progress(frame, 0, 22);
  const word = progress(frame, 16, 12);
  const letters = Math.floor(Math.max(0, frame - 24) / 2.2);
  const feature = progress(frame, 24 + typed.length * 2.2 + 4, 14);
  const note = progress(frame, 24 + typed.length * 2.2 + 16, 14);
  const size = portrait ? 92 : 104;
  return <AbsoluteFill style={{ background: "#FFFFFF", alignItems: "center", justifyContent: "center", flexDirection: "column" }}>
    <Img src={staticFile("brand-mark.svg")} style={{ width: portrait ? 230 : 210, filter: MONO, opacity: Math.min(1, land * 2),
      transform: `scale(${1 + (1 - land) * 5}) rotate(${(1 - land) * -120}deg)`, marginBottom: portrait ? 40 : 30 }} />
    <div data-film-text="headline" style={{ fontFamily: display, fontWeight: 800, fontSize: size, letterSpacing: -size * 0.02, lineHeight: 1, whiteSpace: "nowrap",
      opacity: word, transform: `translateY(${(1 - word) * 30}px)` }}>
      <span style={{ color: "#111111" }}>{lead}</span>
      {typed && <span style={{ color: K.blue }}>{" "}{typed.slice(0, letters)}<span style={{ opacity: letters < typed.length && frame % 16 < 9 ? 1 : 0, color: K.blue, fontWeight: 300 }}>|</span></span>}
    </div>
    <div data-film-text="label" style={{ fontFamily: body, fontWeight: 500, fontSize: portrait ? 44 : 40, letterSpacing: portrait ? 6 : 8, color: "#5F6670", textTransform: "uppercase",
      marginTop: portrait ? 34 : 26, opacity: feature, transform: `translateY(${(1 - feature) * 16}px)`, textAlign: "center", maxWidth: portrait ? 940 : 1500 }}>{scene.headline}</div>
    {scene.body && <div data-film-text="body" style={{ fontFamily: body, fontSize: portrait ? 30 : 26, color: "#8A9099", marginTop: portrait ? 40 : 34, opacity: note, textAlign: "center", maxWidth: portrait ? 900 : 1100 }}>{scene.body}</div>}
  </AbsoluteFill>;
}

/** The close in one of five designs; the film log rotates them like the title card. */
export function EndCard({ scene, frame, look }: { scene: LaunchScene; frame: number; look?: string }) {
  const { steps } = useLaunch();
  const card = look === "recap" && (steps?.length ?? 0) >= 2 ? <EndRecap scene={scene} frame={frame} />
    : look === "poster" || look === "recap" ? <EndPoster scene={scene} frame={frame} />
    : look === "lockup" ? <EndLockup scene={scene} frame={frame} />
    : look === "ink" ? <EndInk scene={scene} frame={frame} /> : <EndMono scene={scene} frame={frame} />;
  // The film craft gate fails any sampled run held identical for over a second, so the close keeps drifting.
  return <AbsoluteFill style={{ transform: `scale(${1 + 0.07 * frame / Math.max(1, scene.frames)})` }}>{card}</AbsoluteFill>;
}

/** The film's product steps tick down a numbered rail on the right while the tagline lands on the left. */
function EndRecap({ scene, frame }: { scene: LaunchScene; frame: number }) {
  const { portrait, title, audioFrom, steps = [] } = useLaunch();
  const product = (title.split(":")[0] || title).trim();
  const cues = wordCues(scene, scene.headline, audioFrom);
  const logo = progress(frame, 0, 14);
  const rail = progress(frame, 4, Math.max(20, steps.length * 9));
  const badge = progress(frame, (cues.at(-1)?.at ?? 20) + 8, 14);
  const rowH = portrait ? 104 : 112;
  const list = <div style={{ position: "relative", paddingLeft: 0 }}>
    <div style={{ position: "absolute", left: 27, top: 28, width: 3, height: (steps.length - 1) * rowH * rail, background: K.blue, borderRadius: 2 }} />
    {steps.map((step, i) => {
      const p = progress(frame, 6 + i * 9, 12);
      return <div key={i} style={{ display: "flex", alignItems: "center", gap: 26, height: rowH, opacity: p, transform: `translateX(${(1 - p) * 30}px)` }}>
        <div style={{ position: "relative", width: 58, height: 58, flex: "none", borderRadius: 29, background: K.blue, color: "#FFFFFF", display: "grid", placeItems: "center",
          fontFamily: display, fontWeight: 700, fontSize: 26, boxShadow: "0 12px 28px rgba(26,98,242,0.3)" }}>{i + 1}</div>
        <span data-film-text="label" style={{ fontFamily: display, fontWeight: 600, fontSize: portrait ? 40 : 38, color: K.ink, letterSpacing: -0.5 }}>{step}</span>
      </div>;
    })}
  </div>;
  return <AbsoluteFill style={{ background: "linear-gradient(115deg, #FFFFFF 0%, #FFFFFF 52%, #EEF4FF 52%, #E3ECFA 100%)" }}>
    <div style={{ position: "absolute", ...(portrait ? { left: 80, right: 80, top: 160 } : { left: 150, width: 760, top: 0, bottom: 0 }), display: "flex", flexDirection: "column", justifyContent: "center", gap: 40 }}>
      <Img src={staticFile("brand-logo-light.svg")} style={{ width: 230, filter: MONO, opacity: logo, objectFit: "contain", objectPosition: "left" }} />
      <KineticType scene={scene} frame={frame} field="light" size={portrait ? 88 : 84} align="left" maxWidth={portrait ? 920 : 760} />
      <div style={{ alignSelf: "flex-start", padding: "12px 26px", borderRadius: 999, background: K.ink, opacity: badge, transform: `translateY(${(1 - badge) * 16}px)` }}>
        <span data-film-text="badge" style={{ fontFamily: display, fontWeight: 700, fontSize: portrait ? 34 : 30, color: "#FFFFFF" }}>{product}</span>
      </div>
    </div>
    <div style={{ position: "absolute", ...(portrait ? { left: 80, right: 80, top: 1160 } : { left: 1060, width: 720, top: 0, bottom: 0 }), display: "flex", flexDirection: "column", justifyContent: "center" }}>{list}</div>
  </AbsoluteFill>;
}

/** Full-bleed brand blue: the tagline set large and flush left at the foot of the frame, like a campaign poster. */
function EndPoster({ scene, frame }: { scene: LaunchScene; frame: number }) {
  const { portrait, title, audioFrom } = useLaunch();
  const product = (title.split(":")[0] || title).trim();
  const cues = wordCues(scene, scene.headline, audioFrom);
  const top = progress(frame, 0, 16);
  const rule = progress(frame, (cues.at(-1)?.at ?? 20) + 4, 18);
  const t = frame / FPS;
  return <AbsoluteFill style={{ background: "linear-gradient(160deg, #2F72FF 0%, #1A62F2 45%, #0A2E7A 100%)", overflow: "hidden" }}>
    <div style={{ position: "absolute", right: -320 + Math.sin(t * 0.5) * 24, top: -380, width: 1100, height: 1100, borderRadius: "50%", border: "2px solid rgba(255,255,255,0.16)" }} />
    <div style={{ position: "absolute", right: -160 + Math.sin(t * 0.5) * 24, top: -220, width: 780, height: 780, borderRadius: "50%", background: "radial-gradient(circle, rgba(127,168,255,0.35) 0%, transparent 70%)" }} />
    <div style={{ position: "absolute", left: portrait ? 80 : 120, right: portrait ? 80 : 120, top: portrait ? 110 : 80, display: "flex", justifyContent: "space-between", alignItems: "center", opacity: top }}>
      <Img src={staticFile("brand-logo-dark.svg")} style={{ width: 200, filter: WHITE, objectFit: "contain", objectPosition: "left" }} />
      <span data-film-text="label" style={{ fontFamily: body, fontWeight: 600, fontSize: portrait ? 24 : 22, letterSpacing: 5, color: "rgba(255,255,255,0.78)", textTransform: "uppercase" }}>{product}</span>
    </div>
    <div style={{ position: "absolute", left: portrait ? 80 : 120, right: portrait ? 80 : 300, bottom: portrait ? 260 : 150 }}>
      <KineticType scene={scene} frame={frame} field="dark" size={portrait ? 104 : 124} align="left" maxWidth={portrait ? 920 : 1450} />
      <div style={{ width: 260 * rule, height: 5, borderRadius: 3, background: "#FFFFFF", marginTop: 40 }} />
      {scene.body && <div data-film-text="body" style={{ fontFamily: body, fontSize: portrait ? 30 : 28, color: "rgba(255,255,255,0.75)", marginTop: 26, opacity: rule, maxWidth: 1100 }}>{scene.body}</div>}
    </div>
  </AbsoluteFill>;
}

/** The tagline alone on white, then it lifts away and the lockup lands large in the middle, as the references close. */
function EndLockup({ scene, frame }: { scene: LaunchScene; frame: number }) {
  const { portrait, audioFrom } = useLaunch();
  const cues = wordCues(scene, scene.headline, audioFrom);
  const turn = Math.min(scene.frames - 40, (cues.at(-1)?.at ?? 20) + 22);
  // The lockup lands before the tagline leaves; a crossfade through bare white reads as a blank frame.
  const logo = progress(frame, turn, 14);
  const out = progress(frame, turn + 8, 12);
  return <AbsoluteFill style={{ background: "#FFFFFF" }}>
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", padding: portrait ? "0 80px" : "0 180px", opacity: 1 - out, transform: `translateY(${-logo * 150 - out * 60}px)` }}>
      <KineticType scene={scene} frame={frame} field="light" size={portrait ? 92 : 100} />
    </AbsoluteFill>
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", opacity: logo, transform: `translateY(${(1 - logo) * 120}px)` }}>
      <Img src={staticFile("brand-logo-light.svg")} style={{ width: portrait ? 640 : 760, filter: MONO, transform: `scale(${0.86 + logo * 0.14})` }} />
    </AbsoluteFill>
  </AbsoluteFill>;
}

/** Black field, white lockup, the tagline in white and the feature as a white pill. */
function EndInk({ scene, frame }: { scene: LaunchScene; frame: number }) {
  const { portrait, title, audioFrom } = useLaunch();
  const product = (title.split(":")[0] || title).trim();
  const logo = progress(frame, 0, 16);
  const cues = wordCues(scene, scene.headline, audioFrom);
  const badge = progress(frame, (cues.at(-1)?.at ?? 20) + 8, 14);
  return <AbsoluteFill style={{ background: "radial-gradient(120% 100% at 50% 120%, #1B1B1B 0%, #0A0A0A 60%, #000000 100%)", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: portrait ? 56 : 46, padding: portrait ? "0 80px" : "0 160px" }}>
    <Img src={staticFile("brand-logo-dark.svg")} style={{ width: portrait ? 360 : 400, filter: WHITE, opacity: logo, transform: `translateY(${(1 - logo) * -24}px)` }} />
    <KineticType scene={scene} frame={frame} field="dark" size={portrait ? 92 : 96} />
    <div style={{ padding: "14px 30px", borderRadius: 999, background: "#FFFFFF", opacity: badge, transform: `translateY(${(1 - badge) * 20}px)` }}>
      <span data-film-text="badge" style={{ fontFamily: display, fontWeight: 700, fontSize: portrait ? 38 : 34, color: "#111111", letterSpacing: -0.4 }}>{product}</span>
    </div>
    {scene.body && <div data-film-text="body" style={{ fontFamily: body, fontSize: portrait ? 32 : 28, color: "rgba(255,255,255,0.6)", opacity: progress(frame, (cues.at(-1)?.at ?? 20) + 16, 14), textAlign: "center" }}>{scene.body}</div>}
  </AbsoluteFill>;
}

/** A designed close on white: the black-and-white lockup, the closing line, and the feature name. */
function EndMono({ scene, frame }: { scene: LaunchScene; frame: number }) {
  const { portrait, title } = useLaunch();
  const product = (title.split(":")[0] || title).trim();
  const logo = progress(frame, 0, 16);
  const cues = wordCues(scene, scene.headline, useLaunch().audioFrom);
  const badge = progress(frame, (cues.at(-1)?.at ?? 20) + 8, 14);
  return <AbsoluteFill style={{ background: "#FFFFFF", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: portrait ? 56 : 46, padding: portrait ? "0 80px" : "0 160px" }}>
    <Img src={staticFile("brand-logo-light.svg")} style={{ width: portrait ? 360 : 400, filter: MONO, opacity: logo, transform: `translateY(${(1 - logo) * -24}px) scale(${0.92 + logo * 0.08})` }} />
    <KineticType scene={scene} frame={frame} field="light" size={portrait ? 92 : 96} />
    <div style={{ display: "flex", alignItems: "center", gap: 16, padding: "14px 28px 14px 16px", borderRadius: 999, background: "#111111", opacity: badge, transform: `translateY(${(1 - badge) * 20}px)` }}>
      <div style={{ width: 48, height: 48, borderRadius: 24, background: "#FFFFFF", color: "#111111", display: "grid", placeItems: "center" }}><Activity size={26} strokeWidth={2.2} /></div>
      <span data-film-text="badge" style={{ fontFamily: display, fontWeight: 700, fontSize: portrait ? 38 : 34, color: "#FFFFFF", letterSpacing: -0.4 }}>{product}</span>
    </div>
    {scene.body && <div data-film-text="body" style={{ fontFamily: body, fontSize: portrait ? 32 : 28, color: "#5F6670", opacity: progress(frame, (cues.at(-1)?.at ?? 20) + 16, 14), textAlign: "center" }}>{scene.body}</div>}
  </AbsoluteFill>;
}
