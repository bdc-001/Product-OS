"use client";

import { useParams } from "next/navigation";
import { api } from "@/lib/api";

export default function PrototypeEmbedPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  if (!id) return null;
  return (
    <iframe
      title="Sense preview"
      src={api.prototypePreviewUrl(id)}
      style={{ width: "100%", height: "100vh", border: 0, display: "block", background: "#fff" }}
    />
  );
}
