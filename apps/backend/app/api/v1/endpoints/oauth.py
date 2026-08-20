"""Endpoints OAuth 2.1 pour l'auth MCP standard.

Implemente le sous-ensemble strictement necessaire pour qu'un client MCP
(Claude Code, Cursor, ChatGPT desktop, Zed, etc.) puisse se connecter sans
que l'utilisateur ait a coller un token a la main :

- `POST /oauth/register` : DCR (RFC 7591). Le client s'enregistre lui-meme,
  recoit un client_id, n'a besoin de rien de plus (public via PKCE).
- `GET /oauth/authorize` : ouvre la page de consentement dans le navigateur.
  Si l'user n'est pas logue a Philum, redirige vers Google OAuth puis revient
  ici. Sinon rend une page HTML minimaliste avec le nom du client et le
  bouton « Autoriser ».
- `POST /oauth/consent` : recoit le POST de la page consent, cree le code
  d'autorisation, redirige vers `redirect_uri` du client avec ?code=&state=.
- `POST /oauth/token` : echange le code contre un access token JWT (avec
  PKCE verify).

La page consent est intentionnellement minimale et servie inline plutot que
par le frontend Vercel : sans dependance externe, l'auth marche meme si le
frontend est en panne.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_auth_service, get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.oauth import (
    ClientRegistrationRequest,
    ClientRegistrationResponse,
    TokenResponse,
)
from app.services.auth import AuthService
from app.services.oauth import (
    create_authorization_code,
    exchange_code_for_token,
    get_client,
    register_client,
)

router = APIRouter(tags=["oauth"])


@router.post(
    "/oauth/register",
    response_model=ClientRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def oauth_register(
    body: ClientRegistrationRequest,
    db: AsyncSession = Depends(get_db),
):
    """Dynamic Client Registration (RFC 7591). Aucune auth requise.

    C'est ce qui distingue OAuth 2.1 pour MCP de l'OAuth classique : chaque
    client s'enregistre lui-meme au moment de sa premiere connexion, l'user
    n'a jamais a copier un client_id.
    """
    try:
        resp = await register_client(
            db,
            redirect_uris=body.redirect_uris,
            client_name=body.client_name,
            token_endpoint_auth_method=body.token_endpoint_auth_method,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_client_metadata", "error_description": str(exc)},
        ) from exc
    return resp


@router.get("/oauth/authorize")
async def oauth_authorize(
    request: Request,
    response_type: str,
    client_id: str,
    redirect_uri: str,
    code_challenge: str,
    code_challenge_method: str = "S256",
    state: str | None = None,
    scope: str | None = None,
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Point d'entree du flow d'autorisation.

    Si l'user n'est pas connecte a Philum, redirige vers Google OAuth avec un
    `state` qui memorise la requete originale ; le callback Google reviendra
    ici avec la session posee. Sinon rend une page HTML de consentement.
    """
    if response_type != "code":
        raise HTTPException(400, {"error": "unsupported_response_type"})
    if code_challenge_method != "S256":
        raise HTTPException(
            400, {"error": "invalid_request", "error_description": "PKCE S256 requis"}
        )

    client = await get_client(db, client_id)
    if client is None:
        raise HTTPException(400, {"error": "invalid_client"})
    if redirect_uri not in client.redirect_uris:
        raise HTTPException(
            400, {"error": "invalid_request", "error_description": "redirect_uri non autorisee"}
        )

    user = await auth_service.get_current_user(request)
    if user is None:
        # Redirige vers Google OAuth. Le state Google porte la totalite des
        # parametres OAuth de MCP pour qu'on revienne ici a la fin.
        original_query = urlencode(
            {
                "response_type": response_type,
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "code_challenge": code_challenge,
                "code_challenge_method": code_challenge_method,
                **({"state": state} if state else {}),
                **({"scope": scope} if scope else {}),
            }
        )
        return_to = f"/api/v1/oauth/authorize?{original_query}"
        login_url = f"/api/v1/auth/google/login?return_to={return_to}"
        return RedirectResponse(url=login_url, status_code=302)

    # Page consent minimaliste.
    client_display = client.client_name or client_id
    return HTMLResponse(
        f"""<!doctype html>
<html lang="fr">
<head><meta charset="utf-8"><title>Autoriser {client_display} - Philum</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 500px; margin: 4rem auto; padding: 0 1rem; color: #1a1a1a; }}
h1 {{ font-size: 1.4rem; font-weight: 500; }}
.card {{ border: 1px solid #ddd; border-radius: 8px; padding: 1.5rem; margin: 1.5rem 0; }}
.user {{ color: #666; font-size: 0.9rem; }}
button {{ background: #1a1a1a; color: white; border: none; padding: 0.7rem 1.4rem; border-radius: 6px; cursor: pointer; font-size: 1rem; }}
button:hover {{ opacity: 0.9; }}
.deny {{ background: white; color: #666; border: 1px solid #ddd; margin-left: 0.5rem; }}
.perms {{ color: #444; font-size: 0.95rem; line-height: 1.5; }}
</style></head>
<body>
<h1>Autoriser l'acces a Philum</h1>
<div class="card">
<p><strong>{client_display}</strong> demande l'acces a votre compte Philum.</p>
<p class="user">Compte : <strong>{user.username}</strong> ({user.email})</p>
<p class="perms">Cette application pourra :</p>
<ul class="perms">
<li>Voir et creer vos fiches, sources et extraits</li>
<li>Voir vos citations entrantes</li>
<li>Publier des fiches en votre nom</li>
</ul>
</div>
<form method="post" action="/api/v1/oauth/consent">
<input type="hidden" name="client_id" value="{client_id}">
<input type="hidden" name="redirect_uri" value="{redirect_uri}">
<input type="hidden" name="code_challenge" value="{code_challenge}">
<input type="hidden" name="code_challenge_method" value="{code_challenge_method}">
<input type="hidden" name="state" value="{state or ""}">
<input type="hidden" name="scope" value="{scope or ""}">
<button type="submit" name="decision" value="allow">Autoriser</button>
<button type="submit" name="decision" value="deny" class="deny">Refuser</button>
</form>
</body></html>"""
    )


@router.post("/oauth/consent")
async def oauth_consent(
    decision: str = Form(...),
    client_id: str = Form(...),
    redirect_uri: str = Form(...),
    code_challenge: str = Form(...),
    code_challenge_method: str = Form("S256"),
    state: str = Form(""),
    scope: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Recoit le POST de la page consent, cree le code et redirige."""
    client = await get_client(db, client_id)
    if client is None:
        raise HTTPException(400, {"error": "invalid_client"})

    if decision != "allow":
        # RFC 6749 § 4.1.2.1 : renvoyer l'erreur au client via redirect.
        denied: dict[str, Any] = {"error": "access_denied"}
        if state:
            denied["state"] = state
        return RedirectResponse(url=f"{redirect_uri}?{urlencode(denied)}", status_code=302)

    try:
        code = await create_authorization_code(
            db,
            client=client,
            user_id=current_user.id,
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            scope=scope or None,
        )
    except ValueError as exc:
        raise HTTPException(
            400, {"error": "invalid_request", "error_description": str(exc)}
        ) from exc

    params: dict[str, Any] = {"code": code}
    if state:
        params["state"] = state
    return RedirectResponse(url=f"{redirect_uri}?{urlencode(params)}", status_code=302)


@router.post("/oauth/token", response_model=TokenResponse)
async def oauth_token(
    grant_type: str = Form(...),
    code: str = Form(...),
    redirect_uri: str = Form(...),
    client_id: str = Form(...),
    code_verifier: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Echange un code d'autorisation contre un access token JWT.

    Sans auth : le client public est identifie par `client_id`, l'authenticite
    du porteur du code par PKCE (`code_verifier`).
    """
    if grant_type != "authorization_code":
        raise HTTPException(400, {"error": "unsupported_grant_type"})

    try:
        result = await exchange_code_for_token(
            db,
            code=code,
            client_id=client_id,
            redirect_uri=redirect_uri,
            code_verifier=code_verifier,
        )
    except ValueError as exc:
        raise HTTPException(400, {"error": "invalid_grant", "error_description": str(exc)}) from exc

    return result


# --- Metadata endpoints (RFC 8414, RFC 9728) --------------------------------
#
# Servis a la racine du domaine, pas sous /api/v1, pour respecter la spec.
# Ces routes sont ajoutees separement dans main.py (au niveau de FastAPI(),
# pas d'un router prefixe).


def _base_url(request: Request) -> str:
    """L'URL publique du serveur, sans slash final. Utilise pour construire
    les endpoints dans les metadata OAuth.

    Force `https` sauf pour localhost/127.0.0.1 : les clients OAuth 2.1
    refusent un issuer non-HTTPS (specs, RFC 8414 § 2). Ceinture et bretelles
    au cas ou `--proxy-headers` ne transmettrait pas correctement le scheme
    depuis Caddy (mesure sur prod le 2026-08-18 : issuer sortait en `http`).
    """
    scheme = request.url.scheme
    host = request.url.netloc
    if scheme == "http" and not (host.startswith("localhost") or host.startswith("127.0.0.1")):
        scheme = "https"
    return f"{scheme}://{host}"


def build_authorization_server_metadata(request: Request) -> dict[str, Any]:
    base = _base_url(request)
    return {
        "issuer": base,
        "authorization_endpoint": f"{base}/api/v1/oauth/authorize",
        "token_endpoint": f"{base}/api/v1/oauth/token",
        "registration_endpoint": f"{base}/api/v1/oauth/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none", "client_secret_basic"],
    }


def build_protected_resource_metadata(request: Request) -> dict[str, Any]:
    """RFC 9728. Dit au client MCP OU trouver l'authorization server.

    C'est ce que le client MCP fetch en premier quand il se voit refuser
    l'acces au /mcp/ endpoint : le header `WWW-Authenticate` pointe vers ce
    document, qui donne l'URL du /.well-known/oauth-authorization-server.
    """
    base = _base_url(request)
    return {
        "resource": f"{base}/mcp/",
        "authorization_servers": [base],
        "bearer_methods_supported": ["header"],
    }
