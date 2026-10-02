"use client";

import Box from "@mui/material/Box";
import Menu from "@mui/material/Menu";
import MenuItem from "@mui/material/MenuItem";
import ExpandMoreRoundedIcon from "@mui/icons-material/ExpandMoreRounded";
import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { PillButton } from "@/app/ui";
import { apple } from "@/app/ui/tokens";
import { createValueStack, historyAction } from "./history";
import {
  htmlToDocumentMarkdown,
  htmlToInlineMarkdown,
  inlineMarkdownToHtml,
  documentMarkdownToHtml,
  type DocLineKind,
} from "./markdown";

export type HeadingKind = "title" | "heading" | "subheading" | "paragraph" | "bullet";

function wrapSelection(tag: "strong" | "em") {
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0 || sel.isCollapsed) return;
  const range = sel.getRangeAt(0);
  const wrap = document.createElement(tag);
  try {
    range.surroundContents(wrap);
  } catch {
    wrap.appendChild(range.extractContents());
    range.insertNode(wrap);
  }
  sel.removeAllRanges();
  const next = document.createRange();
  next.selectNodeContents(wrap);
  sel.addRange(next);
}

export function applyInlineFormat(kind: "bold" | "italic", root?: HTMLElement | null) {
  if (root && document.activeElement !== root) root.focus();
  try {
    if (document.execCommand(kind, false)) return;
  } catch {
    /* fallback below */
  }
  wrapSelection(kind === "bold" ? "strong" : "em");
}

export function splitAtCaret(el: HTMLElement): { before: string; after: string } {
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0 || !el.contains(sel.anchorNode)) {
    return { before: htmlToInlineMarkdown(el), after: "" };
  }
  const range = sel.getRangeAt(0);
  const beforeRange = document.createRange();
  beforeRange.selectNodeContents(el);
  beforeRange.setEnd(range.startContainer, range.startOffset);
  const afterRange = document.createRange();
  afterRange.selectNodeContents(el);
  afterRange.setStart(range.endContainer, range.endOffset);
  const beforeWrap = document.createElement("div");
  beforeWrap.appendChild(beforeRange.cloneContents());
  const afterWrap = document.createElement("div");
  afterWrap.appendChild(afterRange.cloneContents());
  return { before: htmlToInlineMarkdown(beforeWrap), after: htmlToInlineMarkdown(afterWrap) };
}

export function blockFace(type: string) {
  if (type === "title") return { fontSize: 26, fontWeight: 650, letterSpacing: "-0.03em", lineHeight: 1.2 };
  if (type === "heading") return { fontSize: 21, fontWeight: 600, letterSpacing: "-0.022em", lineHeight: 1.25 };
  if (type === "subheading") return { fontSize: 17, fontWeight: 600, letterSpacing: "-0.02em", lineHeight: 1.3 };
  return { fontSize: 16, fontWeight: 400, letterSpacing: 0, lineHeight: 1.45 };
}

export function applyHistory(kind: "undo" | "redo") {
  if (kind === "undo" && activeHistory?.undo()) return;
  if (kind === "redo" && activeHistory?.redo()) return;
  document.execCommand(kind, false);
}

type HistoryHandle = {
  snapshot: () => void;
  undo: () => boolean;
  redo: () => boolean;
  reset: (html: string) => void;
  ensure: (html: string) => void;
  isRestoring: () => boolean;
};
let activeHistory: HistoryHandle | null = null;

function createFieldHistory(
  inner: { current: HTMLElement | null },
  read: (el: HTMLElement) => string,
  write: (el: HTMLElement, value: string) => void,
  emit: (value: string) => void,
): HistoryHandle {
  const stack = createValueStack();
  let restoring = false;

  function snapshot() {
    const el = inner.current;
    if (!el || restoring) return;
    stack.push(read(el));
  }

  function restore(value: string | null) {
    const el = inner.current;
    if (!el || value == null) return false;
    restoring = true;
    write(el, value);
    emit(value);
    restoring = false;
    return true;
  }

  return {
    snapshot,
    undo: () => restore(stack.undo()),
    redo: () => restore(stack.redo()),
    reset: (value) => {
      restoring = false;
      stack.reset(value);
    },
    ensure: (value) => {
      if (!stack.has()) stack.reset(value);
    },
    isRestoring: () => restoring,
  };
}

function onHistoryKey(event: { metaKey: boolean; ctrlKey: boolean; altKey: boolean; shiftKey: boolean; key: string; code?: string; preventDefault: () => void }, history: HistoryHandle | null) {
  const action = historyAction(event);
  if (!action) return false;
  const acted = action === "redo" ? Boolean(history?.redo()) : Boolean(history?.undo());
  if (acted) event.preventDefault();
  return acted;
}

export function formatShortcut(event: KeyboardEvent): "bold" | "italic" | "" {
  if (historyAction(event)) return "";
  if (!(event.metaKey || event.ctrlKey) || event.altKey) return "";
  const key = event.key.toLowerCase();
  if (key === "b") return "bold";
  if (key === "i") return "italic";
  return "";
}

export const gutterBtnSx = {
  width: 22,
  height: 22,
  border: `1px solid ${apple.hairline}`,
  borderRadius: "7px",
  bgcolor: apple.page,
  color: apple.muted,
  cursor: "pointer",
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  p: 0,
  "&:hover": { bgcolor: apple.hoverFill, color: apple.text },
  "&:disabled": { opacity: 0.4, cursor: "not-allowed" },
} as const;

export const blockListSx = {
  display: "flex",
  flexDirection: "column",
  gap: 0,
} as const;

export function blockRowSx(type: string, index: number) {
  const heading = type === "title" || type === "heading" || type === "subheading";
  return {
    position: "relative",
    pl: "28px",
    mt: heading && index > 0 ? 1.25 : 0,
    pt: heading ? 0.35 : "1px",
    pb: heading ? 0.15 : "1px",
  } as const;
}

export const blockGutterSx = {
  position: "absolute",
  left: 0,
  top: 1,
  opacity: 0,
  pointerEvents: "none",
  display: "flex",
  flexDirection: "column",
  gap: 0.25,
  zIndex: 1,
  transition: "opacity 0.15s",
} as const;

const editorBase = {
  display: "block",
  width: "100%",
  border: 0,
  outline: "none",
  bgcolor: "transparent",
  font: "inherit",
  color: apple.text,
  p: 0,
  lineHeight: 1.5,
  minHeight: 24,
  whiteSpace: "pre-wrap",
  wordBreak: "break-word",
} as const;

const formattedSx = {
  "& strong, & b": { fontWeight: 700 },
  "& em, & i": { fontStyle: "italic" },
} as const;

const placeholderSx = {
  '&[data-empty="true"]::before': {
    content: "attr(data-placeholder)",
    color: apple.muted,
    pointerEvents: "none",
  },
} as const;

const focusedPlaceholderSx = {
  '&[data-empty="true"][data-hint="true"]::before': {
    content: "attr(data-placeholder)",
    color: apple.muted,
    pointerEvents: "none",
  },
} as const;

function fieldIsEmpty(el: HTMLElement) {
  return !(el.innerText || "").replace(/\u200B/g, "").trim();
}

function markEmpty(el: HTMLElement) {
  el.dataset.empty = fieldIsEmpty(el) ? "true" : "false";
}

export function AutoArea({
  value,
  onChange,
  onKeyDown,
  onFocus,
  placeholder,
  disabled,
  inputRef,
  sx,
}: {
  value: string;
  onChange: (value: string) => void;
  onKeyDown?: (event: KeyboardEvent<HTMLTextAreaElement>) => void;
  onFocus?: () => void;
  placeholder: string;
  disabled?: boolean;
  inputRef?: (el: HTMLTextAreaElement | null) => void;
  sx?: object;
}) {
  const inner = useRef<HTMLTextAreaElement>(null);
  const emitted = useRef<string | null>(null);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  const history = useRef<HistoryHandle | null>(null);
  if (!history.current) {
    history.current = createFieldHistory(
      inner,
      (el) => (el as HTMLTextAreaElement).value,
      (el, next) => {
        (el as HTMLTextAreaElement).value = next;
      },
      (next) => {
        emitted.current = next;
        onChangeRef.current(next);
      },
    );
  }

  function fit() {
    const el = inner.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = `${Math.max(el.scrollHeight, 24)}px`;
  }

  useLayoutEffect(() => {
    const el = inner.current;
    if (!el || history.current?.isRestoring()) return;
    if (emitted.current === value) {
      history.current?.ensure(el.value);
      fit();
      return;
    }
    if (el.value !== value) el.value = value;
    emitted.current = value;
    history.current?.reset(el.value);
    fit();
  }, [value]);

  useEffect(() => {
    const el = inner.current;
    if (!el) return;
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (onHistoryKey(event, history.current)) return;
    };
    el.addEventListener("keydown", onKey);
    return () => el.removeEventListener("keydown", onKey);
  }, []);

  return (
    <Box
      component="textarea"
      ref={(el: HTMLTextAreaElement | null) => {
        inner.current = el;
        inputRef?.(el);
      }}
      defaultValue={value}
      disabled={disabled}
      placeholder={placeholder}
      rows={1}
      onInput={(event) => {
        const el = event.currentTarget;
        if (history.current?.isRestoring()) return;
        const next = el.value;
        emitted.current = next;
        history.current?.snapshot();
        fit();
        onChange(next);
      }}
      onKeyDown={(event) => {
        if (historyAction(event)) return;
        onKeyDown?.(event);
      }}
      onFocus={() => {
        activeHistory = history.current;
        history.current?.snapshot();
        onFocus?.();
      }}
      sx={{
        ...editorBase,
        resize: "none",
        "&::placeholder": { color: apple.muted },
        ...sx,
      }}
    />
  );
}

function hasInlineMarkup(markdown: string) {
  return /(?:\*\*[^*]+\*\*|\*[^*]+\*)/.test(markdown);
}

function paintInline(el: HTMLElement, markdown: string) {
  const current = htmlToInlineMarkdown(el);
  const alreadyFormatted = Boolean(el.querySelector("strong, b, em, i"));
  if (current === markdown && (!hasInlineMarkup(markdown) || alreadyFormatted)) {
    markEmpty(el);
    return false;
  }
  el.innerHTML = inlineMarkdownToHtml(markdown) || "";
  markEmpty(el);
  return true;
}

export function RichField({
  value,
  onChange,
  onKeyDown,
  onFocus,
  placeholder,
  disabled,
  inputRef,
  showHint,
  sx,
}: {
  value: string;
  onChange: (value: string) => void;
  onKeyDown?: (event: KeyboardEvent<HTMLDivElement>) => void;
  onFocus?: () => void;
  placeholder: string;
  disabled?: boolean;
  inputRef?: (el: HTMLElement | null) => void;
  showHint?: boolean;
  sx?: object;
}) {
  const inner = useRef<HTMLDivElement>(null);
  const emitted = useRef<string | null>(null);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  const history = useRef<HistoryHandle | null>(null);
  if (!history.current) {
    history.current = createFieldHistory(
      inner,
      (el) => el.innerHTML,
      (el, html) => {
        el.innerHTML = html;
        markEmpty(el);
      },
      (html) => {
        const host = inner.current;
        if (!host) return;
        const markdown = htmlToInlineMarkdown(host);
        emitted.current = markdown;
        onChangeRef.current(markdown);
      },
    );
  }

  useLayoutEffect(() => {
    const el = inner.current;
    if (!el || history.current?.isRestoring()) return;
    if (emitted.current === value || (emitted.current !== null && htmlToInlineMarkdown(el) === value)) {
      emitted.current = value;
      markEmpty(el);
      history.current?.ensure(el.innerHTML);
      return;
    }
    const painted = paintInline(el, value);
    emitted.current = value;
    if (painted) history.current?.reset(el.innerHTML);
  }, [value]);

  useEffect(() => {
    const el = inner.current;
    if (!el) return;
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (onHistoryKey(event, history.current)) return;
    };
    el.addEventListener("keydown", onKey);
    return () => el.removeEventListener("keydown", onKey);
  }, []);

  function onEditorKey(event: KeyboardEvent<HTMLDivElement>) {
    if (historyAction(event)) return;
    onKeyDown?.(event);
  }

  return (
    <Box sx={{ ...editorBase, ...formattedSx, ...sx }}>
      <Box
        component="div"
        ref={(el: HTMLDivElement | null) => {
          inner.current = el;
          inputRef?.(el);
        }}
        role="textbox"
        aria-multiline
        aria-label={placeholder}
        aria-readonly={disabled || undefined}
        contentEditable={!disabled}
        suppressContentEditableWarning
        suppressHydrationWarning
        data-placeholder={placeholder}
        data-empty={!value.trim() ? "true" : "false"}
        data-hint={showHint ? "true" : "false"}
        onInput={() => {
          const el = inner.current;
          if (!el || history.current?.isRestoring()) return;
          markEmpty(el);
          history.current?.snapshot();
          const markdown = htmlToInlineMarkdown(el);
          emitted.current = markdown;
          onChange(markdown);
        }}
        onKeyDown={onEditorKey}
        onFocus={() => {
          activeHistory = history.current;
          history.current?.snapshot();
          onFocus?.();
        }}
        onPaste={(event) => {
          event.preventDefault();
          const text = event.clipboardData.getData("text/plain");
          document.execCommand("insertText", false, text);
        }}
        sx={{
          outline: "none",
          minHeight: 24,
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
          ...focusedPlaceholderSx,
          ...formattedSx,
        }}
      />
    </Box>
  );
}

function paintDocument(el: HTMLElement, markdown: string) {
  const current = htmlToDocumentMarkdown(el);
  const alreadyLined = Boolean(el.querySelector("[data-line]"));
  const alreadyFormatted = Boolean(el.querySelector("strong, b, em, i"));
  if (current === markdown && alreadyLined && (!hasInlineMarkup(markdown) || alreadyFormatted)) {
    markEmpty(el);
    return false;
  }
  el.innerHTML = documentMarkdownToHtml(markdown);
  markEmpty(el);
  return true;
}

export function DocField({
  value,
  onChange,
  onKeyDown,
  onSelect,
  placeholder,
  disabled,
  inputRef,
}: {
  value: string;
  onChange: (value: string) => void;
  onKeyDown?: (event: KeyboardEvent<HTMLDivElement>) => void;
  onSelect?: () => void;
  placeholder: string;
  disabled?: boolean;
  inputRef?: (el: HTMLElement | null) => void;
}) {
  const inner = useRef<HTMLDivElement>(null);
  const emitted = useRef<string | null>(null);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  const history = useRef<HistoryHandle | null>(null);
  if (!history.current) {
    history.current = createFieldHistory(
      inner,
      (el) => el.innerHTML,
      (el, html) => {
        el.innerHTML = html;
        markEmpty(el);
      },
      () => {
        const host = inner.current;
        if (!host) return;
        const markdown = htmlToDocumentMarkdown(host);
        emitted.current = markdown;
        onChangeRef.current(markdown);
      },
    );
  }

  useLayoutEffect(() => {
    const el = inner.current;
    if (!el || history.current?.isRestoring()) return;
    if (emitted.current === value || (emitted.current !== null && htmlToDocumentMarkdown(el) === value)) {
      emitted.current = value;
      markEmpty(el);
      history.current?.ensure(el.innerHTML);
      return;
    }
    const painted = paintDocument(el, value);
    emitted.current = value;
    if (painted) history.current?.reset(el.innerHTML);
  }, [value]);

  useEffect(() => {
    const el = inner.current;
    if (!el) return;
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (onHistoryKey(event, history.current)) return;
    };
    el.addEventListener("keydown", onKey);
    return () => el.removeEventListener("keydown", onKey);
  }, []);

  function sync() {
    const el = inner.current;
    if (!el || history.current?.isRestoring()) return;
    for (const child of Array.from(el.children)) {
      if (!child.getAttribute("data-line")) child.setAttribute("data-line", "paragraph");
    }
    markEmpty(el);
    history.current?.snapshot();
    const markdown = htmlToDocumentMarkdown(el);
    emitted.current = markdown;
    onChange(markdown);
    onSelect?.();
  }

  return (
    <Box sx={{ ...editorBase, ...formattedSx, minHeight: 480, fontSize: 16, lineHeight: 1.5 }}>
      <Box
        component="div"
        ref={(el: HTMLDivElement | null) => {
          inner.current = el;
          inputRef?.(el);
        }}
        role="textbox"
        aria-multiline
        aria-label={placeholder}
        aria-readonly={disabled || undefined}
        contentEditable={!disabled}
        suppressContentEditableWarning
        suppressHydrationWarning
        data-placeholder={placeholder}
        data-empty={!value.trim() ? "true" : "false"}
        onInput={sync}
        onKeyUp={onSelect}
        onClick={onSelect}
        onKeyDown={(event) => {
          if (historyAction(event)) return;
          onKeyDown?.(event);
        }}
        onFocus={() => {
          activeHistory = history.current;
          history.current?.snapshot();
        }}
        onPaste={(event) => {
          event.preventDefault();
          const text = event.clipboardData.getData("text/plain");
          document.execCommand("insertText", false, text);
        }}
        sx={{
          outline: "none",
          minHeight: 480,
          ...placeholderSx,
          ...formattedSx,
          "&:focus-visible": { outline: "2px solid", outlineColor: "divider", outlineOffset: 8 },
          "& [data-line='title']": { ...blockFace("title"), mt: 1.25, mb: 0.35 },
          "& [data-line='heading']": { ...blockFace("heading"), mt: 1, mb: 0.25 },
          "& [data-line='subheading']": { ...blockFace("subheading"), mt: 0.75, mb: 0.15 },
          "& [data-line='paragraph']": { my: 0 },
          "& [data-line='bullet']": { pl: 2.25, position: "relative", my: 0, "&:before": { content: '"•"', position: "absolute", left: 0, color: apple.muted } },
          "& [data-line='check']": { pl: 2.25, position: "relative", my: 0, "&:before": { content: '"☐"', position: "absolute", left: 0, color: apple.muted } },
        }}
      />
    </Box>
  );
}

export function currentDocLine(el: HTMLElement | null): HTMLElement | null {
  const sel = window.getSelection();
  if (!el || !sel || !sel.anchorNode || !el.contains(sel.anchorNode)) return el?.querySelector("[data-line]") as HTMLElement | null;
  const node = sel.anchorNode instanceof Element ? sel.anchorNode : sel.anchorNode.parentElement;
  return node?.closest("[data-line]") as HTMLElement | null;
}

export function setDocLineKind(el: HTMLElement | null, kind: DocLineKind) {
  const line = currentDocLine(el);
  if (!line) return;
  line.setAttribute("data-line", kind);
}

const HEADINGS: { id: HeadingKind; label: string }[] = [
  { id: "title", label: "Title" },
  { id: "heading", label: "Heading" },
  { id: "subheading", label: "Subhead" },
  { id: "paragraph", label: "Body" },
  { id: "bullet", label: "List" },
];

const compactBtn = { py: 0.4, px: 1.1, minWidth: 0, fontSize: 12 } as const;

export function FormatToolbar({
  disabled,
  blockType,
  onBlockType,
  onInline,
  extra,
}: {
  disabled?: boolean;
  blockType?: string;
  onBlockType?: (type: HeadingKind) => void;
  onInline: (kind: "bold" | "italic") => void;
  extra?: ReactNode;
}) {
  const [styleAnchor, setStyleAnchor] = useState<HTMLElement | null>(null);
  const selection = useRef<Range | null>(null);
  function chooseStyle(type: HeadingKind) {
    setStyleAnchor(null);
    const range = selection.current;
    if (range?.commonAncestorContainer.isConnected) {
      const current = window.getSelection();
      current?.removeAllRanges();
      current?.addRange(range);
    }
    onBlockType?.(type);
  }
  return (
    <Box role="toolbar" aria-label="Text formatting" sx={{ display: "flex", gap: 0.5, flexWrap: "wrap", alignItems: "center" }}>
      {onBlockType && <>
        <PillButton variant="gray" disabled={disabled} aria-label="Text style" aria-haspopup="menu" aria-expanded={Boolean(styleAnchor)}
          onMouseDown={event => event.preventDefault()}
          onClick={event => { const current = window.getSelection(); selection.current = current?.rangeCount ? current.getRangeAt(0).cloneRange() : null; setStyleAnchor(event.currentTarget); }}
          endIcon={<ExpandMoreRoundedIcon sx={{fontSize:16}}/>} sx={{...compactBtn, minWidth:100, justifyContent:"space-between"}}>
          {HEADINGS.find(item => item.id === blockType)?.label || "Style"}
        </PillButton>
        <Menu anchorEl={styleAnchor} open={Boolean(styleAnchor)} onClose={() => setStyleAnchor(null)} disableRestoreFocus>
          {HEADINGS.map(item => <MenuItem key={item.id} selected={item.id === blockType} onMouseDown={event => event.preventDefault()} onClick={() => chooseStyle(item.id)}>{item.label}</MenuItem>)}
        </Menu>
      </>}
      <PillButton
        variant="text"
        disabled={disabled}
        onMouseDown={(event) => event.preventDefault()}
        onClick={() => onInline("bold")}
        sx={{ ...compactBtn, fontWeight: 700 }}
      >
        Bold
      </PillButton>
      <PillButton
        variant="text"
        disabled={disabled}
        onMouseDown={(event) => event.preventDefault()}
        onClick={() => onInline("italic")}
        sx={{ ...compactBtn, fontStyle: "italic" }}
      >
        Italic
      </PillButton>
      <PillButton
        variant="text"
        disabled={disabled}
        aria-label="Undo"
        title="Undo"
        onMouseDown={(event) => event.preventDefault()}
        onClick={() => applyHistory("undo")}
        sx={compactBtn}
      >
        Undo
      </PillButton>
      <PillButton
        variant="text"
        disabled={disabled}
        aria-label="Redo"
        title="Redo"
        onMouseDown={(event) => event.preventDefault()}
        onClick={() => applyHistory("redo")}
        sx={compactBtn}
      >
        Redo
      </PillButton>
      {extra}
    </Box>
  );
}
