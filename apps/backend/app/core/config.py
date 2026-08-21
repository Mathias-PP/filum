from __future__ import annotations

import os
import secrets
from functools import lru_cache
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    app_name: str = "Filum API"
    app_version: str = "0.1.0"
    debug: bool = False

    database_url: str = "postgresql+asyncpg://filum:changeme@localhost:5432/filum_dev"
    database_pool_size: int = 5
    database_max_overflow: int = 10

    session_secret: str = ""
    master_encryption_key: str = ""

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"

    frontend_base_url: str = "http://localhost:5173"
    backend_base_url: str = "http://localhost:8000"
    api_v1_prefix: str = "/api/v1"

    cors_origins: list[str] = ["http://localhost:5173"]

    rate_limit_per_minute: int = 60

    wayback_api_key: str = ""

    # Point d'entrée LLM, au format OpenAI `/v1/chat/completions` (cf.
    # .docs/17-llm-strategy.md). Vide = couche LLM désactivée. Historiquement
    # le proxy LiteLLM ; peut désormais viser un provider directement, par
    # exemple `https://generativelanguage.googleapis.com/v1beta/openai`.
    litellm_base_url: str = ""
    litellm_master_key: str = ""

    # Les sept appels LLM nomment des alias de tâche (`biblio-parse`,
    # `excerpt-suggest`, `metadata-extract`) que seul LiteLLM sait résoudre.
    # Sans proxy, il faut dire quel modèle réel les honore : renseigner ce
    # champ court-circuite les alias (ADR-035). Vide = alias transmis tels
    # quels, donc mode proxy.
    llm_direct_model: str = ""

    # Modèles de repli, séparés par des virgules, essayés dans l'ordre quand le
    # précédent répond 429. Le quota gratuit de Gemini se compte par modèle et
    # par jour (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`, 20 appels) :
    # une fois épuisé sur un modèle, les autres répondent encore. Sans cette
    # liste, toute la couche LLM s'éteint pour la journée au vingtième appel.
    llm_direct_model_fallbacks: str = ""

    # Modèle d'embedding, appelé sur la même racine que le chat, au format
    # OpenAI `/embeddings`. Les vecteurs sont tronqués à 768 dimensions côté
    # backend (cf. `services/embeddings.py`). Changer ce nom périme les
    # vecteurs déjà calculés : la table les garde côte à côte, la bascule se
    # fait quand la nouvelle série est complète.
    embedding_model: str = "gemini-embedding-001"

    # GROBID (parsing structuré des références d'un PDF). Le Space officiel
    # kermitt2/grobid est PAUSED (2026-07) ; zfhxi/grobid est un duplicate
    # public réveillable. Les Spaces HF gratuits dorment (cold start ~2 min) :
    # tout échec ou timeout retombe sur le parseur regex local. Vide = off.
    grobid_base_url: str = "https://zfhxi-grobid.hf.space"

    duckdb_path: str = "/data/filum_analytics.duckdb"

    # --- Harness agent BYOK (chat + outils) --------------------------------
    # Boucle de l'agent : bornes dures contre les boucles infinies et les coûts.
    agent_max_tours: int = 24
    agent_max_turn_tokens: int = 8192
    # Recherche web dédiée (utilisée quand le provider courant n'expose pas de
    # grounding natif). `agent_web_search_provider` : tavily | exa | brave |
    # serper. Vide = recherche web désactivée pour l'agent.
    agent_web_search_provider: str = ""
    agent_web_search_api_key: str = ""

    # Mode découverte : clé serveur sponsorisée pour permettre d'essayer
    # l'agent sans configurer de provider. Désactivé par défaut.
    # Recommandation prod : DeepSeek (ToS commercial, ~0.27 $/M tokens).
    agent_discovery_enabled: bool = False
    agent_discovery_daily_quota_messages: int = 10
    agent_discovery_provider: str = "deepseek"
    agent_discovery_model: str = "deepseek-chat"
    agent_discovery_api_key: str = ""
    # Self-hosted uniquement : autorise localhost comme base_url de provider.
    # Ne jamais mettre a True sur le SaaS Philum (VM distante != loopback user).
    agent_allow_local_providers: bool = False

    @field_validator("database_url", mode="before")
    @classmethod
    def _coerce_async_driver(cls, value: str) -> str:
        if isinstance(value, str) and value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    def __init__(self, **data: Any):
        super().__init__(**data)
        self._validate_secrets()

    def _validate_secrets(self) -> None:
        """Fail-hard in production if critical secrets are missing.

        Previous behavior generated random secrets on the fly when env vars
        were empty. That hides misconfigurations: every Railway restart
        without proper env vars would invalidate every active session
        silently (new random `session_secret`) and rotate the key used to
        encrypt private keys at rest (new random `master_encryption_key`,
        which corrupts the ability to decrypt previously stored keys).

        We now:
          - Generate fresh secrets ONLY in dev/CI where it's safe.
          - Raise loudly in production with a clear remediation message.

        The "production" detection is conservative: if NEITHER `debug=True`
        NOR `CI=true` is set, we assume a deployment context (Railway, etc.)
        and require explicit secrets.
        """
        is_dev_or_ci = self.debug or os.environ.get("CI") == "true"
        missing = []
        if not self.session_secret:
            if is_dev_or_ci:
                self.session_secret = secrets.token_urlsafe(32)
            else:
                missing.append("session_secret")
        if not self.master_encryption_key:
            if is_dev_or_ci:
                self.master_encryption_key = secrets.token_hex(32)
            else:
                missing.append("master_encryption_key")

        if missing:
            raise RuntimeError(
                "Missing required production secrets: "
                + ", ".join(missing)
                + ". Set them in the deployment environment (Railway → Variables) "
                "or set `debug=true` / `CI=true` to allow ephemeral random generation "
                "(dev only). Generate with `openssl rand -hex 32`."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
