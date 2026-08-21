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
    GROQ = "groq"
    OPENROUTER = "openrouter"
    MISTRAL = "mistral"
    CEREBRAS = "cerebras"
    CUSTOM = "custom"


#: Racines d'API par défaut, résolues à la création et stockées en base
#: (colonne NOT NULL). Gemini expose sa surface OpenAI sous `/v1beta/openai`.
PROVIDER_DEFAULT_BASE_URLS: dict[str, str] = {
    "openai": "https://api.openai.com",
    "anthropic": "https://api.anthropic.com",
    "deepseek": "https://api.deepseek.com",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "mistral": "https://api.mistral.ai/v1",
    "cerebras": "https://api.cerebras.ai/v1",
}

#: Filet de securite quand le fournisseur ne repond pas sur ``/models``. Ce n'est
#: PAS la source de verite : la liste vivante vient de ``lister_modeles()``, qui
#: interroge le compte de l'utilisateur. Verifie le 2026-08-21.
MODELES_SUGGERES: dict[str, list[str]] = {
    "openai": ["gpt-5.6-luna", "gpt-5.6-terra"],
    "anthropic": ["claude-opus-4-7", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"],
    "deepseek": ["deepseek-chat", "deepseek-reasoner"],
    "gemini": ["gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.1-pro"],
    "groq": [],
    "openrouter": [],
    "mistral": [],
    "cerebras": [],
    "custom": [],
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
    """Résultat du test de clé, avec un message actionnable par statut.

    ``provider_message`` porte le texte brut renvoyé par le fournisseur. C'est
    souvent la seule information exploitable de toute la chaine : Gemini y nomme
    le modele de remplacement, OpenAI y distingue un credit epuise d'une limite
    de debit. Ne jamais le remplacer par une reformulation.
    """

    ok: bool
    http_status: int | None = None
    model_resolved: str
    url: str
    message: str
    provider_message: str | None = None
    latency_ms: int | None = None
    # Sur un test reussi, la liste des modeles du compte est chargee en meme
    # temps : le dropdown est chaud et le cache serveur (15 min) est populé
    # sans qu'un second appel soit necessaire depuis le front.
    models: list[str] | None = None
