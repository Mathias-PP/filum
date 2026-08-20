from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProviderKind(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"
    GEMINI = "gemini"
    CUSTOM = "custom"


#: Racines d'API par défaut, résolues à la création et stockées en base
#: (colonne NOT NULL). Gemini expose sa surface OpenAI sous `/v1beta/openai`.
PROVIDER_DEFAULT_BASE_URLS: dict[str, str] = {
    "openai": "https://api.openai.com",
    "anthropic": "https://api.anthropic.com",
    "deepseek": "https://api.deepseek.com",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
}


def _api_key_masked(api_key: str) -> str:
    """Forme affichable d'une clé (`sk-…1234`). Ne renvoie jamais la clé en clair."""
    if len(api_key) <= 8:
        return "…"
    return f"{api_key[:3]}…{api_key[-4:]}"


def _base_url_normalise(v: str) -> str:
    """Nettoyage syntaxique d'une base_url : http(s), hôte présent, sans slash final.

    L'assainissement complet (résolution DNS, blocage des adresses privées) est
    fait dans le service au moment d'enregistrer une base_url fournie par
    l'utilisateur : il exige du réseau, on ne le fait pas à la validation.
    """
    v = v.strip().rstrip("/")
    if not v:
        raise ValueError("base_url ne peut pas être vide")
    if not v.startswith(("http://", "https://")):
        raise ValueError("base_url doit commencer par http:// ou https://")
    if "://" not in v or len(v.split("://", 1)[1]) == 0:
        raise ValueError("base_url doit avoir un hôte")
    return v


class AgentProviderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: ProviderKind
    display_name: str | None = Field(default=None, max_length=80)
    base_url: str | None = Field(default=None, max_length=300)
    model: str = Field(min_length=1, max_length=120)
    api_key: str = Field(min_length=1, max_length=500)
    is_default: bool = False

    @field_validator("api_key")
    @classmethod
    def _api_key_strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("api_key ne peut pas être vide.")
        return v

    @field_validator("model")
    @classmethod
    def _model_strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("model ne peut pas être vide.")
        return v

    @field_validator("base_url")
    @classmethod
    def _base_url_clean(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return _base_url_normalise(v)


class AgentProviderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, max_length=80)
    base_url: str | None = Field(default=None, max_length=300)
    model: str | None = Field(default=None, min_length=1, max_length=120)
    api_key: str | None = Field(default=None, min_length=1, max_length=500)
    is_default: bool | None = None

    @field_validator("api_key")
    @classmethod
    def _api_key_strip(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("api_key ne peut pas être vide.")
        return v

    @field_validator("model")
    @classmethod
    def _model_strip(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("model ne peut pas être vide.")
        return v

    @field_validator("base_url")
    @classmethod
    def _base_url_clean(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return _base_url_normalise(v)


class AgentProviderRead(BaseModel):
    """Sortie : jamais la clé, toujours sa forme masquée."""

    id: UUID
    provider: ProviderKind
    display_name: str
    base_url: str
    model: str
    is_default: bool
    api_key_masked: str
    created_at: datetime | None
    updated_at: datetime | None


class AgentProviderTestResult(BaseModel):
    """Résultat du test de clé, avec un message actionnable par statut."""

    ok: bool
    http_status: int | None = None
    model_resolved: str
    url: str
    message: str
