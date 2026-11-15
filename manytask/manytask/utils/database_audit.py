"""Audit SQLAlchemy writes without logging SQL or bound values."""

from collections import Counter
from typing import Any
from uuid import uuid4

from sqlalchemy import event
from sqlalchemy.orm import ORMExecuteState, Session, SessionTransaction

from .audit import audit_context, audit_event

_STATE = "manytask_audit_transaction"
_SAVEPOINTS = "manytask_audit_savepoints"


def _record_write(session: Session, changes: dict[str, int]) -> None:
    state = session.info.setdefault(_STATE, {"transaction_id": uuid4().hex, "writes": []})
    record: dict[str, Any] = {"context": audit_context(), "changes": changes, "write_id": uuid4().hex}
    state["writes"].append(record)
    audit_event(
        "database.write",
        "attempted",
        context=record["context"],
        transaction_id=state["transaction_id"],
        write_id=record["write_id"],
        changes=changes,
    )


def _before_flush(session: Session, flush_context: Any, instances: Any) -> None:
    changes: Counter[str] = Counter()
    for action, objects in (("insert", session.new), ("update", session.dirty), ("delete", session.deleted)):
        for instance in objects:
            if action != "update" or session.is_modified(instance, include_collections=False):
                changes[f"{action}:{type(instance).__name__}"] += 1
    if changes:
        _record_write(session, dict(changes))


def _orm_execute(state: ORMExecuteState) -> None:
    if state.is_insert or state.is_update or state.is_delete:
        action = "insert" if state.is_insert else "update" if state.is_update else "delete"
        table = getattr(getattr(state.statement, "table", None), "name", "unknown")
        _record_write(state.session, {f"{action}:{table}": 1})


def _finish(session: Session, outcome: str, start: int = 0, *, nested: bool = False) -> None:
    state = session.info.get(_STATE)
    if state is None:
        return
    for record in state["writes"][start:]:
        audit_event(
            "database.write",
            outcome,
            context=record["context"],
            transaction_id=state["transaction_id"],
            write_id=record["write_id"],
            changes=record["changes"],
        )
    del state["writes"][start:]
    if not nested:
        session.info.pop(_STATE, None)


def _after_commit(session: Session) -> None:
    if transaction := session.get_nested_transaction():
        session.info.setdefault("manytask_audit_released", set()).add(transaction)
    else:
        _finish(session, "committed")


def _after_rollback(session: Session) -> None:
    transaction = session.get_nested_transaction()
    start = session.info.get(_SAVEPOINTS, {}).get(transaction, 0)
    _finish(session, "rolled_back", start, nested=transaction is not None)


def _transaction_created(session: Session, transaction: SessionTransaction) -> None:
    if transaction.nested:
        count = len(session.info.get(_STATE, {}).get("writes", []))
        session.info.setdefault(_SAVEPOINTS, {})[transaction] = count


def _transaction_ended(session: Session, transaction: SessionTransaction) -> None:
    snapshots = session.info.get(_SAVEPOINTS, {})
    if transaction.nested and transaction in snapshots:
        released = session.info.get("manytask_audit_released", set())
        if transaction not in released:
            _finish(session, "rolled_back", snapshots[transaction], nested=True)
        released.discard(transaction)
        snapshots.pop(transaction)
    if transaction.parent is None:
        # Session.close() rolls back pending writes without after_rollback.
        _finish(session, "rolled_back")
        session.info.pop(_SAVEPOINTS, None)
        session.info.pop("manytask_audit_released", None)


def audit_session(session: Session) -> Session:
    """Attach once, including sessions supplied by a custom session factory."""
    if not event.contains(session, "before_flush", _before_flush):
        for name, listener in (
            ("before_flush", _before_flush),
            ("do_orm_execute", _orm_execute),
            ("after_commit", _after_commit),
            ("after_rollback", _after_rollback),
            ("after_transaction_create", _transaction_created),
            ("after_transaction_end", _transaction_ended),
        ):
            event.listen(session, name, listener)
    return session
