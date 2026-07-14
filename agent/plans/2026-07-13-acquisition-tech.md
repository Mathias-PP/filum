# Plan d'implémentation — Technique d'acquisition (waitlist, claim, MCP)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Livrer les 3 briques techniques du plan d'acquisition : formulaire waitlist (PR 1), mécanisme « seed & claim » v1 minimal (PR 2), serveur MCP read-only (PR 3).

**Architecture:** Chaque brique = une branche + une PR indépendante, mergeable seule. Backend FastAPI async existant (`apps/backend/app/`), frontend SvelteKit 5 (`apps/frontend/src/`). Le MCP est monté sur l'app FastAPI existante via FastMCP (Streamable HTTP sur `/mcp`).

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2 async / Alembic / Pydantic v2 / slowapi · SvelteKit 2 / Svelte 5 runes / Tailwind · **Nouvelle dépendance (PR 3 uniquement) : `fastmcp`** — signalée et justifiée (serveur MCP, cœur de l'idée E du business plan).

---

## Règles d'exécution (à relire après CHAQUE compaction de contexte)

1. **Ce fichier est la source de vérité.** Après toute compaction : relire ce fichier EN ENTIER + `CLAUDE.md` avant de continuer. Cocher `- [x]` chaque étape terminée **dans ce fichier** immédiatement (c'est la persistance anti-perte-de-contexte).
2. **Avant tout commit/push : `git fetch origin` + `wsl gh pr list` — vérifier qu'aucune PR concernée n'est déjà mergée** (l'utilisateur merge vite ; règle mémoire issue de l'incident PR #103).
3. Chaque PR part de `main` fraîchement pullé. Jamais de branche empilée sur une autre.
4. Conventional commits, titre ≤ 50 caractères. Un commit par étape « Commit » du plan.
5. ID de migration Alembic ≤ 32 caractères. Jamais de `op.create_index` doublonnant un `index=True` déjà présent dans `create_table` (piège PITFALLS §1.1/§1.2).
6. Pas d'autre nouvelle dépendance que `fastmcp` (PR 3). Si une étape semble en exiger une : STOP, demander.
7. Tests via WSL : `wsl -e bash -c "cd /mnt/c/Users/mathi/Documents/filum_project/filum/apps/backend && uv run pytest tests/ -x -q"` (uv Windows casse sur le .venv WSL). Lint : `uv run ruff check .`. Frontend : `pnpm run check` et `pnpm run lint` dans `apps/frontend`.
8. Ne PAS déployer. Ne PAS toucher `.docs/`. Mettre à jour `STATE.md` à la fin de chaque PR.
9. En cas de doute sur un pattern : copier le pattern existant cité dans ce plan (extraits réels du repo, vérifiés le 2026-07-13).

---

# PR 1 — Waitlist (`feat/waitlist`)

**But :** `POST /api/v1/waitlist` public rate-limité + formulaire email sur la home. Stockage Postgres, idempotent, sans révéler si un email est déjà inscrit.

### Task 1.1 : Branche

- [ ] **Step 1 :** `git fetch origin` puis `wsl gh pr list` — noter les PRs ouvertes. Si une PR touche déjà la waitlist : STOP, demander.
- [ ] **Step 2 :** `git checkout main && git pull origin main && git checkout -b feat/waitlist`

### Task 1.2 : Modèle + migration

**Files:**
- Create: `apps/backend/app/models/waitlist_entry.py`
- Modify: `apps/backend/app/models/__init__.py`
- Create: `apps/backend/alembic/versions/009_waitlist.py`

- [ ] **Step 1 : Modèle** — créer `apps/backend/app/models/waitlist_entry.py` :

```python
from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base, TimestampMixin


class WaitlistEntry(Base, TimestampMixin):
    __tablename__ = "waitlist_entries"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    context: Mapped[str] = mapped_column(String(50), nullable=False, default="home")
```

(`TimestampMixin` existe dans `app/db/database.py` lignes 34-40 — fournit created_at/updated_at/deleted_at.)

- [ ] **Step 2 :** Dans `apps/backend/app/models/__init__.py`, ajouter `from app.models.waitlist_entry import WaitlistEntry` (ordre alphabétique des imports) et `"WaitlistEntry"` dans `__all__`.

- [ ] **Step 3 : Migration** — créer `apps/backend/alembic/versions/009_waitlist.py` :

```python
"""Add waitlist_entries table.

Revision ID: 009_waitlist
Revises: 008_source_soft_del
Create Date: 2026-07-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "009_waitlist"
down_revision: str | None = "008_source_soft_del"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "waitlist_entries",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True, index=True),
        sa.Column("context", sa.String(50), nullable=False, server_default="home"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    # NE PAS ajouter d'op.create_index : index=True dans create_table le crée déjà (PITFALLS §1.2)


def downgrade() -> None:
    op.drop_table("waitlist_entries")
```

- [ ] **Step 4 : Commit** — `git add apps/backend/app/models/ apps/backend/alembic/versions/009_waitlist.py && git commit -m "feat: modele et migration waitlist"`

### Task 1.3 : Schema + endpoint (TDD)

**Files:**
- Create: `apps/backend/app/schemas/waitlist.py`
- Create: `apps/backend/app/api/v1/endpoints/waitlist.py`
- Modify: `apps/backend/app/api/v1/router.py` (ou fichier équivalent qui définit `create_router()` — le localiser avec `grep -r "create_router" apps/backend/app/api/`)
- Create: `apps/backend/tests/integration/test_waitlist.py`

- [ ] **Step 1 : Test d'échec d'abord** — créer `apps/backend/tests/integration/test_waitlist.py` (pattern fixture `client` copié de `tests/integration/test_oauth_callback.py` lignes 11-20) :

```python
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select


@pytest_asyncio.fixture
async def client(db_session):
    from app.db.database import get_db
    from app.main import app

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_join_waitlist_creates_entry(client, db_session):
    from app.models.waitlist_entry import WaitlistEntry

    resp = await client.post("/api/v1/waitlist", json={"email": "Ada@Example.org"})
    assert resp.status_code == 201
    assert resp.json() == {"ok": True}
    entry = await db_session.scalar(select(WaitlistEntry))
    assert entry.email == "ada@example.org"  # normalise en lowercase
    assert entry.context == "home"


@pytest.mark.asyncio
async def test_join_waitlist_is_idempotent(client, db_session):
    from app.models.waitlist_entry import WaitlistEntry

    for _ in range(2):
        resp = await client.post("/api/v1/waitlist", json={"email": "ada@example.org"})
        assert resp.status_code == 201
    count = await db_session.scalar(select(func.count()).select_from(WaitlistEntry))
    assert count == 1


@pytest.mark.asyncio
async def test_join_waitlist_rejects_invalid_email(client):
    resp = await client.post("/api/v1/waitlist", json={"email": "pas-un-email"})
    assert resp.status_code == 422
```

⚠️ Ajouter aussi `import app.models.waitlist_entry  # noqa: E402, F401` dans `tests/conftest.py` à la suite des imports de modèles existants (lignes 23-27), sinon `create_all` ne crée pas la table.

- [ ] **Step 2 :** Lancer : `wsl -e bash -c "cd /mnt/c/Users/mathi/Documents/filum_project/filum/apps/backend && uv run pytest tests/integration/test_waitlist.py -x -q"` — Attendu : FAIL (404, la route n'existe pas).

- [ ] **Step 3 : Schema** — créer `apps/backend/app/schemas/waitlist.py` (`email-validator` est déjà en dépendance → `EmailStr` disponible) :

```python
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class WaitlistCreate(BaseModel):
    email: EmailStr
    context: str = Field(default="home", max_length=50)


class WaitlistResponse(BaseModel):
    ok: bool = True
```

- [ ] **Step 4 : Endpoint** — créer `apps/backend/app/api/v1/endpoints/waitlist.py` :

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.db.database import get_db
from app.models.waitlist_entry import WaitlistEntry
from app.schemas.waitlist import WaitlistCreate, WaitlistResponse

router = APIRouter()


@router.post("/waitlist", response_model=WaitlistResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/hour")
async def join_waitlist(
    request: Request,
    payload: WaitlistCreate,
    db: AsyncSession = Depends(get_db),
):
    email = payload.email.lower().strip()
    existing = await db.scalar(select(WaitlistEntry).where(WaitlistEntry.email == email))
    if existing is None:
        db.add(WaitlistEntry(email=email, context=payload.context))
        await db.commit()
    # Toujours 201 : ne révèle pas si l'email était déjà inscrit (anti-énumération)
    return WaitlistResponse()
```

(Le paramètre `request: Request` est requis par slowapi — même pattern que `create_card` dans `cards.py` ligne 65.)

- [ ] **Step 5 :** Enregistrer le router : ouvrir le fichier qui définit `create_router()` (`app/api/v1/router.py`), copier exactement le pattern des autres endpoints (ex. `router.include_router(cards.router, tags=["cards"])`) pour ajouter `waitlist` avec `tags=["waitlist"]`.

- [ ] **Step 6 :** Relancer le test (même commande Step 2) — Attendu : 3 PASS.

- [ ] **Step 7 :** `wsl -e bash -c "cd .../apps/backend && uv run ruff check . && uv run pytest tests/ -q"` — tout vert (aucune régression).

- [ ] **Step 8 : Commit** — `git commit -m "feat: endpoint POST /waitlist idempotent"` (avec les fichiers créés + conftest + router).

### Task 1.4 : Frontend

**Files:**
- Create: `apps/frontend/src/lib/components/WaitlistForm.svelte`
- Modify: `apps/frontend/src/lib/components/index.ts` (export — vérifier le pattern d'export existant)
- Modify: `apps/frontend/src/lib/api/client.ts` (ajouter `api.waitlist`)
- Modify: `apps/frontend/src/routes/+page.svelte` (insérer le formulaire)

- [ ] **Step 1 :** Dans `client.ts`, ajouter à l'objet `api` (même niveau que `auth`, `cards`) :

```typescript
waitlist: {
  join: async (email: string, context: string = 'home'): Promise<{ ok: boolean }> => {
    return request<{ ok: boolean }>('/waitlist', {
      method: 'POST',
      body: JSON.stringify({ email, context }),
    });
  },
},
```

- [ ] **Step 2 :** Créer `WaitlistForm.svelte` (Svelte 5 runes — PAS de `@const` hors bloc, PAS de self-assignment de `$state`) :

```svelte
<script lang="ts">
  import { api } from '$lib/api/client';
  import Button from './Button.svelte';

  interface Props {
    context?: string;
  }

  let { context = 'home' }: Props = $props();

  let email = $state('');
  let status = $state<'idle' | 'loading' | 'done' | 'error'>('idle');

  async function submit(e: SubmitEvent) {
    e.preventDefault();
    if (!email || status === 'loading') return;
    status = 'loading';
    try {
      await api.waitlist.join(email, context);
      status = 'done';
    } catch {
      status = 'error';
    }
  }
</script>

{#if status === 'done'}
  <p class="text-sm text-ink-secondary">Merci ! Vous serez prévenu·e à l'ouverture.</p>
{:else}
  <form onsubmit={submit} class="flex flex-col sm:flex-row gap-2 max-w-md">
    <input
      type="email"
      bind:value={email}
      required
      placeholder="votre@email.fr"
      class="flex-1 rounded border border-border-strong bg-transparent px-3 py-2 text-sm focus:outline-none focus:ring-1"
      aria-label="Adresse email"
    />
    <Button type="submit" loading={status === 'loading'}>Être prévenu·e</Button>
  </form>
  {#if status === 'error'}
    <p class="mt-1 text-sm text-danger">Une erreur est survenue, réessayez.</p>
  {/if}
{/if}
```

(Vérifier que les classes `text-ink-secondary`, `border-border-strong`, `text-danger` existent — elles sont utilisées par `Button.svelte`. Sinon reprendre les classes du composant voisin le plus proche.)

- [ ] **Step 3 :** Lire `src/routes/+page.svelte` (home) et insérer `<WaitlistForm />` dans la section hero/CTA existante, avec un titre court du type « Créateur·ice ? Demandez votre fiche. » — respecter la structure/style existants, modification minimale.

- [ ] **Step 4 :** `cd apps/frontend && pnpm run check && pnpm run lint` — zéro erreur. Puis test manuel : `docker compose -f docker-compose.dev.yml up` (postgres + backend) + `pnpm run dev`, soumettre un email sur http://localhost:5173, vérifier 201 dans l'onglet réseau et la ligne en DB (`docker exec -it filum-postgres-dev psql -U filum -d filum_dev -c "select * from waitlist_entries;"`). Appliquer la migration d'abord : `docker compose -f docker-compose.dev.yml run --rm migrate` ou `uv run alembic upgrade head` via WSL.

- [ ] **Step 5 : Commit** — `git commit -m "feat: formulaire waitlist sur la home"`

### Task 1.5 : PR

- [ ] **Step 1 :** Mettre à jour `STATE.md` (section « Phase courante » : waitlist livrée ; PRs ouvertes : ajouter la ligne). Commit `docs: STATE.md waitlist`.
- [ ] **Step 2 :** `git fetch origin && wsl gh pr list` (re-vérification). Push : `git push -u origin feat/waitlist`. PR avec `wsl gh pr create` — titre « feat: waitlist (plan acquisition PR 1/3) », body : résumé + test plan (checkbox migration Railway/Oracle à appliquer au déploiement).

---

# PR 2 — Seed & Claim v1 minimal (`feat/card-claim`)

**But :** marquer des fiches comme « fiches d'exemple » (`is_seed`), afficher un bandeau public « Réclamez cette fiche », enregistrer les demandes (`claim_requests`). Validation/transfert = manuel (v1). Aucun email envoyé.

### Task 2.1 : Branche

- [ ] **Step 1 :** `git fetch origin` + `wsl gh pr list` (PR 1 peut déjà être mergée — c'est OK, les briques sont indépendantes). `git checkout main && git pull && git checkout -b feat/card-claim`

### Task 2.2 : Modèle + migration

**Files:**
- Modify: `apps/backend/app/models/biblio_card.py` (champ `is_seed`)
- Create: `apps/backend/app/models/claim_request.py`
- Modify: `apps/backend/app/models/__init__.py`
- Create: `apps/backend/alembic/versions/010_claim_requests.py`

- [ ] **Step 1 :** Dans `BiblioCard` (après le champ `status`, ligne ~68) ajouter :

```python
    is_seed: Mapped[bool] = mapped_column(default=False, nullable=False)
```

- [ ] **Step 2 :** Créer `apps/backend/app/models/claim_request.py` :

```python
from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base, TimestampMixin


class ClaimRequest(Base, TimestampMixin):
    __tablename__ = "claim_requests"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    card_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("biblio_cards.id"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    channel_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
```

- [ ] **Step 3 :** `__init__.py` : ajouter import + `__all__` (comme Task 1.2 Step 2).

- [ ] **Step 4 :** Migration `010_claim_requests.py` :

```python
"""Add is_seed on biblio_cards + claim_requests table.

Revision ID: 010_claim_requests
Revises: 009_waitlist
Create Date: 2026-07-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "010_claim_requests"
down_revision: str | None = "009_waitlist"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "biblio_cards",
        sa.Column("is_seed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "claim_requests",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "card_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("biblio_cards.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("channel_url", sa.String(1000), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending", index=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    # index=True dans create_table suffit — pas de create_index (PITFALLS §1.2)


def downgrade() -> None:
    op.drop_table("claim_requests")
    op.drop_column("biblio_cards", "is_seed")
```

⚠️ Si PR 1 n'est pas encore mergée quand cette branche part de main, `down_revision` doit pointer la head réelle : vérifier avec `ls apps/backend/alembic/versions/` et ajuster (`008_source_soft_del` si 009 absent). Le noter dans la description de PR.

- [ ] **Step 5 : Commit** — `git commit -m "feat: is_seed + table claim_requests"`

### Task 2.3 : Exposer `is_seed` + endpoint claim (TDD)

**Files:**
- Modify: `apps/backend/app/schemas/biblio_card.py` (champ `is_seed` dans `CardResponse`)
- Modify: `apps/backend/app/api/v1/endpoints/cards.py` (passer `is_seed` dans `get_public_card`, + endpoint claim)
- Create: `apps/backend/app/schemas/claim.py`
- Create: `apps/backend/tests/integration/test_claim.py`

- [ ] **Step 1 : Tests d'abord** — `tests/integration/test_claim.py` (fixture `client` identique à Task 1.3 ; fixture card : créer un user + une BiblioCard `status="published", is_seed=True` via `db_session`, pattern de `test_user` dans `conftest.py`) :

```python
from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select


@pytest_asyncio.fixture
async def client(db_session):
    from app.db.database import get_db
    from app.main import app

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seed_card(db_session, test_user):
    from app.models.biblio_card import BiblioCard

    card = BiblioCard(
        id=uuid4(),
        user_id=test_user.id,
        slug="fiche-seed",
        title="Fiche seed",
        content_type="video",
        platform="youtube",
        status="published",
        is_seed=True,
    )
    db_session.add(card)
    await db_session.commit()
    await db_session.refresh(card)
    return card


@pytest.mark.asyncio
async def test_public_card_exposes_is_seed(client, seed_card, test_user):
    resp = await client.get(f"/api/v1/@{test_user.username}/{seed_card.slug}")
    assert resp.status_code == 200
    assert resp.json()["is_seed"] is True


@pytest.mark.asyncio
async def test_claim_request_created(client, seed_card, db_session):
    from app.models.claim_request import ClaimRequest

    resp = await client.post(
        f"/api/v1/cards/{seed_card.id}/claim-requests",
        json={"email": "createur@example.org", "channel_url": "https://youtube.com/@createur"},
    )
    assert resp.status_code == 201
    req = await db_session.scalar(select(ClaimRequest))
    assert req.card_id == seed_card.id
    assert req.status == "pending"


@pytest.mark.asyncio
async def test_claim_rejected_on_non_seed_card(client, seed_card, db_session):
    seed_card.is_seed = False
    await db_session.commit()
    resp = await client.post(
        f"/api/v1/cards/{seed_card.id}/claim-requests",
        json={"email": "x@example.org", "channel_url": "https://youtube.com/@x"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_claim_404_on_unknown_card(client):
    resp = await client.post(
        f"/api/v1/cards/{uuid4()}/claim-requests",
        json={"email": "x@example.org", "channel_url": "https://youtube.com/@x"},
    )
    assert resp.status_code == 404
```

⚠️ Ajouter `import app.models.claim_request  # noqa: E402, F401` dans `tests/conftest.py`.

- [ ] **Step 2 :** Lancer — Attendu : FAIL (`is_seed` absent de la réponse ; route claim 404).

- [ ] **Step 3 : Schemas** — dans `schemas/biblio_card.py`, ajouter `is_seed: bool = False` à `CardResponse` (hérité par `CardDetail`). Créer `schemas/claim.py` :

```python
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class ClaimRequestCreate(BaseModel):
    email: EmailStr
    channel_url: str = Field(min_length=8, max_length=1000)
    message: str | None = Field(default=None, max_length=2000)


class ClaimRequestResponse(BaseModel):
    ok: bool = True
```

- [ ] **Step 4 : Endpoint** — dans `cards.py`, (a) ajouter `is_seed=card.is_seed` dans la construction `CardDetail(...)` de `get_public_card` (ligne ~240) ; vérifier si `CardResponse` est construit ailleurs à la main (grep `CardResponse(`) et compléter pareil ; (b) ajouter l'endpoint :

```python
@router.post(
    "/cards/{card_id}/claim-requests",
    response_model=ClaimRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("5/hour")
async def create_claim_request(
    request: Request,
    card_id: UUID,
    payload: ClaimRequestCreate,
    db: AsyncSession = Depends(get_db),
):
    card = await db.get(BiblioCard, card_id)
    if card is None or card.deleted_at is not None or card.status != "published":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Card not found"},
        )
    if not card.is_seed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "not_claimable", "message": "This card is not a seed card"},
        )
    db.add(
        ClaimRequest(
            card_id=card.id,
            email=payload.email.lower().strip(),
            channel_url=payload.channel_url.strip(),
            message=payload.message,
        )
    )
    await db.commit()
    return ClaimRequestResponse()
```

Imports à ajouter en tête de `cards.py` : `from uuid import UUID`, `from app.models.biblio_card import BiblioCard`, `from app.models.claim_request import ClaimRequest`, `from app.schemas.claim import ClaimRequestCreate, ClaimRequestResponse`.

- [ ] **Step 5 :** Relancer les tests claim puis toute la suite + ruff. Tout vert.
- [ ] **Step 6 : Commit** — `git commit -m "feat: endpoint claim-requests + is_seed expose"`

### Task 2.4 : Frontend — bandeau + modal claim

**Files:**
- Create: `apps/frontend/src/lib/components/ClaimBanner.svelte`
- Modify: exports composants + `client.ts` + types (localiser `CardDetail` TS : `grep -r "interface CardDetail" apps/frontend/src/lib`) + `src/routes/@[creator][card]/+page.svelte`

- [ ] **Step 1 :** Ajouter `is_seed: boolean;` au type TS `CardDetail`. Ajouter dans `client.ts` :

```typescript
claims: {
  create: async (
    cardId: string,
    data: { email: string; channel_url: string; message?: string }
  ): Promise<{ ok: boolean }> => {
    return request<{ ok: boolean }>(`/cards/${cardId}/claim-requests`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },
},
```

- [ ] **Step 2 :** Créer `ClaimBanner.svelte` — bandeau + formulaire inline dans le `Modal.svelte` existant :

```svelte
<script lang="ts">
  import { api } from '$lib/api/client';
  import Button from './Button.svelte';
  import Modal from './Modal.svelte';

  interface Props {
    cardId: string;
    creatorName: string;
  }

  let { cardId, creatorName }: Props = $props();

  let open = $state(false);
  let email = $state('');
  let channelUrl = $state('');
  let message = $state('');
  let status = $state<'idle' | 'loading' | 'done' | 'error'>('idle');

  async function submit(e: SubmitEvent) {
    e.preventDefault();
    if (status === 'loading') return;
    status = 'loading';
    try {
      await api.claims.create(cardId, {
        email,
        channel_url: channelUrl,
        message: message || undefined,
      });
      status = 'done';
    } catch {
      status = 'error';
    }
  }
</script>

<div
  class="mb-6 flex flex-col sm:flex-row sm:items-center gap-3 rounded border border-border-strong bg-surface-tertiary px-4 py-3 text-sm"
>
  <p class="flex-1">
    Fiche d'exemple établie par Philum à partir de sources publiques — non validée par
    {creatorName}. Vous êtes {creatorName} ?
  </p>
  <Button size="sm" onclick={() => (open = true)}>Réclamer cette fiche</Button>
</div>

<Modal bind:open title="Réclamer cette fiche">
  {#if status === 'done'}
    <p class="text-sm">Demande envoyée — nous vous recontactons sous 48 h. Merci !</p>
  {:else}
    <form onsubmit={submit} class="flex flex-col gap-3">
      <input
        type="email"
        bind:value={email}
        required
        placeholder="votre@email.fr"
        class="rounded border border-border-strong bg-transparent px-3 py-2 text-sm"
        aria-label="Email"
      />
      <input
        type="url"
        bind:value={channelUrl}
        required
        placeholder="Lien de votre chaîne / site"
        class="rounded border border-border-strong bg-transparent px-3 py-2 text-sm"
        aria-label="Lien de votre chaîne"
      />
      <textarea
        bind:value={message}
        rows="3"
        placeholder="Message (optionnel)"
        class="rounded border border-border-strong bg-transparent px-3 py-2 text-sm"
      ></textarea>
      <Button type="submit" loading={status === 'loading'}>Envoyer la demande</Button>
      {#if status === 'error'}
        <p class="text-sm text-danger">Erreur — réessayez.</p>
      {/if}
    </form>
  {/if}
</Modal>
```

⚠️ Lire `Modal.svelte` d'abord : adapter les props réelles (`bind:open` / `title` / snippet children) à son interface effective.

- [ ] **Step 3 :** Dans la page fiche publique (`src/routes/@[creator][card]/+page.svelte`), afficher le bandeau sous le header de la fiche :

```svelte
{#if card.is_seed}
  <ClaimBanner cardId={card.id} creatorName={card.creator.display_name ?? card.creator.slug} />
{/if}
```

- [ ] **Step 4 :** `pnpm run check && pnpm run lint`. Test manuel navigateur : marquer la fiche seed en DB (`update biblio_cards set is_seed = true where slug = '...'`), vérifier bandeau + soumission modal + ligne `claim_requests` en DB + cas erreur (email invalide).
- [ ] **Step 5 : Commit** — `git commit -m "feat: bandeau claim sur fiche seed"`

### Task 2.5 : PR

- [ ] **Step 1 :** STATE.md à jour, commit. `git fetch` + `wsl gh pr list`, push, `wsl gh pr create` — « feat: seed & claim v1 (plan acquisition PR 2/3) ». Mentionner dans le body : validation des claims = manuelle en v1 (requêtes SQL), pas d'email automatique.

---

# PR 3 — Serveur MCP read-only (`feat/mcp-server`)

**But :** monter un serveur MCP Streamable HTTP sur `/mcp` de l'app FastAPI existante, avec 4 tools read-only frugaux en tokens : `search_cards`, `get_card`, `get_source`, `find_cards_citing`. Données publiées uniquement. Pas d'auth en v1.

**⚠️ Nouvelle dépendance : `fastmcp`** (framework MCP standard, gofastmcp.com). Justification : idée E du business plan, brique de distribution IA. Pattern de montage vérifié sur le web le 2026-07-13 ([doc officielle](https://gofastmcp.com/integrations/fastapi)) :
```python
mcp_app = mcp.http_app(path="/")
app = FastAPI(lifespan=mcp_app.lifespan)   # lifespan OBLIGATOIRE sinon session manager non initialisé
app.mount("/mcp", mcp_app)
```

### Task 3.1 : Branche + dépendance

- [ ] **Step 1 :** `git fetch origin` + `wsl gh pr list`. `git checkout main && git pull && git checkout -b feat/mcp-server`
- [ ] **Step 2 :** `wsl -e bash -c "cd .../apps/backend && uv add fastmcp"` — vérifier que `pyproject.toml` et `uv.lock` sont modifiés. Contrôler la version installée (`uv run python -c "import fastmcp; print(fastmcp.__version__)"`) ; si l'API `http_app` n'existe pas dans la version installée, consulter https://gofastmcp.com/integrations/fastapi AVANT d'écrire du code (ne jamais deviner l'API).
- [ ] **Step 3 : Commit** — `git commit -m "chore: ajoute dependance fastmcp"`

### Task 3.2 : Tools (fonctions pures, TDD)

**Files:**
- Create: `apps/backend/app/mcp_server/__init__.py` (vide)
- Create: `apps/backend/app/mcp_server/tools.py` (fonctions pures — testables sans MCP)
- Create: `apps/backend/tests/unit/test_mcp_tools.py`

Principe : les tools sont des fonctions async pures prenant une `AsyncSession` en paramètre → testables avec la fixture `db_session` existante, sans dépendre de l'API FastMCP.

- [ ] **Step 1 : Tests d'abord** — `tests/unit/test_mcp_tools.py` :

```python
from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def published_card(db_session, test_user):
    from app.models.biblio_card import BiblioCard
    from app.models.source import Source

    card = BiblioCard(
        id=uuid4(),
        user_id=test_user.id,
        slug="memoire-cerveau",
        title="Mémoire et cerveau",
        content_type="video",
        platform="youtube",
        status="published",
    )
    db_session.add(card)
    await db_session.flush()
    source = Source(
        id=uuid4(),
        biblio_card_id=card.id,
        position=0,
        url="https://doi.org/10.1000/exemple",
        title="Étude exemple",
        format="texte",
        category="article-scientifique",
        author_kind="chercheur",
    )
    db_session.add(source)
    await db_session.commit()
    return card, source


@pytest.mark.asyncio
async def test_search_cards_finds_by_title(db_session, published_card, test_user):
    from app.mcp_server.tools import search_cards

    results = await search_cards(db_session, query="mémoire")
    assert len(results) == 1
    assert results[0]["creator"] == test_user.username
    assert results[0]["slug"] == "memoire-cerveau"
    # Compacité token : pas de description ni de sources dans les résultats de recherche
    assert "sources" not in results[0]


@pytest.mark.asyncio
async def test_search_cards_ignores_drafts(db_session, published_card, test_user):
    from app.mcp_server.tools import search_cards
    from app.models.biblio_card import BiblioCard

    draft = BiblioCard(
        id=uuid4(),
        user_id=test_user.id,
        slug="brouillon",
        title="Mémoire brouillon",
        content_type="video",
        platform="youtube",
        status="draft",
    )
    db_session.add(draft)
    await db_session.commit()
    results = await search_cards(db_session, query="mémoire")
    assert len(results) == 1


@pytest.mark.asyncio
async def test_get_card_returns_compact_sources(db_session, published_card, test_user):
    from app.mcp_server.tools import get_card

    card_dict = await get_card(db_session, creator=test_user.username, slug="memoire-cerveau")
    assert card_dict["title"] == "Mémoire et cerveau"
    assert len(card_dict["sources"]) == 1
    src = card_dict["sources"][0]
    assert src["url"] == "https://doi.org/10.1000/exemple"
    assert "annotation" not in src  # détail réservé à get_source


@pytest.mark.asyncio
async def test_get_card_unknown_returns_none(db_session):
    from app.mcp_server.tools import get_card

    assert await get_card(db_session, creator="nobody", slug="nope") is None


@pytest.mark.asyncio
async def test_get_source_detail(db_session, published_card):
    from app.mcp_server.tools import get_source

    _, source = published_card
    detail = await get_source(db_session, source_id=str(source.id))
    assert detail["title"] == "Étude exemple"
    assert detail["category"] == "article-scientifique"


@pytest.mark.asyncio
async def test_find_cards_citing_same_url(db_session, published_card, test_user):
    from app.mcp_server.tools import find_cards_citing

    results = await find_cards_citing(db_session, url="https://doi.org/10.1000/exemple")
    assert len(results) == 1
    assert results[0]["slug"] == "memoire-cerveau"
```

- [ ] **Step 2 :** Lancer — FAIL (module absent).

- [ ] **Step 3 : Implémentation** — `apps/backend/app/mcp_server/tools.py` :

```python
"""Fonctions read-only du serveur MCP.

Fonctions pures (session en paramètre) pour rester testables sans le
protocole MCP. Réponses volontairement compactes : l'IA cliente ne charge
que les nœuds qu'elle visite (frugalité en tokens).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.biblio_card import BiblioCard
from app.models.source import Source
from app.models.user import User

_PUBLISHED = (BiblioCard.status == "published") & BiblioCard.deleted_at.is_(None)


async def search_cards(db: AsyncSession, query: str, limit: int = 10) -> list[dict[str, Any]]:
    stmt = (
        select(BiblioCard)
        .join(User, BiblioCard.user_id == User.id)
        .where(
            _PUBLISHED,
            func.lower(BiblioCard.title).contains(query.lower())
            | func.lower(User.username).contains(query.lower()),
        )
        .options(selectinload(BiblioCard.user))
        .order_by(BiblioCard.published_at.desc())
        .limit(min(max(limit, 1), 25))
    )
    cards = (await db.scalars(stmt)).all()
    return [{"creator": c.user.username, "slug": c.slug, "title": c.title} for c in cards]


async def get_card(db: AsyncSession, creator: str, slug: str) -> dict[str, Any] | None:
    stmt = (
        select(BiblioCard)
        .join(User, BiblioCard.user_id == User.id)
        .where(_PUBLISHED, User.username == creator, BiblioCard.slug == slug)
        .options(selectinload(BiblioCard.user), selectinload(BiblioCard.sources))
    )
    card = await db.scalar(stmt)
    if card is None:
        return None
    return {
        "creator": card.user.username,
        "slug": card.slug,
        "title": card.title,
        "description": card.description,
        "content_url": card.content_url,
        "published_at": card.published_at.isoformat() if card.published_at else None,
        "sources": [
            {
                "id": str(s.id),
                "title": s.title,
                "url": s.url,
                "category": s.category,
                "author_kind": s.author_kind,
            }
            for s in card.sources
            if s.deleted_at is None
        ],
    }


async def get_source(db: AsyncSession, source_id: str) -> dict[str, Any] | None:
    try:
        sid = UUID(source_id)
    except ValueError:
        return None
    source = await db.scalar(
        select(Source).where(Source.id == sid, Source.deleted_at.is_(None))
    )
    if source is None:
        return None
    return {
        "id": str(source.id),
        "title": source.title,
        "url": source.url,
        "authors": source.authors,
        "published_at": source.published_at.isoformat() if source.published_at else None,
        "format": source.format,
        "category": source.category,
        "author_kind": source.author_kind,
        "annotation": source.annotation,
        "archive_url": source.archive_url,
        "archive_timestamp": (
            source.archive_timestamp.isoformat() if source.archive_timestamp else None
        ),
    }


async def find_cards_citing(db: AsyncSession, url: str, limit: int = 10) -> list[dict[str, Any]]:
    stmt = (
        select(BiblioCard)
        .join(Source, Source.biblio_card_id == BiblioCard.id)
        .join(User, BiblioCard.user_id == User.id)
        .where(_PUBLISHED, Source.deleted_at.is_(None), Source.url == url.strip())
        .options(selectinload(BiblioCard.user))
        .distinct()
        .limit(min(max(limit, 1), 25))
    )
    cards = (await db.scalars(stmt)).all()
    return [{"creator": c.user.username, "slug": c.slug, "title": c.title} for c in cards]
```

- [ ] **Step 4 :** Tests unit → PASS. Suite complète + ruff → vert.
- [ ] **Step 5 : Commit** — `git commit -m "feat: tools MCP read-only testables"`

### Task 3.3 : Serveur FastMCP + montage

**Files:**
- Create: `apps/backend/app/mcp_server/server.py`
- Modify: `apps/backend/app/main.py` (lifespan combiné + mount)
- Create: `apps/backend/tests/unit/test_mcp_mount.py`

- [ ] **Step 1 :** `apps/backend/app/mcp_server/server.py` :

```python
"""Serveur MCP Philum — lecture publique du graphe de fiches."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import engine
from app.mcp_server import tools

mcp = FastMCP(
    "philum",
    instructions=(
        "Philum expose des fiches bibliographiques publiques de créateurs de contenu. "
        "Naviguer comme un graphe : search_cards pour trouver, get_card pour le détail "
        "compact d'une fiche, get_source pour une source précise, find_cards_citing "
        "pour découvrir qui d'autre cite une URL."
    ),
)


def _session() -> AsyncSession:
    return AsyncSession(bind=engine, expire_on_commit=False)


@mcp.tool()
async def search_cards(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Recherche des fiches publiées par titre ou nom de créateur (résultats compacts)."""
    async with _session() as db:
        return await tools.search_cards(db, query=query, limit=limit)


@mcp.tool()
async def get_card(creator: str, slug: str) -> dict[str, Any] | None:
    """Détail d'une fiche : description, sources compactes (id, titre, url, catégorie)."""
    async with _session() as db:
        return await tools.get_card(db, creator=creator, slug=slug)


@mcp.tool()
async def get_source(source_id: str) -> dict[str, Any] | None:
    """Détail complet d'une source : auteurs, annotation, archive horodatée."""
    async with _session() as db:
        return await tools.get_source(db, source_id=source_id)


@mcp.tool()
async def find_cards_citing(url: str, limit: int = 10) -> list[dict[str, Any]]:
    """Fiches publiées citant cette URL — les arêtes du graphe de citations."""
    async with _session() as db:
        return await tools.find_cards_citing(db, url=url, limit=limit)


mcp_http_app = mcp.http_app(path="/")
```

- [ ] **Step 2 :** Dans `main.py` : importer `from app.mcp_server.server import mcp_http_app`, modifier le lifespan existant (lignes 27-32) pour imbriquer celui du MCP (requis pour le session manager Streamable HTTP), et monter APRÈS la création de l'app :

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"CORS allowed origins: {settings.cors_origins!r}")
    async with mcp_http_app.lifespan(app):
        yield
    logger.info("Shutting down...")
```

et après `app.include_router(...)` (ligne 74) :

```python
app.mount("/mcp", mcp_http_app)
```

- [ ] **Step 3 : Test smoke** — `tests/unit/test_mcp_mount.py` :

```python
from __future__ import annotations


def test_mcp_route_is_mounted():
    from app.main import app

    mounted = [r.path for r in app.routes if getattr(r, "path", "").startswith("/mcp")]
    assert mounted, "Le serveur MCP doit être monté sur /mcp"


def test_mcp_tools_registered():
    import asyncio

    from app.mcp_server.server import mcp

    tools = asyncio.get_event_loop().run_until_complete(mcp.get_tools())
    names = set(tools)
    assert {"search_cards", "get_card", "get_source", "find_cards_citing"} <= names
```

⚠️ Si `mcp.get_tools()` n'existe pas dans la version installée de fastmcp, chercher la méthode d'introspection équivalente dans la doc (`await mcp._list_tools()` etc.) — ne pas inventer ; en dernier recours supprimer ce second test et garder le smoke test du mount.

- [ ] **Step 4 :** Suite complète + ruff → vert. Vérification manuelle : `uv run uvicorn app.main:app --port 8000` (via WSL) puis `npx @modelcontextprotocol/inspector` (outil officiel) pointé sur `http://localhost:8000/mcp` — lister les tools, appeler `search_cards`. Si l'inspector n'est pas disponible : `curl -X POST http://localhost:8000/mcp -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"test","version":"0"}}}'` — attendu : réponse JSON-RPC `result` avec `serverInfo`.
- [ ] **Step 5 : Commit** — `git commit -m "feat: serveur MCP monte sur /mcp"`

### Task 3.4 : PR

- [ ] **Step 1 :** STATE.md (MCP livré, tools listés, dépendance fastmcp notée) + entrée `DECISIONS.md` (décision : MCP monté in-process sur l'app FastAPI plutôt que service séparé — simplicité pré-MVP, une seule instance à déployer sur la VM Oracle). Commit `docs: STATE et DECISIONS pour MCP`.
- [ ] **Step 2 :** `git fetch` + `wsl gh pr list`, push, PR « feat: serveur MCP read-only (plan acquisition PR 3/3) ». Body : les 4 tools, la nouvelle dépendance justifiée, la vérification inspector, et la note « exposition publique HTTPS = à l'arrivée de la VM Oracle (Caddy) ».

---

## Critères de fin (definition of done globale)

- [ ] 3 PRs ouvertes (ou mergées), CI verte sur chacune
- [ ] `uv run pytest tests/` : 100 % pass, aucune régression sur les ~70 tests existants
- [ ] Frontend : `pnpm run check` + `pnpm run lint` verts ; parcours waitlist et claim testés en navigateur
- [ ] MCP : initialize + tools/list répondent sur `/mcp` en local
- [ ] `STATE.md` reflète l'état réel ; `DECISIONS.md` a l'entrée MCP
- [ ] Aucune dépendance ajoutée hors `fastmcp`
