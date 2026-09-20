"""Incremental, branch-pinned full-text retrieval. Reads Git objects without checkout."""
from __future__ import annotations
import json
from contextlib import contextmanager
import re
import sqlite3
import subprocess
import threading
from pathlib import PurePosixPath
from app.config import ROOT

INDEX_PATH = ROOT / "data" / "codebase" / "source.sqlite3"
LOCK = threading.Lock()
VERSION = 1
EXTENSIONS = {".go", ".py", ".ts", ".tsx", ".js", ".jsx", ".java", ".kt", ".rb", ".rs", ".c", ".h", ".cpp", ".cs", ".sql", ".proto", ".graphql", ".md", ".rst", ".txt", ".yaml", ".yml", ".toml", ".json", ".sh", ".html", ".css", ".xml"}
SKIP = {".git", "node_modules", "vendor", ".venv", "venv", "dist", "build", "coverage", "__pycache__", ".next", "fixtures", "testdata"}
SECRET = re.compile(r"(^|[/._-])(env|secret|secrets|credentials?|passwords?|id_rsa|service.account)([/._-]|$)|\.(pem|key|p12|pfx|keystore)$", re.I)
STOP = {"the", "and", "for", "with", "this", "that", "how", "does", "what", "where", "from", "please", "explain", "code", "codebase", "read", "into", "work", "works", "can", "you", "about", "service"}


@contextmanager
def connect():
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(INDEX_PATH, timeout=120)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript('''CREATE TABLE IF NOT EXISTS branches (branch TEXT PRIMARY KEY, sha TEXT, stats TEXT);
      CREATE TABLE IF NOT EXISTS files (branch TEXT, path TEXT, blob TEXT, PRIMARY KEY(branch,path));
      CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(branch UNINDEXED, path, body, start UNINDEXED, end UNINDEXED, tokenize='unicode61');''')
    try:
        with db:
            yield db
    finally:
        db.close()


def allowed(path):
    p = PurePosixPath(path)
    return not p.is_absolute() and ".." not in p.parts and not any(x in SKIP for x in p.parts) and not SECRET.search(path) and (p.suffix.lower() in EXTENSIONS or p.name in {"Dockerfile", "Makefile", "go.mod"})


def status(branch):
    with connect() as db:
        row = db.execute("SELECT sha,stats FROM branches WHERE branch=?", (branch,)).fetchone()
        return {"ready": bool(row), "branch": branch, **(json.loads(row["stats"]) if row else {}), "sha": row["sha"] if row else ""}


def build(branch):
    from app.services.codebase import codebase_root, resolve_branch_ref
    root = codebase_root()
    name, _, sha = resolve_branch_ref(root, branch)
    # Resolve immutable commit once; a branch advancing during indexing cannot mix versions.
    sha = subprocess.check_output(["git", "-C", str(root), "rev-parse", f"{sha}^{{commit}}"], text=True).strip()
    with LOCK, connect() as db:
        prior = db.execute("SELECT sha,stats FROM branches WHERE branch=?", (name,)).fetchone()
        if prior and prior["sha"] == sha and json.loads(prior["stats"]).get("version") == VERSION:
            return {"ready": True, "branch": name, "sha": sha, **json.loads(prior["stats"]), "cached": True}
        tree = subprocess.check_output(["git", "-C", str(root), "ls-tree", "-r", "-l", "-z", sha])
        entries = []
        skipped = 0
        for record in tree.split(b"\0"):
            if not record: continue
            meta, path_bytes = record.split(b"\t", 1)
            mode, kind, blob, size = meta.decode().split()
            path = path_bytes.decode("utf-8", "replace")
            if kind != "blob" or mode == "120000" or not allowed(path) or int(size) > 1024 * 1024:
                skipped += 1
                continue
            entries.append((path, blob))
        old = dict(db.execute("SELECT path,blob FROM files WHERE branch=?", (name,)).fetchall())
        current = dict(entries)
        changed = [(p, b) for p, b in entries if old.get(p) != b]
        for path in set(old) - set(current):
            db.execute("DELETE FROM chunks WHERE branch=? AND path=?", (name, path))
            db.execute("DELETE FROM files WHERE branch=? AND path=?", (name, path))
        proc = subprocess.Popen(["git", "-C", str(root), "cat-file", "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        try:
            for path, blob in changed:
                proc.stdin.write((blob + "\n").encode()); proc.stdin.flush()
                header = proc.stdout.readline().split()
                if len(header) != 3: raise RuntimeError("Could not read source object")
                raw = proc.stdout.read(int(header[2])); proc.stdout.read(1)
                db.execute("DELETE FROM chunks WHERE branch=? AND path=?", (name, path))
                if b"\0" in raw:
                    skipped += 1
                    db.execute("DELETE FROM files WHERE branch=? AND path=?", (name, path))
                    continue
                lines = raw.decode("utf-8", "replace").splitlines()
                for start in range(0, len(lines), 60):
                    end = min(start + 80, len(lines))
                    db.execute("INSERT INTO chunks(branch,path,body,start,end) VALUES(?,?,?,?,?)", (name, path, "\n".join(lines[start:end]), start + 1, end))
                db.execute("INSERT OR REPLACE INTO files VALUES(?,?,?)", (name, path, blob))
        finally:
            proc.stdin.close(); proc.stdout.close(); proc.wait(timeout=10)
        modules = [dict(row) for row in db.execute("SELECT CASE WHEN instr(path,'/')>0 THEN substr(path,1,instr(path,'/')-1) ELSE '(root)' END AS name,count(*) AS files FROM files WHERE branch=? GROUP BY name ORDER BY files DESC", (name,))]
        stats = {"version": VERSION, "file_count": db.execute("SELECT count(*) FROM files WHERE branch=?", (name,)).fetchone()[0], "chunk_count": db.execute("SELECT count(*) FROM chunks WHERE branch=?", (name,)).fetchone()[0], "updated_files": len(changed), "skipped_files": skipped, "modules": modules}
        db.execute("INSERT OR REPLACE INTO branches VALUES(?,?,?)", (name, sha, json.dumps(stats)))
        db.commit()
    return {"ready": True, "branch": name, "sha": sha, **stats}


def search(branch, query, scope="", limit=8):
    stats = build(branch)
    if not scope:
        scope = next((m["name"] + "/" for m in stats.get("modules", []) if m["name"] != "(root)" and m["name"].lower() in query.lower()), "")
    tokens = list(dict.fromkeys(t.lower() for t in re.findall(r"[A-Za-z][A-Za-z0-9_]{2,}", query) if t.lower() not in STOP))[:16]
    expr = " OR ".join('"' + t + '"' for t in tokens)
    with connect() as db:
        if expr:
            rows = db.execute("SELECT path,body,start,end FROM chunks WHERE chunks MATCH ? AND branch=? AND path LIKE ? ORDER BY bm25(chunks,0,5,1,0,0) LIMIT ?", (expr, stats["branch"], scope + "%", limit * 8)).fetchall()
        else:
            rows = []
        if re.search(r"architecture|overview|structure|entry.?point", query, re.I):
            entry = db.execute("SELECT path,body,start,end FROM chunks WHERE branch=? AND path LIKE ? AND (path LIKE '%/main.go' OR path LIKE '%README.md' OR path LIKE '%/routes.go' OR path LIKE '%/router.go') AND start=1 LIMIT 6", (stats["branch"], scope + "%")).fetchall()
            rows = entry + rows
        seen, selected = {}, []
        for row in rows:
            if seen.get(row["path"], 0) >= 2: continue
            seen[row["path"]] = seen.get(row["path"], 0) + 1
            selected.append(row)
            if len(selected) >= limit: break
        rows = selected
    return {"branch": stats["branch"], "sha": stats["sha"], "file_count": stats["file_count"], "chunk_count": stats["chunk_count"], "hits": [{"path": r["path"], "line": r["start"], "end_line": r["end"], "text": r["body"][:6500]} for r in rows], "note": "Retrieved source excerpts from a committed Git snapshot; uncommitted changes are excluded."}
