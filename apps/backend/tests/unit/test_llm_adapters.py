"""Tests unitaires des adaptateurs de protocole LLM."""

from __future__ import annotations

import json

from app.services.llm_adapters import (
    _messages_vers_anthropic,
    _parse_anthropic_blocking,
    _tools_vers_anthropic,
    format_chat_payload,
    protocole_pour,
    url_et_headers,
)


class TestProtocole:
    def test_anthropic_utilise_protocole_natif(self):
        assert protocole_pour("anthropic") == "anthropic"

    def test_openai_utilise_compat(self):
        assert protocole_pour("openai") == "openai"

    def test_gemini_utilise_compat(self):
        assert protocole_pour("gemini") == "openai"

    def test_inconnu_utilise_compat(self):
        assert protocole_pour("quelque_chose_inconnu") == "openai"


class TestUrlEtHeaders:
    def test_anthropic_va_sur_v1_messages(self):
        url, headers = url_et_headers("anthropic", "https://api.anthropic.com", "sk-ant-123")
        assert url == "https://api.anthropic.com/v1/messages"
        assert headers["x-api-key"] == "sk-ant-123"
        assert headers["anthropic-version"] == "2023-06-01"
        assert "Authorization" not in headers

    def test_openai_va_sur_chat_completions(self):
        url, headers = url_et_headers("openai", "https://api.openai.com", "sk-openai-123")
        assert "chat/completions" in url
        assert headers["Authorization"] == "Bearer sk-openai-123"
        assert "x-api-key" not in headers

    def test_base_url_avec_chemin_ne_repete_pas_v1(self):
        url, _ = url_et_headers(
            "gemini", "https://generativelanguage.googleapis.com/v1beta/openai", "key"
        )
        assert url.endswith("/chat/completions")
        assert "v1/v1" not in url


class TestMessagesVersAnthropic:
    def test_extrait_system_en_champ_dedie(self):
        messages = [
            {"role": "system", "content": "Tu es un assistant."},
            {"role": "user", "content": "Bonjour."},
        ]
        system_text, anthropic_msgs = _messages_vers_anthropic(messages)
        assert system_text == "Tu es un assistant."
        assert not any(m.get("role") == "system" for m in anthropic_msgs)
        assert anthropic_msgs[0]["role"] == "user"

    def test_outil_converti_en_tool_use(self):
        messages = [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_xyz",
                        "type": "function",
                        "function": {"name": "web_search", "arguments": '{"query": "test"}'},
                    }
                ],
            }
        ]
        _, anthropic_msgs = _messages_vers_anthropic(messages)
        assert len(anthropic_msgs) == 1
        block = anthropic_msgs[0]["content"][0]
        assert block["type"] == "tool_use"
        assert block["name"] == "web_search"
        assert block["input"] == {"query": "test"}
        assert block["id"] == "call_xyz"

    def test_messages_tool_regroupes_en_user(self):
        messages = [
            {
                "role": "tool",
                "tool_call_id": "call_1",
                "name": "web_search",
                "content": '{"ok":true}',
            },
            {
                "role": "tool",
                "tool_call_id": "call_2",
                "name": "get_card",
                "content": '{"id":"abc"}',
            },
        ]
        _, anthropic_msgs = _messages_vers_anthropic(messages)
        assert len(anthropic_msgs) == 1
        assert anthropic_msgs[0]["role"] == "user"
        assert len(anthropic_msgs[0]["content"]) == 2
        assert anthropic_msgs[0]["content"][0]["type"] == "tool_result"
        assert anthropic_msgs[0]["content"][0]["tool_use_id"] == "call_1"

    def test_plusieurs_system_joints(self):
        messages = [
            {"role": "system", "content": "Premiere partie."},
            {"role": "system", "content": "Deuxieme partie."},
            {"role": "user", "content": "Question."},
        ]
        system_text, _ = _messages_vers_anthropic(messages)
        assert "Premiere partie." in system_text
        assert "Deuxieme partie." in system_text


class TestToolsVersAnthropic:
    def test_convertit_function_en_tool_anthropic(self):
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Recherche web",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                },
            }
        ]
        result = _tools_vers_anthropic(tools)
        assert len(result) == 1
        assert result[0]["name"] == "web_search"
        assert result[0]["description"] == "Recherche web"
        assert result[0]["input_schema"]["type"] == "object"
        assert "function" not in result[0]
        assert "type" not in result[0]


class TestParseAnthropicBlocking:
    def test_convertit_text_en_message_assistant(self):
        data = {
            "content": [{"type": "text", "text": "Bonjour !"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 3},
        }
        result = _parse_anthropic_blocking(data)
        assert not isinstance(result, str)
        message, finish_reason, usage = result
        assert message["role"] == "assistant"
        assert message["content"] == "Bonjour !"
        assert finish_reason == "stop"
        assert usage["prompt_tokens"] == 10
        assert usage["completion_tokens"] == 3

    def test_convertit_tool_calls(self):
        data = {
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_01",
                    "name": "web_search",
                    "input": {"query": "test"},
                }
            ],
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 5, "output_tokens": 2},
        }
        result = _parse_anthropic_blocking(data)
        assert not isinstance(result, str)
        message, finish_reason, _ = result
        assert finish_reason == "tool_calls"
        assert len(message["tool_calls"]) == 1
        tc = message["tool_calls"][0]
        assert tc["id"] == "toolu_01"
        assert tc["function"]["name"] == "web_search"
        assert json.loads(tc["function"]["arguments"]) == {"query": "test"}

    def test_stop_reason_max_tokens_devient_length(self):
        data = {
            "content": [{"type": "text", "text": "..."}],
            "stop_reason": "max_tokens",
            "usage": {},
        }
        _, finish_reason, _ = _parse_anthropic_blocking(data)  # type: ignore[misc]
        assert finish_reason == "length"


class TestFormatChatPayload:
    def test_anthropic_pas_de_stream_key_si_false(self):
        payload = format_chat_payload("anthropic", "claude-opus-4", [], [], 1024, stream=False)
        assert "stream" not in payload

    def test_anthropic_system_absent_si_pas_de_system_message(self):
        payload = format_chat_payload("anthropic", "claude-opus-4", [], [], 1024)
        assert "system" not in payload

    def test_openai_conserve_messages_tels_quels(self):
        messages = [{"role": "user", "content": "Hello"}]
        payload = format_chat_payload("openai", "gpt-4o", messages, [], 1024)
        assert payload["messages"] is messages
