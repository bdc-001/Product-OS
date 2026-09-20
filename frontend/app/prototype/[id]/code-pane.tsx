"use client";

import ChevronRightRoundedIcon from "@mui/icons-material/ChevronRightRounded";
import CloseRoundedIcon from "@mui/icons-material/CloseRounded";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import Box from "@mui/material/Box";
import IconButton from "@mui/material/IconButton";
import InputBase from "@mui/material/InputBase";
import Typography from "@mui/material/Typography";
import {
  SandpackCodeEditor,
  SandpackProvider,
  useSandpack,
  type SandpackFiles,
  type SandpackTheme,
} from "@codesandbox/sandpack-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { apple, fontFamily } from "@/app/ui/tokens";

type ProtoFile = { path: string; content: string };

type TreeNode = {
  name: string;
  path: string;
  kind: "file" | "folder";
  children: TreeNode[];
};

const EDITOR_THEME: SandpackTheme = {
  colors: {
    surface1: "#ffffff",
    surface2: "#f5f5f7",
    surface3: "rgba(0, 0, 0, 0.05)",
    disabled: "#c5c5c7",
    base: "#1d1d1f",
    clickable: "#6e6e73",
    hover: "#1d1d1f",
    accent: "#1d1d1f",
    error: "#b80000",
    errorSurface: "#fff2f2",
    warning: "#6e6e73",
    warningSurface: "#f5f5f7",
  },
  syntax: {
    plain: "#1d1d1f",
    comment: { color: "#86868b", fontStyle: "italic" },
    keyword: "#af00db",
    tag: "#0000ff",
    punctuation: "#1d1d1f",
    definition: "#0070c1",
    property: "#001080",
    static: "#0000ff",
    string: "#a31515",
  },
  font: {
    body: fontFamily,
    mono: 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace',
    size: "13px",
    lineHeight: "20px",
  },
};

const DEFAULT_OPEN = [
  "src",
  "src/features",
  "src/features/campaigns",
  "src/components",
  "src/components/layout",
  "src/components/filters",
];

function languageOf(path: string) {
  const ext = path.split(".").pop()?.toLowerCase() || "";
  if (ext === "tsx") return "TypeScript React";
  if (ext === "ts") return "TypeScript";
  if (ext === "jsx") return "JavaScript React";
  if (ext === "js" || ext === "mjs" || ext === "cjs") return "JavaScript";
  if (ext === "css") return "CSS";
  if (ext === "json") return "JSON";
  if (ext === "svg") return "SVG";
  if (ext === "md") return "Markdown";
  if (ext === "toml") return "TOML";
  if (ext === "html") return "HTML";
  return ext.toUpperCase() || "Plain text";
}

function tintOf(path: string) {
  const ext = path.split(".").pop()?.toLowerCase() || "";
  if (ext === "tsx" || ext === "jsx") return "#3178c6";
  if (ext === "ts" || ext === "js" || ext === "mjs") return "#7b7b7b";
  if (ext === "css") return "#6e6e73";
  if (ext === "json") return "#6e6e73";
  if (ext === "svg") return "#6e6e73";
  return "#86868b";
}

function sandpackPath(path: string) {
  return path.startsWith("/") ? path : `/${path}`;
}

function studioPath(path: string) {
  return path.replace(/^\//, "");
}

function ancestors(path: string) {
  const parts = path.split("/");
  const rows: string[] = [];
  for (let i = 1; i < parts.length; i += 1) rows.push(parts.slice(0, i).join("/"));
  return rows;
}

function buildTree(paths: string[]): TreeNode[] {
  const root: TreeNode = { name: "", path: "", kind: "folder", children: [] };
  const folders = new Map<string, TreeNode>([["", root]]);
  for (const path of [...paths].sort((a, b) => a.localeCompare(b))) {
    const parts = path.split("/").filter(Boolean);
    let parentPath = "";
    parts.forEach((name, index) => {
      const acc = parentPath ? `${parentPath}/${name}` : name;
      const parent = folders.get(parentPath);
      if (!parent) return;
      const isFile = index === parts.length - 1;
      if (isFile) {
        if (!parent.children.some((child) => child.path === acc && child.kind === "file")) {
          parent.children.push({ name, path: acc, kind: "file", children: [] });
        }
      } else if (!folders.has(acc)) {
        const folder: TreeNode = { name, path: acc, kind: "folder", children: [] };
        parent.children.push(folder);
        folders.set(acc, folder);
      }
      parentPath = acc;
    });
  }
  const sortNodes = (nodes: TreeNode[]) => {
    nodes.sort((a, b) => {
      if (a.kind !== b.kind) return a.kind === "folder" ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
    nodes.forEach((node) => sortNodes(node.children));
  };
  sortNodes(root.children);
  return root.children;
}

function filterTree(nodes: TreeNode[], query: string): TreeNode[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return nodes;
  const walk = (node: TreeNode): TreeNode | null => {
    if (node.kind === "file") {
      return node.path.toLowerCase().includes(needle) || node.name.toLowerCase().includes(needle) ? node : null;
    }
    const children = node.children.map(walk).filter((child): child is TreeNode => Boolean(child));
    if (children.length || node.path.toLowerCase().includes(needle) || node.name.toLowerCase().includes(needle)) {
      return { ...node, children };
    }
    return null;
  };
  return nodes.map(walk).filter((node): node is TreeNode => Boolean(node));
}

function FileTree({
  paths,
  activePath,
}: {
  paths: string[];
  activePath: string;
}) {
  const { sandpack } = useSandpack();
  const selectedPath = studioPath(sandpack.activeFile || activePath);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState<Set<string>>(() => {
    const next = new Set(DEFAULT_OPEN);
    ancestors(activePath).forEach((path) => next.add(path));
    return next;
  });
  const tree = useMemo(() => filterTree(buildTree(paths), query), [paths, query]);
  const searching = Boolean(query.trim());

  function toggle(path: string) {
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }

  function renderNode(node: TreeNode, depth: number) {
    const expanded = searching || open.has(node.path);
            const selected = node.kind === "file" && node.path === selectedPath;
    return (
      <Box key={`${node.kind}:${node.path}`}>
        <Box
          component="button"
          type="button"
          title={node.path}
          aria-expanded={node.kind === "folder" ? expanded : undefined}
          onClick={() => {
            if (node.kind === "folder") toggle(node.path);
            else sandpack.openFile(sandpackPath(node.path));
          }}
          sx={{
            display: "flex",
            alignItems: "center",
            gap: 0.25,
            width: "100%",
            minHeight: 24,
            pl: `${8 + depth * 12}px`,
            pr: 1,
            border: 0,
            borderRadius: "6px",
            cursor: "pointer",
            textAlign: "left",
            fontFamily: "inherit",
            bgcolor: selected ? apple.selFill : "transparent",
            color: apple.text,
            "&:hover": { bgcolor: selected ? apple.selFill : apple.hoverFill },
          }}
        >
          {node.kind === "folder" ? (
            <ChevronRightRoundedIcon
              sx={{
                fontSize: 16,
                color: apple.muted,
                flexShrink: 0,
                transform: expanded ? "rotate(90deg)" : "none",
                transition: "transform 120ms",
              }}
            />
          ) : (
            <Box sx={{ width: 16, display: "grid", placeItems: "center", flexShrink: 0 }}>
              <Box sx={{ width: 7, height: 7, borderRadius: "2px", bgcolor: tintOf(node.path) }} />
            </Box>
          )}
          <Typography
            component="span"
            sx={{
              fontSize: 12.5,
              lineHeight: 1.3,
              fontWeight: selected || node.kind === "folder" ? 600 : 500,
              color: node.kind === "folder" ? apple.text : apple.text,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {node.name}
          </Typography>
        </Box>
        {node.kind === "folder" && expanded
          ? node.children.map((child) => renderNode(child, depth + 1))
          : null}
      </Box>
    );
  }

  return (
    <Box
      sx={{
        height: "100%",
        minWidth: 0,
        display: "flex",
        flexDirection: "column",
        bgcolor: apple.nav,
        borderRight: `1px solid ${apple.hairline}`,
      }}
    >
      <Box sx={{ px: 1.25, pt: 1.25, pb: 1 }}>
        <Typography sx={{ fontSize: 11, fontWeight: 650, letterSpacing: "0.06em", color: apple.muted, mb: 1 }}>
          EXPLORER
        </Typography>
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            gap: 0.75,
            px: 1,
            py: 0.5,
            borderRadius: "8px",
            bgcolor: "#fff",
            border: `1px solid ${apple.hairline}`,
          }}
        >
          <SearchRoundedIcon sx={{ fontSize: 16, color: apple.muted }} />
          <InputBase
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search files"
            inputProps={{ "aria-label": "Search files", spellCheck: false }}
            sx={{ flex: 1, fontSize: 12.5, py: 0.25 }}
          />
        </Box>
      </Box>
      <Box role="tree" aria-label="Prototype files" sx={{ flex: 1, minHeight: 0, overflow: "auto", px: 0.75, pb: 1.5 }}>
        {tree.length ? tree.map((node) => renderNode(node, 0)) : (
          <Typography sx={{ px: 1, fontSize: 12, color: apple.muted }}>No matching files.</Typography>
        )}
      </Box>
    </Box>
  );
}

function EditorTabs() {
  const { sandpack } = useSandpack();
  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "stretch",
        minHeight: 36,
        bgcolor: apple.nav,
        borderBottom: `1px solid ${apple.hairline}`,
        overflowX: "auto",
      }}
    >
      {sandpack.visibleFiles.map((file) => {
        const path = studioPath(file);
        const active = file === sandpack.activeFile;
        const name = path.split("/").pop() || path;
        return (
          <Box
            key={file}
            component="button"
            type="button"
            onClick={() => sandpack.setActiveFile(file)}
            title={path}
            sx={{
              display: "flex",
              alignItems: "center",
              gap: 0.75,
              px: 1.25,
              border: 0,
              borderRight: `1px solid ${apple.hairline}`,
              borderBottom: active ? "2px solid #1d1d1f" : "2px solid transparent",
              bgcolor: active ? "#fff" : "transparent",
              color: apple.text,
              cursor: "pointer",
              fontFamily: "inherit",
              flexShrink: 0,
            }}
          >
            <Box sx={{ width: 7, height: 7, borderRadius: "2px", bgcolor: tintOf(path), flexShrink: 0 }} />
            <Typography component="span" sx={{ fontSize: 12.5, fontWeight: active ? 650 : 500, whiteSpace: "nowrap" }}>
              {name}
            </Typography>
            {sandpack.visibleFiles.length > 1 ? (
              <IconButton
                size="small"
                aria-label={`Close ${name}`}
                onClick={(event) => {
                  event.stopPropagation();
                  sandpack.closeFile(file);
                }}
                sx={{ p: 0.15, color: apple.muted }}
              >
                <CloseRoundedIcon sx={{ fontSize: 14 }} />
              </IconButton>
            ) : null}
          </Box>
        );
      })}
    </Box>
  );
}

function StatusBar() {
  const { sandpack } = useSandpack();
  const path = studioPath(sandpack.activeFile);
  const code = sandpack.files[sandpack.activeFile]?.code || "";
  const lines = code ? code.split("\n").length : 0;
  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        gap: 1.5,
        minHeight: 28,
        px: 1.5,
        bgcolor: apple.nav,
        borderTop: `1px solid ${apple.hairline}`,
        color: apple.muted,
      }}
    >
      <Typography sx={{ fontSize: 11, fontWeight: 600, color: apple.text }}>{languageOf(path)}</Typography>
      <Typography sx={{ fontSize: 11, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{path}</Typography>
      <Typography sx={{ fontSize: 11, ml: "auto", flexShrink: 0 }}>{lines} lines</Typography>
    </Box>
  );
}

function EditorSync({
  onActivePath,
  onDraft,
}: {
  onActivePath: (path: string) => void;
  onDraft: (path: string, content: string) => void;
}) {
  const { sandpack } = useSandpack();
  const path = studioPath(sandpack.activeFile);
  const code = sandpack.files[sandpack.activeFile]?.code ?? "";
  const last = useRef({ path: "", code: "" });

  useEffect(() => {
    if (path) onActivePath(path);
  }, [path, onActivePath]);

  useEffect(() => {
    if (last.current.path === path && last.current.code !== code) onDraft(path, code);
    last.current = { path, code };
  }, [path, code, onDraft]);

  return null;
}

export function PrototypeCodePane({
  files,
  activePath,
  revision,
  onActivePath,
  onDraft,
}: {
  files: ProtoFile[];
  activePath: string;
  revision: string;
  onActivePath: (path: string) => void;
  onDraft: (path: string, content: string) => void;
}) {
  const paths = useMemo(() => files.map((file) => file.path), [files]);
  const sandpackFiles = useMemo(() => {
    const next: SandpackFiles = {};
    files.forEach((file) => {
      next[sandpackPath(file.path)] = file.content;
    });
    return next;
    // Recreate the editor document only when the prototype revision changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [revision, files.length]);
  const current = paths.includes(activePath) ? activePath : paths[0] || "src/pages/Campaigns.jsx";
  const handlePath = useCallback((path: string) => onActivePath(path), [onActivePath]);
  const handleDraft = useCallback((path: string, content: string) => onDraft(path, content), [onDraft]);

  if (!paths.length) {
    return (
      <Box sx={{ height: "100%", display: "grid", placeItems: "center", color: apple.muted, fontSize: 13 }}>
        No files in this prototype.
      </Box>
    );
  }

  return (
    <Box
      sx={{
        height: "100%",
        minHeight: 0,
        "& .sp-wrapper": { height: "100%", width: "100%" },
        "& .sp-stack": { height: "100%", background: "transparent" },
        "& .sp-code-editor": { flex: 1, minHeight: 0, overflow: "hidden" },
        "& .cm-editor": { height: "100%", fontSize: 13 },
        "& .cm-scroller": { overflow: "auto", fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace' },
        "& .cm-gutters": { background: apple.nav, borderRight: `1px solid ${apple.hairline}`, color: apple.muted },
      }}
    >
      <SandpackProvider
        files={sandpackFiles}
        theme={EDITOR_THEME}
        customSetup={{ environment: "static" }}
        options={{
          autorun: false,
          autoReload: false,
          skipEval: true,
          initMode: "immediate",
          activeFile: sandpackPath(current),
          visibleFiles: [sandpackPath(current)],
        }}
        style={{ height: "100%", width: "100%" }}
      >
        <EditorSync onActivePath={handlePath} onDraft={handleDraft} />
        <Box sx={{ height: "100%", display: "grid", gridTemplateColumns: { xs: "188px minmax(0,1fr)", md: "248px minmax(0,1fr)" } }}>
          <FileTree paths={paths} activePath={current} />
          <Box sx={{ minWidth: 0, minHeight: 0, height: "100%", display: "flex", flexDirection: "column" }}>
            <EditorTabs />
            <Box sx={{ flex: 1, minHeight: 0 }}>
              <SandpackCodeEditor
                showTabs={false}
                showLineNumbers
                showRunButton={false}
                wrapContent={false}
                initMode="immediate"
                style={{ height: "100%" }}
              />
            </Box>
            <StatusBar />
          </Box>
        </Box>
      </SandpackProvider>
    </Box>
  );
}
