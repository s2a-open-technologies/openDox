"""openDox - Medical transcription platform
Copyright (C) 2025  Christopher Abanilla <christopher.abanilla@gmx.de>
SPDX-FileCopyrightText: 2025 Christopher Abanilla <christopher.abanilla@gmx.de>
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
"""

from typing import Optional

from sqlmodel import Field, SQLModel


class Categories(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    description: str
    system_prompt: str
    whisper_prompt: Optional[str] = Field(default=None)
    llm_override_enabled: bool = Field(default=False)
    llm_model: Optional[str] = Field(default=None)
    llm_api_endpoint: Optional[str] = Field(default=None)
    llm_api_key: Optional[str] = Field(default=None)
    llm_temperature: Optional[float] = Field(default=None)
    llm_max_tokens: Optional[int] = Field(default=None)
    llm_top_p: Optional[float] = Field(default=None)
    llm_frequency_penalty: Optional[float] = Field(default=None)
    llm_enable_thinking: Optional[bool] = Field(default=None)
    user_id: Optional[int] = Field(default=None)


class CategoriesCreate(SQLModel):
    name: str
    description: str
    system_prompt: str
    whisper_prompt: Optional[str] = None
    llm_override_enabled: bool = False
    llm_model: Optional[str] = None
    llm_api_endpoint: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_temperature: Optional[float] = None
    llm_max_tokens: Optional[int] = None
    llm_top_p: Optional[float] = None
    llm_frequency_penalty: Optional[float] = None
    llm_enable_thinking: Optional[bool] = None


class CategoriesRead(SQLModel):
    id: int
    name: str
    description: str
    system_prompt: str
    whisper_prompt: Optional[str] = None
    llm_override_enabled: bool
    llm_model: Optional[str]
    llm_api_endpoint: Optional[str]
    llm_api_key: Optional[str]
    llm_temperature: Optional[float]
    llm_max_tokens: Optional[int]
    llm_top_p: Optional[float] = None
    llm_frequency_penalty: Optional[float] = None
    llm_enable_thinking: Optional[bool] = None
    user_id: Optional[int] = None


class CategoriesListRead(SQLModel):
    """Slim shape for list/single-item reads — omits llm_api_key.

    Used by GET /categories/ and GET /categories/{id}, which any
    authenticated user can call; the raw LLM API key must never be
    exposed there. The full CategoriesRead (with llm_api_key) is only
    returned from the create/update endpoints, to the caller who just
    submitted that key.
    """

    id: int
    name: str
    description: str
    system_prompt: str
    whisper_prompt: Optional[str] = None
    llm_override_enabled: bool
    llm_model: Optional[str]
    llm_api_endpoint: Optional[str]
    llm_temperature: Optional[float]
    llm_max_tokens: Optional[int]
    llm_top_p: Optional[float] = None
    llm_frequency_penalty: Optional[float] = None
    llm_enable_thinking: Optional[bool] = None
    user_id: Optional[int] = None
