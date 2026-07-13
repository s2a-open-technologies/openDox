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

import re

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from backend.components.services.settings_service import get_llm_settings

# No default timeout exists on ChatOpenAI/httpx — without one, a hung or
# very slow local model (e.g. a large model with no GPU) leaves the
# background task stuck at status="processing_llm" forever, indistinguishable
# from a genuine hang. 5 minutes is generous enough for a large local model
# on modest hardware while still guaranteeing the task eventually errors out.
LLM_REQUEST_TIMEOUT_SECONDS = 300

_THINKING_STARTERS = re.compile(
    r"^(thought\b|<think|<thinking|<thought|here\'s my|let me|i need to|i will|"
    r"understand\b|the user\b|my task\b|step \d|first,|next,|now,)",
    re.IGNORECASE,
)


def _strip_thinking(text: str) -> str:
    """Remove reasoning blocks that thinking-capable models (MedGemma, Qwen3, etc.) emit."""
    # XML-style tags
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(
        r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL | re.IGNORECASE
    )
    text = re.sub(r"<thought>.*?</thought>", "", text, flags=re.DOTALL | re.IGNORECASE)

    # Gemma/MedGemma: "thought <multi-paragraph reasoning>\n\nActual answer"
    # Split into paragraphs; drop leading ones that look like thinking, keep the rest.
    stripped = text.strip()
    if re.match(r"^thought\s", stripped, re.IGNORECASE):
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", stripped) if p.strip()]
        actual = [p for p in paragraphs if not _THINKING_STARTERS.match(p)]
        text = "\n\n".join(actual) if actual else paragraphs[-1] if paragraphs else text

    return text.strip()


class OllamaModel:
    def __init__(
        self,
        model_name=None,
        base_url=None,
        api_key=None,
        temperature=None,
        max_tokens=None,
    ):
        """Initializes the OllamaModel with DB settings or overrides."""
        try:
            db_settings = get_llm_settings()  # Dedicated LLM settings
        except Exception:
            db_settings = None

        self.model = model_name or (
            db_settings.llm_model
            if db_settings and db_settings.llm_model
            else "medgemma-4b-it:Q4_K_M"
        )
        self.base_url = base_url or (
            db_settings.llm_api_endpoint
            if db_settings and db_settings.llm_api_endpoint
            else "http://localhost:11434/v1"
        )
        self.api_key = api_key or (
            db_settings.llm_api_key
            if db_settings and db_settings.llm_api_key
            else "loc-123"
        )
        self.temperature = (
            temperature
            if temperature is not None
            else (db_settings.llm_temperature if db_settings else 0.2)
        )
        self.max_tokens = (
            max_tokens
            if max_tokens is not None
            else (db_settings.llm_max_tokens if db_settings else 2048)
        )

        self.client = ChatOpenAI(
            model=self.model,
            base_url=self.base_url,
            api_key=self.api_key,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            top_p=0.9,
            frequency_penalty=0.3,
            timeout=LLM_REQUEST_TIMEOUT_SECONDS,
        )

    def reload(self):
        """Reload settings from database."""
        try:
            db_settings = get_llm_settings()
            if db_settings:
                self.model = db_settings.llm_model
                self.base_url = db_settings.llm_api_endpoint
                self.api_key = db_settings.llm_api_key
                self.temperature = db_settings.llm_temperature
                self.max_tokens = db_settings.llm_max_tokens

                self.client = ChatOpenAI(
                    model=self.model,
                    base_url=self.base_url,
                    api_key=self.api_key,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    top_p=0.9,
                    frequency_penalty=0.3,
                    timeout=LLM_REQUEST_TIMEOUT_SECONDS,
                    model_kwargs={"think": False},
                )
        except Exception:
            pass

    def get_system_prompt(self) -> str:
        """Returns a default system prompt for the Ollama model."""
        prompt = """
            You are a powerfull grammar und summarization specialist.
            There is a whipser transcription of a german audio file.
            Your task is to correct the grammar and summarize the content in a concise manner.
            Provide the output in well-structured german sentences.
            Keep the meaning of the original transcription intact.
            It is very important to only correct grammar and not change any words or meaning.
            Use the following format:
            
            --- Original Transcription ---
            {message}
            --- Original Transcription End ---  
            
            --- Corrected and Summarized Transcription ---
            
            Do not use more words than necessary.
            Do not add any explanations or additional information.
            Do not mention that you are an AI model.
            Do not apologize.
            Do not self-reference.
            Do not use emoticons or special characters.            
            """

        return prompt

    def generate_response(
        self, message: str, custom_system_prompt: str | None = None
    ) -> str:
        prompt = (
            custom_system_prompt if custom_system_prompt else self.get_system_prompt()
        )
        # Suppress thinking output for all models — harmless for non-thinking models
        prompt = (
            prompt.rstrip()
            + "\nDo not output your reasoning or thinking process. Output only the final result."
        )

        template = ChatPromptTemplate.from_messages(
            [("system", prompt), ("user", "{message}")]
        )

        chain = template | self.client
        response = chain.invoke({"message": message})

        result = _strip_thinking(response.content)
        if not result.strip():
            raise ValueError(
                "LLM response was empty after stripping reasoning/thinking "
                "blocks — the model likely got stuck reasoning without "
                "producing an answer."
            )
        return result
