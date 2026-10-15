"""PostgreSQL advisory lock used to serialise startup work across instances."""

from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine

from backend.components.sql.advisory_lock import advisory_lock


def test_is_a_no_op_on_sqlite():
    engine = create_engine("sqlite://")
    ran = []
    with advisory_lock(123, engine=engine):
        ran.append(True)
    assert ran == [True]


def _postgres_engine():
    engine = MagicMock()
    engine.dialect.name = "postgresql"
    connection = engine.connect.return_value.__enter__.return_value
    return engine, connection


def _statements(connection):
    return [str(call.args[0]) for call in connection.execute.call_args_list]


def test_locks_before_and_unlocks_after_the_body():
    engine, connection = _postgres_engine()
    order = []
    connection.execute.side_effect = lambda stmt, params=None: order.append(
        "lock" if "pg_advisory_lock" in str(stmt) else "unlock"
    )

    with advisory_lock(42, engine=engine):
        order.append("body")

    assert order == ["lock", "body", "unlock"]
    assert connection.execute.call_args_list[0].args[1] == {"key": 42}


def test_unlocks_even_if_the_body_raises():
    engine, connection = _postgres_engine()

    with pytest.raises(RuntimeError):
        with advisory_lock(42, engine=engine):
            raise RuntimeError("rotation failed")

    assert any("pg_advisory_unlock" in s for s in _statements(connection))
