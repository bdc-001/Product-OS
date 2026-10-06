import type { ReactNode } from "react";

export default function PrototypeEmbedLayout({ children }: { children: ReactNode }) {
  return <div style={{ height: "100vh", overflow: "hidden" }}>{children}</div>;
}
