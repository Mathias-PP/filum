from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.models.source_excerpt import SourceExcerpt


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


#: Dimension des vecteurs stockes.
#:
#: `gemini-embedding-001` rend 3072 dimensions et supporte la troncature MRL a
#: 1536 ou 768 : les premieres dimensions portent l'essentiel du signal, on
#: coupe et on renormalise. 768 est le compromis retenu : quatre fois moins de
#: stockage que 3072, pour une perte de rappel marginale a notre echelle.
#:
#: Changer ce nombre invalide les vecteurs existants. C'est precisement ce que
#: la table separee rend supportable : on ecrit les nouveaux a cote des
#: anciens, puis on bascule.
EMBEDDING_DIM = 768

#: Le type `vector` n'existe pas sous SQLite, ou tournent les tests via
#: `Base.metadata.create_all`. La variante garde le schema creable des deux
#: cotes ; aucune requete de similarite n'est possible sous SQLite, et c'est
#: assume : ce qui se teste sans Postgres, c'est le calcul du vecteur, pas la
#: recherche.
EMBEDDING_TYPE = Vector(EMBEDDING_DIM).with_variant(sa.Text(), "sqlite")


class ExcerptEmbedding(Base):
    """Vecteur d'un extrait, dans une table a part de `source_excerpts`.

    Une colonne sur `source_excerpts` aurait ete plus courte a ecrire et bien
    plus chere a faire evoluer. Trois raisons de la separation :

    - changer de modele d'embedding se fait en ecrivant la nouvelle serie a
      cote de l'ancienne, sans verrou sur la table chaude ni fenetre ou la
      recherche ne repond plus ;
    - un extrait sans vecteur est l'etat normal (jamais indexe, ou modifie
      depuis), et se lit ici comme une absence de ligne plutot que comme un
      NULL a interpreter ;
    - la table des extraits est lue a chaque affichage de fiche. Lui coller
      trois kilo-octets par ligne alourdirait des requetes qui n'ont que faire
      des vecteurs.
    """

    __tablename__ = "excerpt_embeddings"
    __table_args__ = (
        # Un extrait a au plus un vecteur par modele. Pendant une bascule, il
        # en a donc deux, ce qui est exactement l'etat recherche.
        UniqueConstraint("excerpt_id", "model", name="uq_excerpt_embedding_model"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    excerpt_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("source_excerpts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    model: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    dim: Mapped[int] = mapped_column(Integer, nullable=False)
    # SHA-256 du texte reellement soumis au modele. C'est lui qui dit si un
    # vecteur est perime : l'extrait a pu etre reformule, son intitule change,
    # sa mise en situation reecrite. Comparer les dates ne suffirait pas, une
    # ligne touchee n'est pas une ligne dont le sens a bouge.
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(EMBEDDING_TYPE, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow_naive, nullable=False)

    excerpt: Mapped[SourceExcerpt] = relationship("SourceExcerpt")

    def __repr__(self) -> str:
        return f"<ExcerptEmbedding {self.excerpt_id} {self.model}>"
