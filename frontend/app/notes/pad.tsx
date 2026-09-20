"use client";

import AddRoundedIcon from "@mui/icons-material/AddRounded";
import Box from "@mui/material/Box";
import Checkbox from "@mui/material/Checkbox";
import Typography from "@mui/material/Typography";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { PillButton, StatusChip, TicketLink } from "@/app/ui";
import { apple, radius } from "@/app/ui/tokens";
import type { NoteBlock } from "@/lib/api";
import { type NoteDraft, newBlock } from "./model";

const INSERTS: { id: NoteBlock["type"]; slash: string; label: string; hint: string }[] = [
  { id: "heading", slash: "heading", label: "Heading", hint: "Section title" },
  { id: "actionable", slash: "todo", label: "Actionable", hint: "Follow-up you can file in Jira" },
  { id: "decision", slash: "decision", label: "Decision", hint: "What you locked" },
  { id: "learning", slash: "learn", label: "Learning", hint: "What you take away" },
  { id: "paragraph", slash: "text", label: "Text", hint: "Body copy" },
];

function AutoArea({
  value,
  onChange,
  onKeyDown,
  placeholder,
  disabled,
  inputRef,
  sx,
}: {
  value: string;
  onChange: (value: string) => void;
  onKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void;
  placeholder: string;
  disabled?: boolean;
  inputRef?: (el: HTMLTextAreaElement | null) => void;
  sx?: object;
}) {
  const inner = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const el = inner.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = `${Math.max(el.scrollHeight, 28)}px`;
  }, [value]);
  return (
    <Box
      component="textarea"
      ref={(el: HTMLTextAreaElement | null) => {
        inner.current = el;
        inputRef?.(el);
      }}
      value={value}
      disabled={disabled}
      placeholder={placeholder}
      rows={1}
      onChange={(event) => onChange(event.target.value)}
      onKeyDown={onKeyDown}
      sx={{
        display: "block",
        width: "100%",
        border: 0,
        resize: "none",
        outline: "none",
        bgcolor: "transparent",
        font: "inherit",
        color: apple.text,
        p: 0,
        lineHeight: 1.5,
        "&::placeholder": { color: apple.muted },
        ...sx,
      }}
    />
  );
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
  const focusId = useRef<string>("");
  const refs = useRef<Record<string, HTMLTextAreaElement | null>>({});

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
    setSlash(null);
    setBlocks(blocks);
  }

  function applyType(index: number, type: NoteBlock["type"]) {
    const current = draft.blocks[index];
    if (!current) return;
    const text = current.text.replace(/^\/[a-z]*$/i, "").trim();
    patchBlock(index, { type, text });
    setSlash(null);
    focusId.current = current.id;
  }

  function onBlockKey(index: number, event: KeyboardEvent<HTMLTextAreaElement>) {
    const block = draft.blocks[index];
    if (!block) return;
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
      const el = event.currentTarget;
      const start = el.selectionStart ?? block.text.length;
      const end = el.selectionEnd ?? start;
      const before = block.text.slice(0, start);
      const after = block.text.slice(end);
      const next = newBlock("paragraph", after);
      const blocks = draft.blocks.map((item, i) => (i === index ? { ...item, text: before } : item));
      blocks.splice(index + 1, 0, next);
      focusId.current = next.id;
      setSlash(null);
      setBlocks(blocks);
      return;
    }
    if (event.key === "Backspace" && !block.text && draft.blocks.length > 1) {
      event.preventDefault();
      const prev = draft.blocks[index - 1];
      focusId.current = prev?.id || draft.blocks[index + 1]?.id || "";
      setSlash(null);
      setBlocks(draft.blocks.filter((_, i) => i !== index));
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

  return (
    <Box>
      <AutoArea
        value={draft.title}
        disabled={busy}
        placeholder="Untitled"
        onChange={(value) => onChange({ title: value })}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            refs.current[draft.blocks[0]?.id || ""]?.focus();
          }
        }}
        sx={{ fontSize: 28, fontWeight: 650, letterSpacing: "-0.035em", lineHeight: 1.2, mb: 0.75 }}
      />
      <Typography sx={{ fontSize: 12, color: apple.muted, mb: 2 }}>
        Type <Box component="kbd" sx={{ font: "inherit" }}>/</Box> for heading, actionable, decision, or learning.
      </Typography>
      <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
        {draft.blocks.map((block, index) => {
          const card = block.type === "actionable" || block.type === "decision" || block.type === "learning";
          return (
            <Box
              key={block.id}
              sx={{
                position: "relative",
                display: "grid",
                gridTemplateColumns: "28px minmax(0,1fr)",
                gap: 1,
                alignItems: "flex-start",
                "&:hover .note-gutter": { opacity: 1 },
              }}
            >
              <Box className="note-gutter" sx={{ opacity: 0, pt: card ? 1.25 : block.type === "heading" ? 0.5 : 0.25, transition: "opacity 0.2s" }}>
                <Box
                  component="button"
                  type="button"
                  disabled={busy}
                  aria-label="Add block"
                  onClick={() => insertAt(index + 1, "paragraph")}
                  sx={{
                    width: 24,
                    height: 24,
                    border: `1px solid ${apple.hairline}`,
                    borderRadius: "7px",
                    bgcolor: apple.page,
                    color: apple.muted,
                    cursor: "pointer",
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    "&:hover": { bgcolor: apple.hoverFill, color: apple.text },
                  }}
                >
                  <AddRoundedIcon sx={{ fontSize: 16 }} />
                </Box>
              </Box>
              <Box
                sx={
                  card
                    ? {
                        minWidth: 0,
                        border: `1px solid ${apple.hairline}`,
                        borderRadius: `${radius.lg}px`,
                        bgcolor: apple.page,
                        overflow: "visible",
                      }
                    : { minWidth: 0, py: 0.25 }
                }
              >
                {card ? (
                  <Box sx={{ px: 1.5, pt: 1.25, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 1 }}>
                    <StatusChip
                      label={block.type === "actionable" ? "Actionable" : block.type === "decision" ? "Decision" : "Learning"}
                      tone={block.type === "actionable" ? "ink" : "default"}
                    />
                    {block.type === "actionable" && block.ticket_key ? <TicketLink issueKey={block.ticket_key} /> : null}
                  </Box>
                ) : null}
                <Box sx={{ display: "flex", gap: 1, alignItems: "flex-start", px: card ? 1.5 : 0, py: card ? 1 : 0 }}>
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
                  <AutoArea
                    value={block.text}
                    disabled={busy}
                    inputRef={(el) => {
                      refs.current[block.id] = el;
                    }}
                    placeholder={
                      block.type === "heading"
                        ? "Heading"
                        : block.type === "actionable"
                          ? "Follow-up to file in Jira"
                          : block.type === "decision"
                            ? "What was decided?"
                            : block.type === "learning"
                              ? "What you learned"
                              : "Write, or type /"
                    }
                    onChange={(value) => onBlockChange(index, value)}
                    onKeyDown={(event) => onBlockKey(index, event)}
                    sx={{
                      fontSize: block.type === "heading" ? 22 : 16,
                      fontWeight: block.type === "heading" ? 650 : 400,
                      letterSpacing: block.type === "heading" ? "-0.022em" : 0,
                      textDecoration: block.type === "actionable" && block.done ? "line-through" : "none",
                      color: block.type === "actionable" && block.done ? apple.muted : apple.text,
                    }}
                  />
                </Box>
                {block.type === "actionable" ? (
                  <Box
                    sx={{
                      px: 1.5,
                      py: 1,
                      borderTop: `1px solid ${apple.hairline}`,
                      display: "flex",
                      justifyContent: "flex-end",
                      bgcolor: apple.hoverFill,
                    }}
                  >
                    {block.ticket_key ? (
                      <Typography sx={{ fontSize: 12, color: apple.muted }}>Filed in Jira</Typography>
                    ) : (
                      <PillButton variant="gray" type="button" disabled={busy || !block.text.trim()} onClick={() => onTicket(block)} sx={{ py: 0.4, px: 1.25, fontSize: 12 }}>
                        Create ticket
                      </PillButton>
                    )}
                  </Box>
                ) : null}
                {slash?.index === index ? slashMenu : null}
              </Box>
            </Box>
          );
        })}
      </Box>
    </Box>
  );
}
