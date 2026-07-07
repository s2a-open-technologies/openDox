"""openDox - Medical transcription platform
Copyright (C) 2025  Christopher Abanilla <christopher.abanilla@gmx.de>

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


class LlmSettingsModel(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    # LLM / Ollama / OpenAI-compatible API Settings
    llm_api_endpoint: Optional[str] = Field(default="http://localhost:11434/v1")
    llm_api_key: Optional[str] = Field(default=None)
    llm_model: Optional[str] = Field(default="medgemma-4b-it:Q4_K_M")
    llm_temperature: float = Field(default=0.2)
    llm_max_tokens: int = Field(default=2048)

    # Optional dedicated model for near-live chunk correction.
    # Leave empty to use llm_model (same model for both correction and summary).
    correction_model: Optional[str] = Field(default=None)
    
    # Sanitizer settings
    sanitizer_enabled: Optional[bool] = Field(default=False)
    sanitizer_endpoint: Optional[str] = Field(default=None)
    sanitizer_api_key: Optional[str] = Field(default=None)
