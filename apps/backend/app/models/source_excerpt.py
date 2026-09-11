from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.models.source import Source


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class SourceExcerpt(Base):
    __tablename__ = "source_excerpts"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    source_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # Nullable et le reste : imposer un intitule ferait inventer une etiquette
    # la ou il n'y a rien a dire.
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    suggested_by_ai: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Une phrase qui situe le passage : de quoi il parle, dans quel texte, de
    # qui. Un extrait se cite hors de sa page — « ce modele distingue trois
    # composantes » ne nomme ni son auteur ni son objet, et qui le rencontre
    # seul ne peut pas savoir de quoi il traite. Champ separe du verbatim, et
    # jamais concatene dedans : la citation doit rester exactement ce que la
    # source dit, la mise en situation exactement ce qu'elle n'a pas dit.
    context: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Vrai quand l'intitule ou la mise en situation viennent d'un modele. La
    # prose generee cotoie ici du verbatim : ne pas la distinguer laisserait
    # attribuer a la source des mots qu'elle n'a jamais ecrits.
    annotated_by_ai: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Selecteurs d'ancrage (cf. `app/services/excerpt_anchor.py`) : de quoi
    # retrouver le passage dans une page qui a bouge. Nullables et le restent —
    # les extraits saisis sans que le texte de la source soit connu n'en ont
    # pas, et un ancrage invente serait pire que pas d'ancrage.
    anchor_prefix: Mapped[str | None] = mapped_column(Text, nullable=True)
    anchor_suffix: Mapped[str | None] = mapped_column(Text, nullable=True)
    anchor_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Verdict de la derniere relecture. `None` veut dire « jamais relu » : un
    # etat a afficher tel quel, pas a combler par un defaut qui ferait passer
    # l'extrait pour verifie. `verified_text_source` distingue un verdict obtenu
    # contre la page publique d'un verdict obtenu contre un texte fourni.
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verified_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    verified_text_source: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # La relecture ci-dessus demande « ces mots sont-ils dans la page ». Celle-ci
    # demande autre chose : « la source dit-elle ce que l'annotation lui fait
    # dire ». Un passage peut etre retrouve au mot pres et servir a etayer le
    # contraire de ce qu'il affirme.
    #
    # Enumeration fermee a six valeurs, tenue par `services/fidelite.py`. `None`
    # se lit « jamais juge », un etat a afficher tel quel : sans lui, un extrait
    # jamais soumis au juge se lirait comme un extrait que le juge a valide.
    fidelity_verdict: Mapped[str | None] = mapped_column(String(24), nullable=True)
    # Sur quoi le verdict porte : `texte_integral`, `resume_seul` ou
    # `metadonnees_seules`. Un verdict rendu sur un titre n'engage pas ce qu'un
    # verdict rendu sur l'article engage, et ne pas le dire serait mentir par
    # omission.
    fidelity_scope: Mapped[str | None] = mapped_column(String(24), nullable=True)
    fidelity_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # La phrase du juge, dans ses mots. Aucun score numerique ici ni ailleurs :
    # un scalaire invite a la moyenne, et une moyenne de jugements categoriels
    # ne veut rien dire.
    fidelity_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow_naive, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    source: Mapped[Source] = relationship("Source", back_populates="excerpts")

    def __repr__(self) -> str:
        snippet = self.text[:30] if self.text else ""
        return f"<SourceExcerpt {snippet}>"
