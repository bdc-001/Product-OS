"use client";

import AddRoundedIcon from "@mui/icons-material/AddRounded";
import DeleteOutlineRoundedIcon from "@mui/icons-material/DeleteOutlineRounded";
import Box from "@mui/material/Box";
import Checkbox from "@mui/material/Checkbox";
import Typography from "@mui/material/Typography";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { AutoArea, FormatToolbar, RichField, applyInlineFormat, blockFace, blockGutterSx, blockListSx, blockRowSx, formatShortcut, gutterBtnSx, splitAtCaret, type HeadingKind } from "@/app/editor/format";
import { htmlToInlineMarkdown } from "@/app/editor/markdown";
import { PillButton, StatusChip, TicketLink } from "@/app/ui";
import { apple, radius } from "@/app/ui/tokens";
import type { NoteBlock } from "@/lib/api";
import { type NoteDraft, newBlock } from "./model";

const INSERTS: { id: NoteBlock["type"]; slash: string; label: string; hint: string }[] = [
  { id: "title", slash: "title", label: "Title", hint: "Largest heading" },
  { id: "heading", slash: "heading", label: "Heading", hint: "Section title" },
  { id: "subheading", slash: "subhead", label: "Subhead", hint: "Smaller heading" },
  { id: "bullet", slash: "list", label: "List", hint: "Bullet point" },
  { id: "actionable", slash: "todo", label: "Actionable", hint: "Follow-up you can file in Jira" },
  { id: "decision", slash: "decision", label: "Decision", hint: "What you locked" },
  { id: "learning", slash: "learn", label: "Learning", hint: "What you take away" },
  { id: "paragraph", slash: "text", label: "Text", hint: "Body copy" },
];

function placeholderFor(type: NoteBlock["type"]) {
  if (type === "title") return "Title";
  if (type === "heading") return "Heading";
  if (type === "subheading") return "Subhead";
  if (type === "bullet") return "List item";
  if (type === "actionable") return "Follow-up to file in Jira";
  if (type === "decision") return "What was decided?";
  if (type === "learning") return "What you learned";
  return "Write, or type /";
}

export function NotePad({
  draft,
  busy,
  onChange,
  onTicket,
}: {
  draft: NoteDraft;
  busy: boolean;
  onChange: (patch: Partial<NoteDraft>) => void;
  onTicket: (block: NoteBlock) => void;
}) {
  const [slash, setSlash] = useState<{ index: number; query: string; active: number } | null>(null);
  const [focusIndex, setFocusIndex] = useState(0);
  const focusId = useRef<string>("");
  const refs = useRef<Record<string, HTMLElement | null>>({});

  useEffect(() => {
    if (!focusId.current) return;
    refs.current[focusId.current]?.focus();
    focusId.current = "";
  }, [draft.blocks]);

  const matches = slash
    ? INSERTS.filter((item) => item.slash.startsWith(slash.query) || item.label.toLowerCase().startsWith(slash.query))
    : [];

  function setBlocks(blocks: NoteBlock[]) {
    onChange({ blocks });
  }

  function patchBlock(index: number, patch: Partial<NoteBlock>) {
    setBlocks(draft.blocks.map((item, i) => (i === index ? { ...item, ...patch } : item)));
  }

  function insertAt(index: number, type: NoteBlock["type"], text = "") {
    const next = newBlock(type, text);
    const blocks = [...draft.blocks];
    blocks.splice(index, 0, next);
    focusId.current = next.id;
    setFocusIndex(index);
    setSlash(null);
    setBlocks(blocks);
  }

  function removeAt(index: number) {
    setSlash(null);
    if (draft.blocks.length <= 1) {
      const next = newBlock("paragraph");
      focusId.current = next.id;
      setFocusIndex(0);
      setBlocks([next]);
      return;
    }
    const prev = draft.blocks[index - 1];
    focusId.current = prev?.id || draft.blocks[index + 1]?.id || "";
    setFocusIndex(Math.max(0, index - 1));
    setBlocks(draft.blocks.filter((_, i) => i !== index));
  }

  function applyType(index: number, type: NoteBlock["type"]) {
    const current = draft.blocks[index];
    if (!current) return;
    const text = current.text.replace(/^\/[a-z]*$/i, "").trim();
    patchBlock(index, { type, text });
    setSlash(null);
    focusId.current = current.id;
  }

  function applyInline(kind: "bold" | "italic") {
    const index = focusIndex;
    const block = draft.blocks[index];
    const el = block ? refs.current[block.id] : null;
    if (!block || !el) return;
    applyInlineFormat(kind, el);
    patchBlock(index, { text: htmlToInlineMarkdown(el) });
  }

  function onBlockKey(index: number, event: KeyboardEvent<HTMLDivElement>) {
    const block = draft.blocks[index];
    if (!block) return;
    if ((event.metaKey || event.ctrlKey) && (event.key.toLowerCase() === "z" || event.key.toLowerCase() === "y" || event.code === "KeyZ" || event.code === "KeyY")) return;
    const shortcut = formatShortcut(event);
    if (shortcut) {
      event.preventDefault();
      applyInline(shortcut);
      return;
    }
    if (slash) {
      if (event.key === "Escape") {
        event.preventDefault();
        setSlash(null);
        return;
      }
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        const n = matches.length || 1;
        const delta = event.key === "ArrowDown" ? 1 : -1;
        setSlash({ ...slash, active: (slash.active + delta + n) % n });
        return;
      }
      if (event.key === "Enter" || event.key === "Tab") {
        event.preventDefault();
        const pick = matches[slash.active] || matches[0];
        if (pick) applyType(index, pick.id);
        return;
      }
    }
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      const split = splitAtCaret(event.currentTarget);
      if (block.type === "bullet" && !split.before.trim() && !split.after.trim()) {
        patchBlock(index, { type: "paragraph", text: "" });
        return;
      }
      const next = newBlock(block.type === "bullet" ? "bullet" : "paragraph", split.after);
      const blocks = draft.blocks.map((item, i) => (i === index ? { ...item, text: split.before } : item));
      blocks.splice(index + 1, 0, next);
      focusId.current = next.id;
      setFocusIndex(index + 1);
      setSlash(null);
      setBlocks(blocks);
      return;
    }
    if (event.key === "Backspace" && !block.text && draft.blocks.length > 1) {
      event.preventDefault();
      removeAt(index);
    }
  }

  function onBlockChange(index: number, text: string) {
    const slashMatch = text.match(/^\/([a-z]*)$/i);
    setSlash(slashMatch ? { index, query: slashMatch[1].toLowerCase(), active: 0 } : null);
    const ticket = text.toUpperCase().match(/\b([A-Z][A-Z0-9]+-\d+)\b/);
    patchBlock(index, { text, ticket_key: ticket?.[1] || draft.blocks[index]?.ticket_key || "" });
  }

  const slashMenu =
    slash && matches.length ? (
      <Box
        role="listbox"
        sx={{
          mt: 1,
          width: 280,
          border: `1px solid ${apple.hairline}`,
          borderRadius: `${radius.lg}px`,
          bgcolor: apple.page,
          boxShadow: apple.shadow,
          overflow: "hidden",
          zIndex: 2,
        }}
      >
        {matches.map((item, i) => (
          <Box
            key={item.id}
            component="button"
            type="button"
            role="option"
            aria-selected={i === slash.active}
            onMouseDown={(event) => {
              event.preventDefault();
              applyType(slash.index, item.id);
            }}
            sx={{
              display: "block",
              width: "100%",
              textAlign: "left",
              border: 0,
              bgcolor: i === slash.active ? apple.hoverFill : "transparent",
              px: 1.5,
              py: 1,
              cursor: "pointer",
              font: "inherit",
            }}
          >
            <Typography sx={{ fontSize: 14, fontWeight: 600 }}>{item.label}</Typography>
            <Typography sx={{ fontSize: 12, color: apple.muted }}>{item.hint}</Typography>
          </Box>
        ))}
      </Box>
    ) : null;

  const focused = draft.blocks[focusIndex];
  const headingKind: HeadingKind | undefined =
    focused?.type === "title" || focused?.type === "heading" || focused?.type === "subheading" || focused?.type === "paragraph" || focused?.type === "bullet"
      ? focused.type
      : undefined;

  return (
    <Box>
      <AutoArea
        value={draft.title}
        disabled={busy}
        placeholder="Untitled"
        onFocus={() => setFocusIndex(-1)}
        onChange={(value) => onChange({ title: value })}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            refs.current[draft.blocks[0]?.id || ""]?.focus();
          }
        }}
        sx={{ fontSize: 28, fontWeight: 650, letterSpacing: "-0.035em", lineHeight: 1.2, mb: 0.75 }}
      />
      <Box
        sx={{
          position: "sticky",
          top: 0,
          zIndex: 3,
          bgcolor: apple.page,
          py: 1,
          mb: 0.5,
          borderBottom: `1px solid ${apple.hairline}`,
        }}
      >
        <FormatToolbar
          disabled={busy}
          blockType={headingKind || focused?.type}
          onBlockType={(type) => {
            if (draft.blocks[focusIndex]) applyType(focusIndex, type);
          }}
          onInline={applyInline}
          extra={
            <>
              {(["actionable", "decision", "learning"] as const).map((type) => (
                <PillButton
                  key={type}
                  variant="text"
                  disabled={busy}
                  aria-pressed={focused?.type === type}
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => {
                    if (draft.blocks[focusIndex]) applyType(focusIndex, type);
                  }}
                  sx={{ py: 0.4, px: 1.1, minWidth: 0, fontSize: 12, bgcolor: focused?.type === type ? apple.selFill : "transparent" }}
                >
                  {type === "actionable" ? "Actionable" : type === "decision" ? "Decision" : "Learning"}
                </PillButton>
              ))}
            </>
          }
        />
      </Box>
      <Typography sx={{ fontSize: 12, color: apple.muted, mb: 2 }}>
        Type <Box component="kbd" sx={{ font: "inherit" }}>/</Box> to insert a block. Select text, then Bold or Italic.
      </Typography>
      <Box sx={blockListSx}>
        {draft.blocks.map((block, index) => (
          <Box
            key={block.id}
            onMouseDown={() => setFocusIndex(index)}
            sx={{
              ...blockRowSx(block.type, index),
              "&:hover .note-gutter": { opacity: 1, pointerEvents: "auto" },
            }}
          >
            <Box className="note-gutter" sx={blockGutterSx}>
              <Box component="button" type="button" disabled={busy} aria-label="Add block" onClick={() => insertAt(index + 1, "paragraph")} sx={gutterBtnSx}>
                <AddRoundedIcon sx={{ fontSize: 16 }} />
              </Box>
              <Box component="button" type="button" disabled={busy} aria-label="Delete block" onClick={() => removeAt(index)} sx={gutterBtnSx}>
                <DeleteOutlineRoundedIcon sx={{ fontSize: 15 }} />
              </Box>
            </Box>
            <Box sx={{ minWidth: 0 }}>
              {block.type === "actionable" || block.type === "decision" || block.type === "learning" ? (
                <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 1, mb: 0.5 }}>
                  <StatusChip
                    label={block.type === "actionable" ? "Actionable" : block.type === "decision" ? "Decision" : "Learning"}
                    tone={block.type === "actionable" ? "ink" : "default"}
                  />
                  {block.type === "actionable" && block.ticket_key ? <TicketLink issueKey={block.ticket_key} /> : null}
                  {block.type === "actionable" && !block.ticket_key ? (
                    <PillButton variant="text" type="button" disabled={busy || !block.text.trim()} onClick={() => onTicket(block)} sx={{ py: 0.25, px: 1, fontSize: 12 }}>
                      Create ticket
                    </PillButton>
                  ) : null}
                </Box>
              ) : null}
              <Box sx={{ display: "flex", gap: 1, alignItems: "flex-start" }}>
                {block.type === "actionable" ? (
                  <Checkbox
                    size="small"
                    disabled={busy}
                    checked={Boolean(block.done)}
                    onChange={() => patchBlock(index, { done: !block.done })}
                    sx={{ mt: "-2px" }}
                    slotProps={{ input: { "aria-label": "Mark actionable done" } }}
                  />
                ) : null}
                {block.type === "bullet" ? (
                  <Typography sx={{ mt: "4px", color: apple.muted, lineHeight: 1, fontSize: 16 }} aria-hidden>
                    •
                  </Typography>
                ) : null}
                <RichField
                  value={block.text}
                  disabled={busy}
                  inputRef={(el) => {
                    refs.current[block.id] = el;
                  }}
                  placeholder={placeholderFor(block.type)}
                  showHint={index === focusIndex}
                  onFocus={() => setFocusIndex(index)}
                  onChange={(value) => onBlockChange(index, value)}
                  onKeyDown={(event) => onBlockKey(index, event)}
                  sx={{
                    ...blockFace(block.type),
                    textDecoration: block.type === "actionable" && block.done ? "line-through" : "none",
                    color: block.type === "actionable" && block.done ? apple.muted : apple.text,
                  }}
                />
              </Box>
              {slash?.index === index ? slashMenu : null}
            </Box>
          </Box>
        ))}
      </Box>
    </Box>
  );
}
