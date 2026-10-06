"""ClubMember : un licencié du club pour une saison (#1202).

Lu sur la page FFTri du club ou importé d'un fichier pour une saison passée.
`season` suit `core/season` (année de début) : la licence FFTri « 2027 »,
publiée dès septembre 2026, couvre la saison 2026.

Rattaché à une fiche, il fait compter pour le club les résultats de cette
fiche sur la saison (`tcn_count_repository`). Les clés d'identité sont écrites
par l'écouteur, comme celles d'`Athlete`.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, event, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.athlete_identity import athlete_identity_keys
from app.core.database import Base
from app.core.time import utcnow

LINK_AUTO = "auto"
LINK_MANUAL = "manual"
LINK_UNLINKED = "unlinked"
LINK_AMBIGUOUS = "ambiguous"
LINKED = (LINK_AUTO, LINK_MANUAL)

SOURCE_FFTRI = "fftri"
SOURCE_FILE = "file"


class ClubMember(Base):
    __tablename__ = "club_members"
    __table_args__ = (
        UniqueConstraint("season", "licence_id", name="uq_club_member_licence"),
        # Sans numéro de licence, le nom seul identifie une ligne non rattachée ou
        # ambiguë. Une ligne rattachée sans numéro (saison purgée) est identifiée
        # par sa fiche : hors de l'index, l'import de fichier la dédoublonne.
        Index(
            "uq_club_member_identity_without_licence",
            "season", "last_name_key", "first_name_key",
            unique=True,
            postgresql_where=text("licence_id IS NULL AND link_status IN ('unlinked', 'ambiguous')"),
            sqlite_where=text("licence_id IS NULL AND link_status IN ('unlinked', 'ambiguous')"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    season: Mapped[int] = mapped_column(Integer, index=True)
    licence_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    nom: Mapped[str] = mapped_column(String)
    prenom: Mapped[str] = mapped_column(String, default="")
    gender: Mapped[str] = mapped_column(String(1), default="")
    last_name_key: Mapped[str | None] = mapped_column(String, nullable=True)
    first_name_key: Mapped[str | None] = mapped_column(String, nullable=True)
    athlete_id: Mapped[int | None] = mapped_column(
        ForeignKey("athletes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    link_status: Mapped[str] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


@event.listens_for(ClubMember, "before_insert")
@event.listens_for(ClubMember, "before_update")
def _store_identity_keys(_mapper, _connection, member: ClubMember) -> None:
    member.last_name_key, member.first_name_key = athlete_identity_keys(member.nom, member.prenom)
