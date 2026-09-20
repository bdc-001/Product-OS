from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.common import CodebaseAskBody, CodebaseIndexBody
from app.database import get_db
from app.services.codebase import (
    ask_codebase,
    build_query_index,
    get_query_index,
    list_asks,
    list_recent_branches,
    refresh_live_summary,
    snapshot_out,
    update_index,
)
from app.services.jobs import enqueue, job_out
from app.services.profile import save_profile

router = APIRouter()


@router.get("/codebase/status")
def codebase_status(db: Session = Depends(get_db)):
    return snapshot_out(db)


@router.get("/codebase/asks")
def codebase_asks(db: Session = Depends(get_db)):
    return {"asks": list_asks(db)}


@router.post("/codebase/branches")
def codebase_branches(fetch: bool = True):
    try:
        return list_recent_branches(fetch=fetch)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/codebase/index")
def codebase_index(body: CodebaseIndexBody, db: Session = Depends(get_db)):
    branch = (body.branch or "").strip() or None
    pull = body.pull

    def work(session, set_step):
        set_step("index", {"ok": True, "status": "running", "branch": branch or ""})
        result = update_index(session, pull=pull, branch=branch)
        set_step("index", {"ok": True, "status": "done", "branch": (result or {}).get("indexed_branch") or branch or ""})
        return {"ok": True, **(result or {})}

    job = enqueue(db, "index", work)
    return JSONResponse(status_code=202, content=job_out(job))


@router.get("/codebase/query-index")
def codebase_query_get(branch: str = ""):
    return get_query_index(branch)


@router.post("/codebase/query-index")
def codebase_query_build(body: CodebaseIndexBody):
    try:
        return build_query_index((body.branch or "").strip())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/codebase/ask")
def codebase_ask(body: CodebaseAskBody, db: Session = Depends(get_db)):
    try:
        return ask_codebase(db, body.question, branch=(body.branch or "").strip())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/codebase/data-branch")
def codebase_data_branch(body: CodebaseIndexBody, db: Session = Depends(get_db)):
    branch = (body.branch or "").strip()
    save_profile({"data_branch": branch})
    out = snapshot_out(db)
    out["data_branch"] = branch
    return out


@router.post("/codebase/live")
def codebase_live(db: Session = Depends(get_db)):
    try:
        return refresh_live_summary(db)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/codebase/update")
def codebase_update(pull: bool = True, db: Session = Depends(get_db)):
    try:
        return update_index(db, pull=pull)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@router.get("/codebase/source-index")
def source_status(branch: str):
    from app.services.source_index import status
    return status(branch)

@router.post("/codebase/source-index")
def source_build(body: CodebaseIndexBody, db: Session = Depends(get_db)):
    from app.services.source_index import build
    def work(session, set_step):
        set_step("source", {"status": "running", "branch": body.branch})
        result = build(body.branch)
        set_step("source", {"ok": True, "status": "done", "count": result["file_count"]})
        return {"ok": True, **result}
    return JSONResponse(status_code=202, content=job_out(enqueue(db, "source-index", work)))

@router.get("/codebase/source-search")
def source_search(branch: str, q: str, scope: str = ""):
    from app.services.source_index import search
    try: return search(branch, q, scope)
    except (RuntimeError, FileNotFoundError) as exc: raise HTTPException(400, str(exc)) from exc

@router.get("/codebase/source-file")
def source_file(branch: str, path: str, line: int = 1):
    from fastapi.responses import PlainTextResponse
    from app.services.source_index import allowed
    from app.services.codebase import codebase_root, resolve_branch_ref, _git
    if not allowed(path): raise HTTPException(400, "This path is not available for source reading")
    try:
        root = codebase_root()
        _, _, sha = resolve_branch_ref(root, branch)
        data = _git(root, "show", f"{sha}:{path}")
        if data.returncode: raise HTTPException(404, "Source file not found")
        lines = data.stdout.splitlines()
        start = max(0,line - 20)
        return PlainTextResponse(f"{path} @ {sha}\n\n" + "\n".join(f"{i+1}: {text}" for i,text in enumerate(lines) if start<=i<start+240))
    except RuntimeError as exc: raise HTTPException(400, str(exc)) from exc
