"""
llm/gemini_provider.py — Gemini implementation of LLMProvider.

Uses google-genai SDK. Tool schemas arrive already in Gemini format
(declared in tools.py) so no translation needed.

Get a free API key: https://aistudio.google.com/app/apikey
"""

import os
import json
from google import genai
from google.genai import types

from .base_provider import LLMProvider, LLMResponse, ToolCall


class GeminiProvider(LLMProvider):
    def __init__(self, model: str = "gemini-3.1-flash-lite"):
        self._model = model
        self._client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

    @property
    def name(self) -> str:
        return f"gemini/{self._model}"

    def complete(
        self,
        messages: list[dict],
        system_prompt: str,
        tool_schemas: list[dict],
    ) -> LLMResponse:
        # Build Gemini tool declarations directly from schemas
        declarations = [
            types.FunctionDeclaration(
                name=s["name"],
                description=s["description"],
                parameters=s["parameters"],
            )
            for s in tool_schemas
        ]

        response = self._client.models.generate_content(
            model=self._model,
            contents=_to_contents(messages),
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                tools=[types.Tool(function_declarations=declarations)],
                tool_config=types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(mode="AUTO")
                ),
            ),
        )

        text = None
        tool_calls = []
        for part in response.candidates[0].content.parts:
            if getattr(part, "text", None):
                text = (text or "") + part.text
            if getattr(part, "function_call", None):
                fc = part.function_call
                tool_calls.append(ToolCall(id=fc.name, name=fc.name, input=dict(fc.args)))

        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            stop_reason="tool_use" if tool_calls else "end_turn",
        )


def _to_contents(messages: list[dict]) -> list[types.Content]:
    contents = []
    for msg in messages:
        role = msg["role"]
        if role == "user":
            contents.append(types.Content(role="user", parts=[types.Part(text=msg["content"])]))
        elif role == "assistant":
            contents.append(types.Content(role="model", parts=[types.Part(text=msg["content"] or "")]))
        elif role == "tool":
            contents.append(types.Content(
                role="user",
                parts=[types.Part(function_response=types.FunctionResponse(
                    name=msg["name"],
                    response={"result": json.loads(msg["content"])},
                ))]
            ))
    return contents
