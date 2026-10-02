export type DocLineKind = "title" | "heading" | "subheading" | "paragraph" | "bullet" | "check";

export function inlineMarkdownToHtml(text: string): string {
  if (!text) return "";
  const escaped = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return escaped
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>")
    .replace(/\n/g, "<br>");
}

export function htmlStringToMarkdown(html: string): string {
  let s = html || "";
  s = s.replace(/&nbsp;/gi, " ");
  s = s.replace(/<br\s*\/?>/gi, "\n");
  s = s.replace(/<\/(div|p)>/gi, "\n");
  s = s.replace(/<(div|p)[^>]*>/gi, "");
  for (let i = 0; i < 6; i += 1) {
    const next = s
      .replace(/<(strong|b)>([\s\S]*?)<\/\1>/gi, (_m, _tag, inner: string) => `**${inner}**`)
      .replace(/<(em|i)>([\s\S]*?)<\/\1>/gi, (_m, _tag, inner: string) => `*${inner}*`)
      .replace(/<span[^>]*font-weight:\s*(bold|[6-9]00)[^>]*>([\s\S]*?)<\/span>/gi, "**$2**")
      .replace(/<span[^>]*font-style:\s*italic[^>]*>([\s\S]*?)<\/span>/gi, "*$2*");
    if (next === s) break;
    s = next;
  }
  s = s.replace(/<[^>]+>/g, "");
  s = s.replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"');
  return s.replace(/\n+$/g, "").replace(/^\n+/g, "");
}

export function htmlToInlineMarkdown(source: string | HTMLElement | DocumentFragment): string {
  if (typeof source === "string") return htmlStringToMarkdown(source);
  if (typeof HTMLElement !== "undefined" && source instanceof HTMLElement) return htmlStringToMarkdown(source.innerHTML);
  if (typeof document !== "undefined") {
    const wrap = document.createElement("div");
    wrap.appendChild(source.cloneNode(true));
    return htmlStringToMarkdown(wrap.innerHTML);
  }
  return "";
}

function lineKind(line: string): { kind: DocLineKind; text: string } {
  if (line.startsWith("### ")) return { kind: "subheading", text: line.slice(4) };
  if (line.startsWith("## ")) return { kind: "heading", text: line.slice(3) };
  if (line.startsWith("# ")) return { kind: "title", text: line.slice(2) };
  const check = line.match(/^-\s+\[(?: |x|X)\]\s+(.*)$/);
  if (check) return { kind: "check", text: check[1] };
  const bullet = line.match(/^[-*•]\s+(.*)$/);
  if (bullet) return { kind: "bullet", text: bullet[1] };
  return { kind: "paragraph", text: line };
}

export function documentMarkdownToHtml(md: string): string {
  const lines = (md || "").replace(/\r\n/g, "\n").split("\n");
  if (!lines.length) return `<div data-line="paragraph"><br></div>`;
  return lines
    .map((line) => {
      const { kind, text } = lineKind(line);
      const inner = inlineMarkdownToHtml(text) || "<br>";
      return `<div data-line="${kind}">${inner}</div>`;
    })
    .join("");
}

export function prefixForLine(kind: DocLineKind, text: string): string {
  if (kind === "title") return `# ${text}`;
  if (kind === "heading") return `## ${text}`;
  if (kind === "subheading") return `### ${text}`;
  if (kind === "bullet") return text ? `- ${text}` : "- ";
  if (kind === "check") return `- [ ] ${text}`;
  return text;
}

export function htmlToDocumentMarkdown(root: HTMLElement): string {
  const children = Array.from(root.children);
  if (!children.length) return htmlToInlineMarkdown(root);
  return children
    .map((child) => {
      const kind = ((child.getAttribute("data-line") || "paragraph") as DocLineKind);
      const text = htmlToInlineMarkdown(child as HTMLElement);
      return prefixForLine(kind, text);
    })
    .join("\n");
}
