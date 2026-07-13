"""Tests for backend.components.modules.logger.

Regression coverage for a production bug: initialize_logging() used to
borrow handlers from the "uvicorn.error" logger, which is empty at the
point create_app() runs during app import (before uvicorn configures its
own logging) — leaving the root logger with zero handlers and silently
dropping every application log line, with no error.
"""

import logging

from backend.components.modules import logger as logger_module


def test_initialize_logging_attaches_a_handler_even_without_uvicorn_configured():
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    # Simulate the real startup ordering: uvicorn hasn't attached anything
    # to "uvicorn.error" yet when create_app() runs.
    logging.getLogger("uvicorn.error").handlers.clear()

    logger_module.initialize_logging()

    assert len(root_logger.handlers) > 0


def test_app_logger_output_reaches_the_attached_handler(capsys):
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    logging.getLogger("uvicorn.error").handlers.clear()

    logger_module.initialize_logging()
    logger_module.get_logger("test.startup").info("checkpoint reached")

    captured = capsys.readouterr()
    assert "checkpoint reached" in captured.err


def test_initialize_logging_is_idempotent_and_does_not_duplicate_handlers():
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    logger_module.initialize_logging()
    logger_module.initialize_logging()

    assert len(root_logger.handlers) == 1


def test_initialize_logging_keeps_uvicorn_error_propagation_enabled():
    # Regression guard: uvicorn.error has no handlers of its own — the
    # "Uvicorn running on ..." startup banner only reaches a handler by
    # propagating to the parent "uvicorn" logger. Setting propagate=False
    # here silently swallowed the banner in production.
    logging.getLogger("uvicorn.error").propagate = True

    logger_module.initialize_logging()

    assert logging.getLogger("uvicorn.error").propagate is True
    assert logging.getLogger("uvicorn.access").propagate is True


def test_initialize_logging_recovers_from_fileconfig_style_reconfiguration():
    # alembic/env.py runs fileConfig(alembic.ini), which replaces the root
    # handler and sets the root level to WARNING. _run_alembic_migrations()
    # calls initialize_logging() again afterwards — this pins that a re-init
    # actually restores INFO-level app logging.
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.WARNING)
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    root_logger.addHandler(logging.NullHandler())

    logger_module.initialize_logging()

    assert root_logger.isEnabledFor(logging.INFO)
    assert any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, logging.NullHandler)
        for h in root_logger.handlers
    )
