export type CommsFormat = "release_notes" | "whatsapp" | "newsletter";

export type DocBlock = {
  id: string;
  type: "title" | "heading" | "subheading" | "paragraph" | "bullet";
  text: string;
};

export type CommsDraft = {
  title: string;
  kind: CommsFormat;
  blocks: DocBlock[];
};

export const FORMATS: { id: CommsFormat; label: string; hint: string }[] = [
  { id: "release_notes", label: "Release notes", hint: "Clients" },
  { id: "whatsapp", label: "WhatsApp", hint: "Internal" },
  { id: "newsletter", label: "Newsletter", hint: "Customers" },
];

export function newBlock(type: DocBlock["type"] = "paragraph", text = ""): DocBlock {
  return { id: `b${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`, type, text };
}

export function emptyDraft(kind: CommsFormat = "release_notes"): CommsDraft {
  return { title: "", kind, blocks: [newBlock("paragraph")] };
}

export function packBody(pack: {
  kind?: string;
  whatsapp?: string;
  internal_update?: string;
  release_notes?: string;
  newsletter_markdown?: string;
}): string {
  const kind = pack.kind === "whatsapp" || pack.kind === "newsletter" ? pack.kind : "release_notes";
  if (kind === "whatsapp") return pack.whatsapp || pack.internal_update || "";
  if (kind === "newsletter") return pack.newsletter_markdown || "";
  return pack.release_notes || "";
}

export function blocksFromMarkdown(markdown: string): DocBlock[] {
  const blocks: DocBlock[] = [];
  const chunks = (markdown || "").replace(/\r\n/g, "\n").split(/\n{2,}/);
  for (const chunk of chunks) {
    let para: DocBlock | null = null;
    for (const line of chunk.split("\n")) {
      const trimmed = line.replace(/\s+$/, "");
      if (!trimmed) continue;
      const heading = trimmed.match(/^(#{1,6})\s+(.*)$/);
      if (heading) {
        para = null;
        const hashes = heading[1].length;
        const type: DocBlock["type"] = hashes === 1 ? "title" : hashes >= 3 ? "subheading" : "heading";
        blocks.push(newBlock(type, heading[2]));
        continue;
      }
      const bullet = trimmed.match(/^[-*•]\s+(.*)$/) || trimmed.match(/^\d+\.\s+(.*)$/);
      if (bullet) {
        para = null;
        blocks.push(newBlock("bullet", bullet[1]));
        continue;
      }
      if (para) {
        para.text = `${para.text}\n${trimmed}`;
      } else {
        para = newBlock("paragraph", trimmed);
        blocks.push(para);
      }
    }
  }
  return blocks.length ? blocks : [newBlock("paragraph")];
}

export function markdownFromBlocks(blocks: DocBlock[]): string {
  const parts: string[] = [];
  let bullets: string[] = [];
  function flushBullets() {
    if (bullets.length) {
      parts.push(bullets.join("\n"));
      bullets = [];
    }
  }
  for (const block of blocks) {
    const text = (block.text || "").trim();
    if (block.type === "bullet") {
      if (text) bullets.push(`- ${text}`);
      continue;
    }
    flushBullets();
    if (!text) continue;
    if (block.type === "title") parts.push(`# ${text}`);
    else if (block.type === "heading") parts.push(`## ${text}`);
    else if (block.type === "subheading") parts.push(`### ${text}`);
    else parts.push(text);
  }
  flushBullets();
  return parts.join("\n\n").trim();
}

export function draftFromPack(pack: {
  title?: string;
  kind?: string;
  whatsapp?: string;
  internal_update?: string;
  release_notes?: string;
  newsletter_markdown?: string;
}): CommsDraft {
  const kind: CommsFormat = pack.kind === "whatsapp" || pack.kind === "newsletter" ? pack.kind : "release_notes";
  return {
    title: pack.title || "",
    kind,
    blocks: blocksFromMarkdown(packBody(pack)),
  };
}

export function previewText(pack: Parameters<typeof packBody>[0] & { preview?: string }) {
  return (pack.preview || packBody(pack)).replace(/\s+/g, " ").trim();
}

export function formatLabel(kind: string) {
  return FORMATS.find((row) => row.id === kind)?.label || "Draft";
}
