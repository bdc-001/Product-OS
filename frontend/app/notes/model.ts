import type { NoteBlock } from "@/lib/api";

export type NoteKind = "daily" | "meeting" | "decision" | "learning";

export type NoteDraft = {
  day: string;
  title: string;
  body: string;
  learning: string;
  kind: NoteKind;
  blocks: NoteBlock[];
  tags: string[];
};

export const NOTE_KINDS: { id: NoteKind | "all" | "actionable"; label: string }[] = [
  { id: "all", label: "All" },
  { id: "meeting", label: "Meetings" },
  { id: "actionable", label: "Actionables" },
  { id: "decision", label: "Decisions" },
  { id: "learning", label: "Learning" },
  { id: "daily", label: "Daily" },
];

export const KIND_LABEL: Record<NoteKind, string> = {
  daily: "Daily",
  meeting: "Meeting",
  decision: "Decision",
  learning: "Learning",
};

export function todayIst() {
  return new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Kolkata" }).format(new Date());
}

export function newBlock(type: NoteBlock["type"] = "paragraph", text = ""): NoteBlock {
  return { id: `b${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`, type, text };
}

export function emptyDraft(kind: NoteKind = "daily"): NoteDraft {
  return {
    day: todayIst(),
    title: "",
    body: "",
    learning: "",
    kind,
    blocks: [newBlock("paragraph")],
    tags: [],
  };
}

export function draftFromNote(row: {
  day: string;
  title: string;
  body: string;
  learning: string;
  kind?: string;
  blocks?: NoteBlock[];
  tags?: string[];
}): NoteDraft {
  const kind = row.kind === "meeting" || row.kind === "decision" || row.kind === "learning" ? row.kind : "daily";
  const blocks = (row.blocks || []).length
    ? row.blocks!.map((item) => ({
        id: item.id || newBlock().id,
        type: item.type || "paragraph",
        text: item.text || "",
        done: Boolean(item.done),
        ticket_key: item.ticket_key || "",
      }))
    : [
        ...(row.body ? [newBlock("paragraph", row.body)] : []),
        ...(row.learning ? [newBlock("learning", row.learning)] : []),
      ];
  return {
    day: row.day,
    title: row.title,
    body: row.body,
    learning: row.learning,
    kind,
    blocks: blocks.length ? blocks : [newBlock("paragraph")],
    tags: row.tags || [],
  };
}

export function previewText(row: { body?: string; learning?: string; blocks?: NoteBlock[] }) {
  const fromBlocks = (row.blocks || [])
    .map((item) => item.text)
    .filter(Boolean)
    .join(" · ");
  return (fromBlocks || row.body || row.learning || "").replace(/\s+/g, " ").trim();
}
