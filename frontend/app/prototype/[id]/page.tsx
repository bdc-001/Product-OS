"use client";

import { useParams } from "next/navigation";
import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import Box from "@mui/material/Box";
import IconButton from "@mui/material/IconButton";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import ChevronLeftRoundedIcon from "@mui/icons-material/ChevronLeftRounded";
import { api, type PrototypeSession } from "@/lib/api";
import { apple } from "@/app/ui/tokens";
import { Banner, PillButton, Segmented } from "@/app/ui";
import { useCopilot } from "@/app/copilot/context";

const PrototypeCodePane = dynamic(() => import("./code-pane").then((mod) => mod.PrototypeCodePane), {
  ssr: false,
  loading: () => (
    <Box sx={{ height: "100%", display: "grid", placeItems: "center", color: apple.muted, fontSize: 13 }}>
      Opening editor…
    </Box>
  ),
});

const CHAT_KEY = "prototype-chat-open";

export default function PrototypeStudioPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const { open } = useCopilot();
  const [session, setSession] = useState<PrototypeSession | null>(null);
  const [prompt, setPrompt] = useState("");
  const [target, setTarget] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [pane, setPane] = useState<"preview" | "code">("preview");
  const [activePath, setActivePath] = useState("src/pages/Campaigns.jsx");
  const [chatOpen, setChatOpen] = useState(true);
  const persist = useRef<Record<string, string>>({});
  const streamRef = useRef<HTMLDivElement | null>(null);
  const saveTimer = useRef<number>(0);

  const load = useCallback(() => {
    if (!id) return;
    api
      .prototype(id)
      .then((row) => {
        setSession(row);
        persist.current = Object.fromEntries((row.files || []).map((file) => [file.path, file.content]));
      })
      .catch((err) => setError(String(err)));
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    try {
      setChatOpen(window.localStorage.getItem(CHAT_KEY) !== "0");
    } catch {
      /* ignore */
    }
  }, []);

  function toggleChat(next: boolean) {
    setChatOpen(next);
    try {
      window.localStorage.setItem(CHAT_KEY, next ? "1" : "0");
    } catch {
      /* ignore */
    }
  }

  useEffect(() => {
    if (session?.status !== "generating") return;
    const timer = window.setInterval(load, 1500);
    return () => window.clearInterval(timer);
  }, [session?.status, load]);

  useEffect(() => {
    streamRef.current?.scrollTo({ top: streamRef.current.scrollHeight });
  }, [session?.messages, busy]);

  const files = session?.files || [];
  const filePaths = useMemo(
    () => files.map((file) => file.path).sort((a, b) => a.localeCompare(b)),
    [files],
  );

  useEffect(() => {
    if (!filePaths.length) return;
    if (filePaths.includes(activePath)) return;
    setActivePath(filePaths.find((path) => path.endsWith("Campaigns.jsx")) || filePaths[0]);
  }, [filePaths, activePath]);

  async function send(event: FormEvent) {
    event.preventDefault();
    const text = prompt.trim();
    if (!text || !id) return;
    setBusy(true);
    setError("");
    try {
      await api.prototypeTurn(id, text, undefined, target.trim() || (pane === "code" ? activePath : ""));
      setPrompt("");
      setPane("preview");
      load();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  const onDraft = useCallback((path: string, content: string) => {
    persist.current[path] = content;
    window.clearTimeout(saveTimer.current);
    saveTimer.current = window.setTimeout(() => {
      if (!id) return;
      void api.savePrototypeFile(id, path, content).catch(() => null);
    }, 400);
  }, [id]);

  const editorFiles = useMemo(
    () => files.map((file) => ({ path: file.path, content: persist.current[file.path] ?? file.content })),
    [files, pane, session?.messages?.length, session?.updated_at],
  );

  const messages = session?.messages || [];
  const generating = busy || session?.status === "generating";
  const revision = `${id}-${(session?.messages || []).length}-${session?.status || ""}`;

  return (
    <Box
      sx={{
        height: { xs: "calc(100dvh - 52px)", md: "100dvh" },
        display: "grid",
        gridTemplateColumns: chatOpen ? { xs: "1fr", md: "340px minmax(0,1fr)" } : "minmax(0,1fr)",
        minWidth: 0,
        bgcolor: apple.page,
        overflow: "hidden",
      }}
    >
      {chatOpen ? (
      <Box
        sx={{
          borderRight: `1px solid ${apple.hairline}`,
          display: "flex",
          flexDirection: "column",
          minWidth: 0,
          minHeight: 0,
          bgcolor: apple.nav,
        }}
      >
        <Box sx={{ px: 2, py: 1.5, borderBottom: `1px solid ${apple.hairline}`, display: "flex", alignItems: "center", gap: 1, bgcolor: apple.page }}>
          <Box sx={{ minWidth: 0, flex: 1 }}>
            <Typography sx={{ fontWeight: 650, fontSize: 15, letterSpacing: "-0.02em" }}>{session?.title || "Sense"}</Typography>
            <Typography sx={{ mt: 0.25, fontSize: 12, color: apple.muted }}>Prompt a change · Code copies into go_services</Typography>
          </Box>
          <IconButton
            size="small"
            aria-label="Hide prompt sidebar"
            onClick={() => toggleChat(false)}
            sx={{ border: `1px solid ${apple.hairline}`, bgcolor: apple.page, color: apple.muted, "&:hover": { bgcolor: apple.hoverFill } }}
          >
            <ChevronLeftRoundedIcon />
          </IconButton>
        </Box>
        <Box ref={streamRef} sx={{ flex: 1, overflow: "auto", p: 2, display: "flex", flexDirection: "column", gap: 1.25 }}>
          {error ? <Banner severity="error">{error}</Banner> : null}
          {session?.error ? <Banner severity="error">{session.error}</Banner> : null}
          {!messages.length ? (
            <Box
              sx={{
                border: `1px solid ${apple.hairline}`,
                borderRadius: "16px",
                bgcolor: apple.page,
                p: 2,
              }}
            >
              <Typography sx={{ fontSize: 14, fontWeight: 600, mb: 0.5 }}>Studio prompt</Typography>
              <Typography sx={{ fontSize: 13, color: apple.muted, lineHeight: 1.55 }}>
                This canvas is current Sense. Describe a screen or control, then Build. Hide this panel for a full preview.
              </Typography>
            </Box>
          ) : null}
          {messages.map((item) => (
            <Box
              key={item.id}
              className={`copilot-msg ${item.role === "user" ? "you" : "bot"}`}
              sx={{ maxWidth: "92%", ...(item.role === "user" ? { ml: "auto" } : { mr: "auto" }) }}
            >
              <b>{item.role === "user" ? "You" : "Studio"}</b>
              <p>{item.body}</p>
            </Box>
          ))}
        </Box>
        <Box component="form" onSubmit={send} sx={{ p: 1.5, borderTop: `1px solid ${apple.hairline}`, bgcolor: apple.page }}>
          <TextField
            size="small"
            fullWidth
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            disabled={generating}
            placeholder="Scope · screen, tab, or control"
            slotProps={{ htmlInput: { maxLength: 256 } }}
            sx={{ mb: 1 }}
          />
          <div className="copilot-input">
            <textarea
              value={prompt}
              disabled={generating}
              rows={3}
              placeholder="Describe the change…"
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  if (!generating && prompt.trim()) {
                    event.currentTarget.form?.requestSubmit();
                  }
                }
              }}
            />
            <PillButton type="submit" disabled={generating || !prompt.trim()}>
              {generating ? "…" : "Build"}
            </PillButton>
          </div>
        </Box>
      </Box>
      ) : null}
      <Box sx={{ minWidth: 0, minHeight: 0, height: "100%", display: "flex", flexDirection: "column", bgcolor: "#fff" }}>
        <Box sx={{ px: 2, py: 1, borderBottom: `1px solid ${apple.hairline}`, display: "flex", alignItems: "center", gap: 2, bgcolor: apple.page }}>
          {!chatOpen ? (
            <PillButton variant="gray" onClick={() => toggleChat(true)}>
              Prompt
            </PillButton>
          ) : null}
          <Box sx={{ width: 220 }}>
            <Segmented
              value={pane}
              onChange={(next) => setPane(next === "code" ? "code" : "preview")}
              options={[
                { id: "preview", label: "Preview" },
                { id: "code", label: "Code" },
              ]}
            />
          </Box>
          <Box sx={{ ml: "auto", display: "flex", gap: 1 }}>
            {id ? (
              <PillButton
                variant="gray"
                type="button"
                onClick={() =>
                  open({
                    prototype: id,
                    prompt: `Write a PRD from this Sense prototype${session?.title ? ` "${session.title}"` : ""}. Ground it in the prototype code and prompt history.`,
                  })
                }
              >
                Write PRD
              </PillButton>
            ) : null}
            {id ? (
              <PillButton variant="gray" href={api.prototypeExportUrl(id)} download>
                Export zip
              </PillButton>
            ) : null}
          </Box>
        </Box>
        <Box sx={{ flex: 1, minHeight: 0 }}>
          {pane === "preview" ? (
            id ? (
              <Box
                component="iframe"
                key={revision}
                title="Sense preview"
                src={api.prototypePreviewUrl(id, revision)}
                sx={{ width: "100%", height: "100%", border: 0, bgcolor: "#fff", display: "block" }}
              />
            ) : (
              <Box sx={{ p: 3, color: apple.muted }}>Loading Sense…</Box>
            )
          ) : (
            <PrototypeCodePane
              key={revision}
              files={editorFiles}
              activePath={activePath}
              revision={revision}
              onActivePath={setActivePath}
              onDraft={onDraft}
            />
          )}
        </Box>
      </Box>
    </Box>
  );
}
