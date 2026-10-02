import { Contact, Grid3x3, Mic, Phone, UserPlus, Video, Volume2 } from "lucide-react";
import React from "react";

/** iPhone 15 Pro logical points. Screen content is authored at 3× (1170×2532) and scaled in. */
export const IPHONE = { width: 393, height: 852, radius: 55, bezel: 10, island: { width: 126, height: 37 } };
export const IPHONE_OUTER = { width: IPHONE.width + IPHONE.bezel * 2, height: IPHONE.height + IPHONE.bezel * 2 };
export const SCREEN = { width: 1179, height: 2556 };

export function lockupFile(luma: "dark" | "light") {
  return luma === "dark" ? "brand-logo-dark.svg" : "brand-logo-light.svg";
}

export function headerInk(luma: "dark" | "light") {
  return luma === "dark" ? "#BED6FF" : "#5A6B85";
}

function StatusBar({ appearance }: { appearance: "light" | "dark" }) {
  const ink = appearance === "dark" ? "#F1F1F1" : "#050505";
  return <div style={{ position: "absolute", top: 14, left: 28, right: 28, height: 36, display: "flex", alignItems: "center", justifyContent: "space-between", zIndex: 6, pointerEvents: "none" }}>
    <span style={{ fontSize: 17, fontWeight: 600, color: ink, letterSpacing: 0.3, width: 64 }}>9:41</span>
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <svg width="18" height="12" viewBox="0 0 18 12"><rect x="0" y="8" width="3" height="4" rx="0.6" fill={ink}/><rect x="5" y="5" width="3" height="7" rx="0.6" fill={ink}/><rect x="10" y="2" width="3" height="10" rx="0.6" fill={ink}/><rect x="15" y="0" width="3" height="12" rx="0.6" fill={ink} opacity={0.35}/></svg>
      <svg width="16" height="12" viewBox="0 0 16 12"><path d="M1 8.5a7 7 0 0 1 14 0" fill="none" stroke={ink} strokeWidth="1.4" strokeLinecap="round"/><path d="M4 9.2a4 4 0 0 1 8 0" fill="none" stroke={ink} strokeWidth="1.4" strokeLinecap="round"/><circle cx="8" cy="10.5" r="1.1" fill={ink}/></svg>
      <div style={{ width: 27, height: 12, border: `1.4px solid ${ink}`, borderRadius: 3.5, opacity: 0.9, position: "relative" }}>
        <div style={{ position: "absolute", inset: 1.5, width: "72%", borderRadius: 1.5, background: ink }} />
        <div style={{ position: "absolute", right: -3, top: 3.5, width: 1.6, height: 5, borderRadius: 1, background: ink, opacity: 0.55 }} />
      </div>
    </div>
  </div>;
}

export function IOSCallButton({ kind, active = false, danger = false, size = 192 }: { kind: string; active?: boolean; danger?: boolean; size?: number }) {
  const fill = danger ? "#FF3B30" : active ? "#FFFFFF" : "rgba(255,255,255,0.18)";
  const iconSize = Math.round(size * 0.36);
  const icon = kind === "Mute" ? <Mic size={iconSize} strokeWidth={1.75} />
    : kind === "Keypad" ? <Grid3x3 size={iconSize} strokeWidth={1.75} />
    : kind === "Speaker" ? <Volume2 size={iconSize} strokeWidth={1.75} />
    : kind === "Add call" ? <UserPlus size={iconSize} strokeWidth={1.75} />
    : kind === "FaceTime" ? <Video size={iconSize} strokeWidth={1.75} />
    : kind === "Contacts" ? <Contact size={iconSize} strokeWidth={1.75} />
    : <Phone size={iconSize} strokeWidth={1.75} />;
  return <div style={{ width: size, height: size, borderRadius: size / 2, background: fill, color: active && !danger ? "#202834" : "white", display: "grid", placeItems: "center" }}>{icon}</div>;
}

/** Persistent device chrome. Black island and bezel only sit on a light stage; in-call screens go dark inside the glass. */
export function IPhone({ children, scale = 1, ringing = false, beat = 0, appearance = "light", style }: {
  children: React.ReactNode; scale?: number; ringing?: boolean; beat?: number; appearance?: "light" | "dark"; style?: React.CSSProperties;
}) {
  const { width: W, height: H, radius, bezel } = IPHONE;
  const outerW = W + bezel * 2, outerH = H + bezel * 2;
  const glow = ringing
    ? `0 28px 70px rgba(26,98,242,0.28), 0 0 ${18 + beat * 36}px rgba(26,98,242,0.32)`
    : "0 28px 64px rgba(10,22,48,0.22)";
  const innerScale = W / SCREEN.width;
  return <div style={{
    width: outerW * scale, height: outerH * scale, position: "relative", flexShrink: 0,
    transform: ringing ? `scale(${1 + beat * 0.01})` : undefined, transformOrigin: "center top", ...style,
  }}>
    <div style={{
      position: "absolute", top: 0, left: 0, width: outerW, height: outerH, borderRadius: radius + bezel,
      background: "linear-gradient(165deg,#3A3A3E 0%,#111114 42%,#1C1C20 100%)",
      padding: bezel, boxShadow: glow, transform: `scale(${scale})`, transformOrigin: "top left",
    }}>
      <div style={{ position: "absolute", left: -2, top: 168, width: 3, height: 32, background: "#2A2A2E", borderRadius: 1 }} />
      <div style={{ position: "absolute", left: -2, top: 214, width: 3, height: 62, background: "#2A2A2E", borderRadius: 1 }} />
      <div style={{ position: "absolute", left: -2, top: 284, width: 3, height: 62, background: "#2A2A2E", borderRadius: 1 }} />
      <div style={{ position: "absolute", right: -2, top: 236, width: 3, height: 90, background: "#2A2A2E", borderRadius: 1 }} />
      <div style={{
        width: W, height: H, borderRadius: radius - 4, overflow: "hidden", position: "relative",
        background: appearance === "dark" ? "#000" : "#F2F4F8",
      }}>
        <div style={{
          position: "absolute", top: 0, left: 0, width: SCREEN.width, height: SCREEN.height,
          transform: `scale(${innerScale})`, transformOrigin: "top left",
        }}>{children}</div>
        <div style={{
          position: "absolute", top: 11, left: "50%", transform: "translateX(-50%)",
          width: IPHONE.island.width, height: IPHONE.island.height, borderRadius: 20, background: "#000", zIndex: 7,
        }} />
        <StatusBar appearance={appearance} />
        <div style={{
          position: "absolute", bottom: 8, left: "50%", transform: "translateX(-50%)",
          width: 134, height: 5, borderRadius: 3, background: appearance === "dark" ? "rgba(255,255,255,0.38)" : "rgba(0,0,0,0.32)", zIndex: 7,
        }} />
      </div>
    </div>
  </div>;
}
