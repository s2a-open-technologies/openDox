"""openDox - Medical transcription platform
Copyright (C) 2025  S2A Open Technologies gGmbH
SPDX-FileCopyrightText: 2025 S2A Open Technologies gGmbH
SPDX-License-Identifier: AGPL-3.0-or-later

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

Decides whether a recording gets an LLM summary and runs that step.

The LLM is optional on two levels: ``LlmSettingsModel.llm_enabled`` (is there
an LLM at all) and ``Categories.llm_enabled`` (does this category use it).
Without a summary ``Record.summarize`` stays empty in the DB and the API serves
the transcript in its place (``effective_summary``), because the desktop client
only reads ``summarize`` and must keep working unchanged.
"""

# Standard library
from typing import Optional

# Third party
from sqlmodel import Session, select

# Custom imports
from backend.components.llm.llm_model import SummarizeModel
from backend.components.models.categories import Categories
from backend.components.models.llm_settings_model import LlmSettingsModel
from backend.components.models.record_model import Record
from backend.components.services.sanitizing_service import (
    _PRESERVE_TOKENS_INSTRUCTION,
    reinject,
    sanitize,
)


def llm_globally_enabled(db: Session) -> bool:
    """Return the global LLM switch; no settings row means enabled (default)."""
    llm_settings = db.exec(select(LlmSettingsModel)).first()
    return llm_settings is None or bool(llm_settings.llm_enabled)


def category_llm_enabled(category: Optional[Categories]) -> bool:
    """Return the category switch; no category means the global switch decides."""
    return category is None or bool(category.llm_enabled)


def personal_categories_allowed(db: Session) -> bool:
    """Return whether users may have their own categories (default: no).

    Off by default because a user's own LLM prompt bypasses the operator's
    control over the intended purpose (docs/zweckbestimmung.md §6).
    """
    llm_settings = db.exec(select(LlmSettingsModel)).first()
    return llm_settings is not None and bool(llm_settings.personal_categories_allowed)


def effective_category(db: Session, record: Optional[Record]) -> Optional[Categories]:
    """Return the record's category as it applies to processing.

    A personal category counts as no category while the operator has not
    allowed personal categories (its prompts must not take effect), and so
    does another user's personal category.
    """
    if record is None or not record.category_id:
        return None
    category = db.get(Categories, record.category_id)
    if (
        category is not None
        and category.user_id is not None
        and (category.user_id != record.user_id or not personal_categories_allowed(db))
    ):
        return None
    return category


def summary_enabled(db: Session, record: Record) -> bool:
    """Return whether the record's pipeline runs the LLM summary step."""
    if not llm_globally_enabled(db):
        return False
    return category_llm_enabled(effective_category(db, record))


def effective_summary(record: Record, enabled: bool) -> str:
    """Return the text the API serves as ``summarize``.

    A stored summary always wins. Without one, a record whose category runs no
    LLM gets its transcript, so clients that only read ``summarize`` still get
    the result text — and always the current one, also after transcript edits.
    """
    if record.summarize:
        return record.summarize
    return "" if enabled else (record.content or "")


def run_summary(
    db: Session, category: Optional[Categories], text: str
) -> tuple[str, dict[str, str]]:
    """Sanitize ``text`` (if EntityGuard is configured) and summarize it.

    Uses the category's LLM override when active, else the global LLM.

    Returns:
        The summary with real names re-injected, and the entity mapping
        (empty when the sanitizer is off or found nothing).
    """
    llm_settings = db.exec(select(LlmSettingsModel)).first()
    text_for_llm = text
    entity_mapping: dict[str, str] = {}

    if (
        llm_settings
        and llm_settings.sanitizer_enabled
        and llm_settings.sanitizer_endpoint
    ):
        text_for_llm, entity_mapping = sanitize(
            text=text,
            endpoint=llm_settings.sanitizer_endpoint,
            api_key=llm_settings.sanitizer_api_key,
        )

    if category and category.llm_override_enabled and category.llm_model:
        model = SummarizeModel(
            model_name=category.llm_model,
            base_url=category.llm_api_endpoint,
            api_key=category.llm_api_key,
            temperature=category.llm_temperature,
            max_tokens=category.llm_max_tokens,
            top_p=category.llm_top_p,
            frequency_penalty=category.llm_frequency_penalty,
            enable_thinking=category.llm_enable_thinking,
        )
    else:
        model = SummarizeModel()

    category_prompt = category.system_prompt if category else None
    effective_prompt = (category_prompt or "") + (
        _PRESERVE_TOKENS_INSTRUCTION if entity_mapping else ""
    )
    summary = model.generate_response(
        text_for_llm, custom_system_prompt=effective_prompt or None
    )

    if entity_mapping:
        summary = reinject(summary, entity_mapping)

    return summary, entity_mapping
