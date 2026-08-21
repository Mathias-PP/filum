"""Adaptateurs de protocole pour les providers BYOK.

Deux protocoles : OpenAI-compat (tous les providers sauf Anthropic) et
Anthropic natif (/v1/messages). Le reste du code (boucle, tester) travaille
toujours avec des structures OpenAI-like en interne ; la conversion est
confinee ici.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

import httpx

_PROTOCOLE: dict[str, str] = {
    "anthropic": "anthropic",
    "openai": "openai",
    "deepseek": "openai",
    "gemini": "openai",
    "groq": "openai",
    "openrouter": "openai",
    "mistral": "openai",
    "cerebras": "openai",
    "custom": "openai",
}


def protocole_pour(kind: str) -> str:
    return _PROTOCOLE.get(kind, "openai")


# ---------------------------------------------------------------------------
# URL + headers selon le protocole
# ---------------------------------------------------------------------------


def _url_openai(base_url: str) -> str:
    base = base_url.rstrip("/")
    chemin = urlparse(base).path
    return f"{base}/chat/completions" if chemin else f"{base}/v1/chat/completions"


def url_et_headers(kind: str, base_url: str, api_key: str) -> tuple[str, dict[str, str]]:
    """URL de l'endpoint de chat et headers d'authentification."""
    if protocole_pour(kind) == "anthropic":
        return (
            f"{base_url.rstrip('/')}/v1/messages",
            {"x-api-key": api_key, "anthropic-version": "2023-06-01"},
        )
    return _url_openai(base_url), {"Authorization": f"Bearer {api_key}"}


# ---------------------------------------------------------------------------
# Construction du payload de chat
# ---------------------------------------------------------------------------


def _messages_vers_anthropic(
    messages: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    """Convertit les messages OpenAI-like vers le format Anthropic.

    Retourne (system_text, anthropic_messages). Plusieurs messages system sont
    joints. Les messages tool sont regroupes en un seul bloc user (Anthropic
    exige l'alternance user/assistant). Les tool_calls du format assistant
    OpenAI sont convertis en blocs tool_use.
    """
    system_parts: list[str] = []
    anthropic_messages: list[dict[str, Any]] = []
    pending_tool_results: list[dict[str, Any]] = []

    for msg in messages:
        role = msg.get("role")

        if role == "system":
            content = msg.get("content") or ""
            if isinstance(content, str) and content:
                system_parts.append(content)
            continue

        if role == "tool":
            pending_tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": msg.get("tool_call_id") or "",
                    "content": msg.get("content") or "",
                }
            )
            continue

        if pending_tool_results:
            anthropic_messages.append({"role": "user", "content": pending_tool_results})
            pending_tool_results = []

        if role == "user":
            anthropic_messages.append({"role": "user", "content": msg.get("content") or ""})

        elif role == "assistant":
            content_parts: list[dict[str, Any]] = []
            texte = msg.get("content") or ""
            if isinstance(texte, str) and texte:
                content_parts.append({"type": "text", "text": texte})
            for tc in msg.get("tool_calls") or []:
                if not isinstance(tc, dict):
                    continue
                fn = tc.get("function") or {}
                try:
                    input_dict: Any = json.loads(fn.get("arguments") or "{}")
                    if not isinstance(input_dict, dict):
                        input_dict = {}
                except json.JSONDecodeError:
                    input_dict = {}
                content_parts.append(
                    {
                        "type": "tool_use",
                        "id": tc.get("id") or f"toolu_{len(content_parts)}",
                        "name": fn.get("name") or "",
                        "input": input_dict,
                    }
                )
            anthropic_messages.append(
                {
                    "role": "assistant",
                    "content": content_parts if content_parts else [{"type": "text", "text": ""}],
                }
            )

    if pending_tool_results:
        anthropic_messages.append({"role": "user", "content": pending_tool_results})

    return "\n\n".join(system_parts), anthropic_messages


def _tools_vers_anthropic(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convertit les tools OpenAI-like vers le format Anthropic."""
    result = []
    for tool in tools:
        if tool.get("type") == "function":
            fn = tool.get("function") or {}
            result.append(
                {
                    "name": fn.get("name") or "",
                    "description": fn.get("description") or "",
                    "input_schema": fn.get("parameters") or {"type": "object", "properties": {}},
                }
            )
    return result


def format_chat_payload(
    kind: str,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    max_tokens: int,
    *,
    stream: bool = True,
) -> dict[str, Any]:
    """Le payload du POST de chat dans le bon format pour ce provider."""
    if protocole_pour(kind) == "anthropic":
        system_text, anthropic_messages = _messages_vers_anthropic(messages)
        anthropic_tools = _tools_vers_anthropic(tools)
        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": anthropic_messages,
            "temperature": 0,
        }
        if system_text:
            payload["system"] = system_text
        if anthropic_tools:
            payload["tools"] = anthropic_tools
        if stream:
            payload["stream"] = True
        return payload

    # OpenAI-compat
    return {
        "model": model,
        "messages": messages,
        "tools": tools,
        "max_tokens": max_tokens,
        "temperature": 0,
        "stream": stream,
    }


# ---------------------------------------------------------------------------
# Parsing des reponses bloquantes (HTTP 200, body JSON)
# ---------------------------------------------------------------------------


def parse_blocking_response(
    kind: str,
    data: dict[str, Any],
) -> tuple[dict[str, Any], str | None, dict[str, Any]] | str:
    """Convertit un corps JSON de reponse en (message_openai_like, finish_reason, usage)."""
    if protocole_pour(kind) == "anthropic":
        return _parse_anthropic_blocking(data)
    return _parse_openai_blocking(data)


def _parse_openai_blocking(
    data: dict[str, Any],
) -> tuple[dict[str, Any], str | None, dict[str, Any]] | str:
    try:
        choice = data["choices"][0]
        message = choice["message"]
    except (KeyError, IndexError, TypeError) as exc:
        return f"Reponse du provider inattendue (pas de choices) : {exc}"
    finish_reason = choice.get("finish_reason") if isinstance(choice, dict) else None
    usage = data.get("usage") or {}
    return message, finish_reason, usage


def _parse_anthropic_blocking(
    data: dict[str, Any],
) -> tuple[dict[str, Any], str | None, dict[str, Any]] | str:
    """Anthropic /v1/messages → format OpenAI-like."""
    content_blocks = data.get("content") or []
    text_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []

    for block in content_blocks:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            text_parts.append(block.get("text") or "")
        elif block.get("type") == "tool_use":
            tool_calls.append(
                {
                    "id": block.get("id") or "",
                    "type": "function",
                    "function": {
                        "name": block.get("name") or "",
                        "arguments": json.dumps(block.get("input") or {}),
                    },
                }
            )

    text = "".join(text_parts)
    message: dict[str, Any] = {"role": "assistant", "content": text or None}
    if tool_calls:
        message["tool_calls"] = tool_calls

    stop_reason = data.get("stop_reason")
    finish_reason_map = {"end_turn": "stop", "tool_use": "tool_calls", "max_tokens": "length"}
    finish_reason = finish_reason_map.get(stop_reason) if stop_reason else None

    usage_raw = data.get("usage") or {}
    usage = {
        "prompt_tokens": usage_raw.get("input_tokens") or 0,
        "completion_tokens": usage_raw.get("output_tokens") or 0,
    }
    return message, finish_reason, usage


# ---------------------------------------------------------------------------
# Parsing des flux SSE Anthropic
# ---------------------------------------------------------------------------


async def parse_sse_stream_anthropic(
    response: httpx.Response,
    on_delta: Any,
) -> tuple[dict[str, Any], str | None, dict[str, Any]] | str:
    """Lit un flux SSE Anthropic et rend (message_openai_like, finish_reason, usage).

    Anthropic emet des evenements types (content_block_start, content_block_delta,
    message_delta). On reconstruit le message complet et on emet chaque delta
    texte via on_delta.
    """
    text_parts: list[str] = []
    tool_calls_par_index: dict[int, dict[str, Any]] = {}
    finish_reason: str | None = None
    usage: dict[str, Any] = {}

    try:
        async for ligne in response.aiter_lines():
            ligne = ligne.strip()
            if not ligne:
                continue
            if ligne.startswith("event: "):
                continue
            if not ligne.startswith("data: "):
                continue
            data_str = ligne[6:]
            if data_str == "[DONE]":
                break
            try:
                chunk = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            chunk_type = chunk.get("type") if isinstance(chunk, dict) else None
            if chunk_type == "message_stop":
                break

            if chunk_type == "message_delta":
                delta = chunk.get("delta") or {}
                stop_reason = delta.get("stop_reason")
                if stop_reason:
                    finish_reason_map = {
                        "end_turn": "stop",
                        "tool_use": "tool_calls",
                        "max_tokens": "length",
                    }
                    finish_reason = finish_reason_map.get(stop_reason, stop_reason)
                usage_delta = chunk.get("usage") or {}
                if usage_delta:
                    usage = {
                        "prompt_tokens": usage.get("prompt_tokens") or 0,
                        "completion_tokens": usage_delta.get("output_tokens") or 0,
                    }
                continue

            if chunk_type == "message_start":
                msg = chunk.get("message") or {}
                usage_raw = msg.get("usage") or {}
                if usage_raw:
                    usage = {
                        "prompt_tokens": usage_raw.get("input_tokens") or 0,
                        "completion_tokens": usage_raw.get("output_tokens") or 0,
                    }
                continue

            if chunk_type == "content_block_start":
                idx = chunk.get("index", 0)
                block = chunk.get("content_block") or {}
                if block.get("type") == "tool_use":
                    tool_calls_par_index[idx] = {
                        "id": block.get("id") or "",
                        "type": "function",
                        "function": {"name": block.get("name") or "", "arguments": ""},
                    }
                continue

            if chunk_type == "content_block_delta":
                idx = chunk.get("index", 0)
                delta = chunk.get("delta") or {}
                delta_type = delta.get("type")
                if delta_type == "text_delta":
                    text = delta.get("text") or ""
                    if text:
                        text_parts.append(text)
                        if on_delta is not None:
                            await on_delta(text)
                elif delta_type == "input_json_delta":
                    partial = delta.get("partial_json") or ""
                    if idx in tool_calls_par_index:
                        tool_calls_par_index[idx]["function"]["arguments"] += partial
                continue

    except httpx.StreamError as exc:
        return f"Erreur reseau vers le provider : {exc}"

    text = "".join(text_parts)
    tool_calls = [tool_calls_par_index[i] for i in sorted(tool_calls_par_index)]
    message: dict[str, Any] = {"role": "assistant", "content": text or None}
    if tool_calls:
        message["tool_calls"] = tool_calls

    return message, finish_reason, usage
