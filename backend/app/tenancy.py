"""Row-level workspace isolation for the ORM.

Every domain model mixes in `WorkspaceScoped`. A session hook adds `workspace_id = <current>` to
every ORM SELECT, UPDATE and DELETE that touches a scoped model, and new rows take the current
workspace by default. Queries without an active workspace fail unless the caller is explicitly in
`context.system()` (scheduler, worker claims, migrations).
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text, event
from sqlalchemy.orm import Mapped, Mapper, Session, declared_attr, mapped_column, with_loader_criteria

from app import context


class TenancyError(RuntimeError):
    pass


def _default_workspace_id() -> int:
    wid = context.current_workspace_id()
    if wid is None:
        raise TenancyError("Cannot create a workspace row without an active workspace.")
    return wid


class WorkspaceScoped:
    @declared_attr
    def workspace_id(cls) -> Mapped[int]:
        return mapped_column(
            Integer,
            ForeignKey("workspaces.id", ondelete="CASCADE"),
            index=True,
            nullable=False,
            default=_default_workspace_id,
        )


def is_scoped(model: type) -> bool:
    return isinstance(model, type) and issubclass(model, WorkspaceScoped)


def scoped(db: Session, model: type):
    """Explicit workspace filter; the session hook applies the same criteria automatically."""
    wid = context.current_workspace_id()
    if wid is None:
        raise TenancyError(f"{model.__name__} query needs an active workspace.")
    return db.query(model).filter(model.workspace_id == wid)


@event.listens_for(Session, "do_orm_execute")
def _workspace_criteria(state) -> None:
    if state.is_column_load or state.is_relationship_load:
        return
    if not any(is_scoped(mapper.class_) for mapper in state.all_mappers):
        return
    wid = context.current_workspace_id()
    if wid is None:
        if context.is_system():
            return
        names = ", ".join(sorted(m.class_.__name__ for m in state.all_mappers if is_scoped(m.class_)))
        raise TenancyError(f"Query on {names} has no active workspace.")
    state.statement = state.statement.options(
        with_loader_criteria(WorkspaceScoped, lambda cls: cls.workspace_id == wid, include_aliases=True)
    )


def _clean_strings(mapper: Mapper, target) -> None:
    # Postgres enforces VARCHAR lengths and rejects NUL bytes; SQLite silently accepted both.
    for column in mapper.columns:
        if not isinstance(column.type, (String, Text)):
            continue
        key = mapper.get_property_by_column(column).key
        value = target.__dict__.get(key)
        if not isinstance(value, str):
            continue
        cleaned = value.replace("\x00", "")
        length = getattr(column.type, "length", None)
        if length and len(cleaned) > length:
            cleaned = cleaned[:length]
        if cleaned is not value and cleaned != value:
            setattr(target, key, cleaned)


@event.listens_for(Mapper, "before_insert")
def _before_insert(mapper, _connection, target) -> None:
    _clean_strings(mapper, target)


@event.listens_for(Mapper, "before_update")
def _before_update(mapper, _connection, target) -> None:
    _clean_strings(mapper, target)
