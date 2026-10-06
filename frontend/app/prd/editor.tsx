"use client";

import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Box, TextField, Typography } from "@mui/material";
import { DocField, FormatToolbar, applyInlineFormat, currentDocLine, setDocLineKind, type HeadingKind } from "@/app/editor/format";
import { htmlToDocumentMarkdown, type DocLineKind } from "@/app/editor/markdown";
import { api, type Prd } from "@/lib/api";
import { Banner, FrostCard, MarkdownBlock, PillButton } from "@/app/ui";
import { apple } from "@/app/ui/tokens";

function lineKindFromEl(el: HTMLElement | null): HeadingKind | "check" {
  const kind = el?.getAttribute("data-line") || "paragraph";
  if (kind === "title" || kind === "heading" || kind === "subheading" || kind === "paragraph" || kind === "bullet") return kind;
  if (kind === "check") return "check";
  return "paragraph";
}

export function PrdEditor({ document, onSave, onDirty, onPdf, onError, onBusy, generating }: { document: Prd | null; onSave: (row: Prd) => void; onDirty: (dirty: boolean) => void; onPdf: (url: string) => void; onError: (message: string) => void; onBusy: (busy: boolean) => void; generating: boolean }) {
  const [title, setTitle] = useState(document?.title || "");
  const [body, setBody] = useState(document?.markdown || "");
  const [preview, setPreview] = useState(false);
  const [saving, setBusy] = useState(false);
  const busy = saving || generating;
  const [error, setError] = useState("");
  const [activeKind, setActiveKind] = useState<HeadingKind | "check">("paragraph");
  const input = useRef<HTMLElement | null>(null);
  const dirty = title !== (document?.title || "") || body !== (document?.markdown || "");
  useEffect(() => { onDirty(dirty); }, [dirty, onDirty]);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { if (dirty) { event.preventDefault(); event.returnValue = ""; } };
    const leave = (event: MouseEvent) => {
      const link = (event.target as Element)?.closest?.("a[href]") as HTMLAnchorElement | null;
      if (!dirty || !link || link.target === "_blank" || event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0 || link.href === window.location.href) return;
      if (!window.confirm("Leave this document and discard unsaved changes?")) {
        event.preventDefault(); event.stopPropagation();
      }
    };
    window.document.addEventListener("click", leave, true);
    window.addEventListener("beforeunload", warn);
    return () => { window.removeEventListener("beforeunload", warn); window.document.removeEventListener("click", leave, true); };
  }, [dirty]);

  function rememberLine() {
    setActiveKind(lineKindFromEl(currentDocLine(input.current)));
  }

  async function persist() {
    const payload = { title: title.trim() || "Untitled", markdown: body };
    const row = document ? await api.savePrd(document.id, payload) : await api.createPrd(payload);
    setTitle(row.title);
    onSave(row);
    return row;
  }

  async function save(pdf = false) {
    setBusy(true); onBusy(true); setError(""); onError(""); onPdf("");
    try {
      const row = await persist();
      if (pdf) {
        try {
          const file = await api.savePrdPdf(row.id);
          onPdf(file.url);
        } catch (e) { onError(`Draft saved, but PDF could not be saved to LMS: ${String(e)}`); }
      }
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); onBusy(false); }
  }

  async function exportPdf() {
    setBusy(true); onBusy(true); setError(""); onError("");
    try {
      const row = dirty || !document ? await persist() : document;
      window.open(api.prdPdfUrl(row.id), "_blank", "noopener,noreferrer");
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); onBusy(false); }
  }

  function applyLine(type: HeadingKind | "check") {
    const el = input.current;
    if (!el) return;
    setDocLineKind(el, type as DocLineKind);
    setBody(htmlToDocumentMarkdown(el));
    setActiveKind(type);
  }

  function applyInline(kind: "bold" | "italic") {
    applyInlineFormat(kind, input.current);
    if (input.current) setBody(htmlToDocumentMarkdown(input.current));
  }

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if ((event.metaKey || event.ctrlKey) && (event.key.toLowerCase() === "z" || event.key.toLowerCase() === "y" || event.code === "KeyZ" || event.code === "KeyY")) return;
    const shortcut = event.metaKey || event.ctrlKey ? event.key.toLowerCase() : "";
    if (shortcut === "b") {
      event.preventDefault();
      applyInline("bold");
    } else if (shortcut === "i") {
      event.preventDefault();
      applyInline("italic");
    }
  }

  return <FrostCard sx={{ p: 0, overflow: "hidden" }}>
    <Box sx={{ px: 2, py: 1.5, borderBottom: 1, borderColor: "divider", display: "flex", alignItems: "center", gap: 1, flexWrap: "wrap" }}>
      <Typography role="status" variant="caption" color="text.secondary" sx={{ flex: 1 }}>{busy ? "Saving…" : dirty ? "Unsaved changes" : document ? "Saved" : "New document"}</Typography>
      <PillButton variant="text" onClick={() => setPreview(!preview)}>{preview ? "Edit" : "Preview"}</PillButton>
      <PillButton variant="gray" disabled={busy || !title.trim()} onClick={() => void exportPdf()}>Export PDF</PillButton>
      <PillButton variant="gray" disabled={busy || !title.trim()} onClick={() => save(true)}>Save PDF to LMS</PillButton>
      <PillButton disabled={busy || !dirty || !title.trim()} onClick={() => save()}>Save draft</PillButton>
    </Box>
    {error && <Banner severity="error">{error}</Banner>}

    <Box sx={{ maxWidth: 820, mx: "auto", p: { xs: 2, md: 5 }, minHeight: 600 }}>
      <TextField fullWidth variant="standard" label="Document title" value={title} disabled={busy} onChange={e => setTitle(e.target.value)} slotProps={{ input: { disableUnderline: true, sx: { fontSize: 28, fontWeight: 600 } } }} />
      {preview ? <Box sx={{ mt: 3 }}><MarkdownBlock>{body || "Start writing your requirements."}</MarkdownBlock></Box> : <>
        <Box sx={{ my: 2, pb: 1, borderBottom: `1px solid ${apple.hairline}` }}>
          <FormatToolbar
            disabled={busy}
            blockType={activeKind === "check" ? "bullet" : activeKind}
            onBlockType={applyLine}
            onInline={applyInline}
            extra={
              <PillButton
                variant="text"
                disabled={busy}
                aria-pressed={activeKind === "check"}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => applyLine("check")}
                sx={{ py: 0.4, px: 1.1, minWidth: 0, fontSize: 12, bgcolor: activeKind === "check" ? apple.selFill : "transparent" }}
              >
                Checklist
              </PillButton>
            }
          />
        </Box>
        <DocField
          value={body}
          disabled={busy}
          placeholder="Describe the problem, goals, requirements, and acceptance criteria…"
          inputRef={(el) => { input.current = el; }}
          onChange={setBody}
          onSelect={rememberLine}
          onKeyDown={onKeyDown}
        />
      </>}
    </Box>
  </FrostCard>;
}
