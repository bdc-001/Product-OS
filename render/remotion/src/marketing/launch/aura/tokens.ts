import { useEffect, useState } from "react";
import { continueRender, delayRender, Easing, interpolate, spring, staticFile } from "remotion";
import { FPS } from "../core";

/** Aura: the brand blue softened into an airy white field. Every tint stays inside the brand ramp,
 *  the tertiary blues and the logo-mark cyan; amber is a rare spark on one object. */
export const A = {
  blue: "#1A62F2", glow: "#7FA8FF", mist: "#E9EFFF", field: "#FAFBFD", ink: "#161A23", muted: "#6B7280",
  haze: "#D6E4FF", lilac: "#BFD4FF", periwinkle: "#A7C3FF", mark: "#6699FF", cyan: "#5FE6EB", amber: "#F8AA0D",
  navy: "#0A2E7A", rule: "#E6EAF2", card: "#FFFFFF",
};

/** Gradient pairs for objects: light face to deep edge. */
export const TINTS: [string, string][] = [
  ["#BFD4FF", "#1A62F2"], ["#D6E4FF", "#6699FF"], ["#C9F6F8", "#5FE6EB"], ["#E3EAFF", "#7FA8FF"], ["#A7C3FF", "#144ECF"],
];

export const auraSans = "'Inter Aura', Inter, 'Helvetica Neue', Arial, sans-serif";
export const auraSerif = "'Instrument Serif', Georgia, 'Times New Roman', serif";

/** Moves commit fast and land soft (a short wind-up, then a long settle); arrivals are an expo-out. */
export const auraEase = Easing.bezier(0.5, 0, 0.1, 1);
export const auraOut = Easing.bezier(0.16, 1, 0.3, 1);

export const glide = (frame: number, start = 0, duration = 16) =>
  interpolate(frame, [start, start + duration], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: auraEase });
export const rise = (frame: number, start = 0, duration = 12) =>
  interpolate(frame, [start, start + duration], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: auraOut });
/** Constant-speed travel across a span: the camera never parks. */
export const along = (frame: number, span: number) => Math.max(0, Math.min(1, frame / Math.max(1, span)));

/** Deterministic spring on the film clock: objects pop in with a little overshoot and settle quickly. */
export const springAt = (frame: number, at: number, config: { damping?: number; stiffness?: number; mass?: number } = {}) =>
  frame < at ? 0 : spring({ frame: frame - at, fps: FPS, config: { damping: 14, stiffness: 190, mass: 0.6, ...config } });

/** Launch-film tempo: a character lands in a third of a second, a morph in under half a second. */
export const BEAT = { char: 0.7, charIn: 9, dissolve: 9, overlap: 12, settle: 14 };

export const AURA_FONTS = [
  { family: "Inter Aura", file: "Inter-Variable.ttf", weight: "100 900", style: "normal" },
  { family: "Instrument Serif", file: "InstrumentSerif-Regular.ttf", weight: "400", style: "normal" },
  { family: "Instrument Serif", file: "InstrumentSerif-Italic.ttf", weight: "400", style: "italic" },
];

/** Aura faces load before the first frame; a film rendered from an older media folder falls back to Inter. */
export function useAuraFonts(active: boolean) {
  const [handle] = useState(() => (active ? delayRender("Aura fonts") : null));
  useEffect(() => {
    if (handle === null) return;
    Promise.all(AURA_FONTS.map(async font => {
      try {
        const face = new FontFace(font.family, `url('${staticFile(font.file)}') format('truetype')`, { weight: font.weight, style: font.style });
        await face.load();
        (document.fonts as unknown as { add: (f: FontFace) => void }).add(face);
      } catch {
        // Missing optional face: the stack falls back to Inter.
      }
    })).finally(() => continueRender(handle));
  }, [handle]);
}
