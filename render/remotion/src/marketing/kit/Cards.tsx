import React from "react";

/** ISO/IEC 7810 ID-1. Both PAN and payment cards are this size in the real world. */
const RATIO = "1.5858 / 1";
const RADIUS = 18;

function settle(enter: number): React.CSSProperties {
  const t = Math.min(1, Math.max(0, enter));
  return {
    opacity: t,
    transform: t >= 1 ? "translateZ(0)" : `translateY(${(1 - t) * 12}px) translateZ(0)`,
    backfaceVisibility: "hidden",
    WebkitBackfaceVisibility: "hidden",
  };
}

function Face({ children, enter = 1, tone }: { children: React.ReactNode; enter?: number; tone: "id" | "pay" }) {
  return <div style={{ width: "100%", ...settle(enter) }}>
    <div style={{
      width: "100%", aspectRatio: RATIO, borderRadius: RADIUS, overflow: "hidden", position: "relative",
      boxShadow: tone === "pay"
        ? "0 18px 40px rgba(8,16,40,0.45), 0 2px 0 rgba(255,255,255,0.08) inset"
        : "0 16px 36px rgba(10,46,122,0.18), 0 1px 0 rgba(255,255,255,0.85) inset",
    }}>{children}</div>
  </div>;
}

function Chip() {
  const pad = (x: number, y: number) => <rect key={`${x}-${y}`} x={x} y={y} width="7" height="6" rx="1" fill="#C7922C" />;
  return <svg width="54" height="42" viewBox="0 0 54 42">
    <rect width="54" height="42" rx="6" fill="#E0B24A"/>
    <rect x="1.5" y="1.5" width="51" height="39" rx="5" fill="none" stroke="#F4D27A" strokeWidth="1.4"/>
    <rect x="18" y="0" width="18" height="42" fill="#D7A43A" opacity=".55"/>
    {[6, 16, 26, 36].flatMap((y) => [6, 22, 38].map((x) => pad(x, y)))}
  </svg>;
}

function Contactless({ color = "#D7E4FF" }: { color?: string }) {
  return <svg width="28" height="32" viewBox="0 0 28 32">
    <path d="M6 11c3.2 2.4 3.2 7.6 0 10" fill="none" stroke={color} strokeWidth="2.2" strokeLinecap="round"/>
    <path d="M12 7.5c5.2 4 5.2 13 0 17" fill="none" stroke={color} strokeWidth="2.2" strokeLinecap="round"/>
    <path d="M18 4.5c7 5.4 7 17.6 0 23" fill="none" stroke={color} strokeWidth="2.2" strokeLinecap="round"/>
  </svg>;
}

function PersonSilhouette() {
  return <svg viewBox="0 0 80 96" width="100%" height="100%">
    <rect width="80" height="96" fill="#9BB4D4"/>
    <circle cx="40" cy="34" r="16" fill="#D7E4F5"/>
    <path d="M14 96 v-12 a26 22 0 0 1 52 0 V96" fill="#D7E4F5"/>
  </svg>;
}

/** Indian PAN card, ID-1, sitting on the desk. No 3D hinge. */
export function IdentityCard({ label, value, enter = 1 }: { label: string; value: string; enter?: number }) {
  return <Face enter={enter} tone="id">
    <div style={{
      position: "absolute", inset: 0,
      background: "linear-gradient(180deg,#F7FBFF 0%,#E7F0FA 55%,#D7E6F4 100%)",
      color: "#0A2E7A", fontFamily: "'Helvetica Neue', Helvetica, Arial, sans-serif",
    }}>
      <div style={{
        height: "23%", background: "linear-gradient(90deg,#0A2E7A,#1552B8)",
        display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 5.5%",
        color: "white",
      }}>
        <div>
          <div style={{ fontSize: 11, letterSpacing: 1.6, opacity: 0.8 }}>GOVT. OF INDIA</div>
          <div style={{ fontSize: 15, fontWeight: 700, letterSpacing: 0.4, marginTop: 2 }}>INCOME TAX DEPARTMENT</div>
        </div>
        <div style={{
          width: 36, height: 36, borderRadius: 18, border: "1.5px solid rgba(255,255,255,0.7)",
          display: "grid", placeItems: "center", fontSize: 9, letterSpacing: 1, fontWeight: 700,
        }}>IND</div>
      </div>
      <div style={{ display: "flex", gap: "4.5%", padding: "4.5% 5.5% 0", height: "52%", boxSizing: "border-box" }}>
        <div style={{
          width: "22%", borderRadius: 6, overflow: "hidden", background: "#C5D6EA",
          boxShadow: "inset 0 0 0 1px #9BB4D4",
        }}><PersonSilhouette/></div>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "space-between", padding: "2px 0 6px" }}>
          <Field k="Name" v="RAHUL SHARMA"/>
          <Field k="Father's Name" v="AMIT SHARMA"/>
          <Field k="Date of Birth" v="14/03/1992"/>
        </div>
        <div style={{
          width: 44, height: 44, borderRadius: 22, marginTop: 4, flexShrink: 0,
          background: "conic-gradient(from 40deg,#E8F0FF,#9BB6DC,#F7FBFF,#7EA2D4,#E8F0FF)",
          boxShadow: "inset 0 0 0 2px rgba(255,255,255,0.7)",
        }}/>
      </div>
      <div style={{
        position: "absolute", left: "5.5%", right: "5.5%", bottom: "9%",
        background: "#FFF8E8", border: "1px solid #E6D7A8", borderRadius: 6,
        padding: "7px 12px 6px", display: "flex", justifyContent: "space-between", alignItems: "baseline",
      }}>
        <div>
          <div style={{ fontSize: 9, letterSpacing: 1.6, color: "#8A7A42" }}>PERMANENT ACCOUNT NUMBER</div>
          <div style={{ fontSize: 22, fontWeight: 750, letterSpacing: 2.2, color: "#0A2E7A", fontVariantNumeric: "tabular-nums" }}>{value}</div>
        </div>
        <div style={{ fontSize: 9, letterSpacing: 1.2, color: "#9AA7BC" }}>{label.includes("PAN") ? "PAN CARD" : label}</div>
      </div>
      <div style={{ position: "absolute", left: "5.5%", bottom: "3%", fontSize: 8, letterSpacing: 1.1, color: "#93A2B8" }}>ILLUSTRATIVE DEMO · NOT A GOVERNMENT DOCUMENT</div>
    </div>
  </Face>;
}

function Field({ k, v }: { k: string; v: string }) {
  return <div>
    <div style={{ fontSize: 9, letterSpacing: 1.3, color: "#7A8AA3" }}>{k}</div>
    <div style={{ fontSize: 14, fontWeight: 650, letterSpacing: 0.2, color: "#0A2E7A", marginTop: 1 }}>{v}</div>
  </div>;
}

/** Plastic payment card, ID-1, flat on the desk. Chip is HTML/SVG, never a 3D rotate. */
export function PaymentCard({ label, value, enter = 1 }: { label: string; value: string; enter?: number }) {
  return <Face enter={enter} tone="pay">
    <div style={{
      position: "absolute", inset: 0, color: "white",
      background: "linear-gradient(148deg,#2A4A86 0%,#13244A 42%,#0B1224 100%)",
      fontFamily: "'Helvetica Neue', Helvetica, Arial, sans-serif",
    }}>
      <div style={{
        position: "absolute", inset: 0, opacity: 0.18, pointerEvents: "none",
        background: "repeating-linear-gradient(115deg, transparent 0 18px, rgba(255,255,255,0.07) 18px 19px)",
      }}/>
      <div style={{
        position: "absolute", inset: 0, pointerEvents: "none",
        background: "linear-gradient(118deg, rgba(255,255,255,0.16) 0%, transparent 36%, transparent 62%, rgba(255,255,255,0.05) 100%)",
      }}/>
      <div style={{ position: "absolute", top: "10%", left: "6.5%", right: "6.5%", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ fontSize: 11, letterSpacing: 2.4, fontWeight: 650, color: "#D7E4FF" }}>PLATINUM</div>
        <div style={{ fontSize: 10, letterSpacing: 1.8, color: "#9BB4D4" }}>{label.includes("CARD") ? "CREDIT" : label}</div>
      </div>
      <div style={{ position: "absolute", top: "32%", left: "6.5%", display: "flex", alignItems: "center", gap: 14 }}>
        <Chip/>
        <Contactless/>
      </div>
      <div style={{
        position: "absolute", left: "6.5%", right: "6.5%", top: "58%",
        fontSize: 20, fontWeight: 650, letterSpacing: 3.2, fontVariantNumeric: "tabular-nums",
        textShadow: "0 1px 0 rgba(0,0,0,0.35)",
      }}>{value}</div>
      <div style={{ position: "absolute", left: "6.5%", right: "6.5%", bottom: "10%", display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
        <div>
          <div style={{ fontSize: 8, letterSpacing: 1.6, color: "#9BB4D4" }}>CARDHOLDER</div>
          <div style={{ fontSize: 13, fontWeight: 650, letterSpacing: 1.4, marginTop: 3 }}>RAHUL SHARMA</div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: 8, letterSpacing: 1.6, color: "#9BB4D4" }}>VALID THRU</div>
          <div style={{ fontSize: 13, fontWeight: 650, letterSpacing: 1.4, marginTop: 3 }}>12/28</div>
        </div>
      </div>
    </div>
  </Face>;
}
