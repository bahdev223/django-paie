from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional


@dataclass
class RubriquePaie:
    code: str
    libelle: str
    type: str  # "gain" ou "retenue"
    imposable: bool = True
    cotisable: bool = True

    @property
    def est_gain(self):
        return self.type == "gain"

    @property
    def est_retenue(self):
        return self.type == "retenue"


@dataclass
class LignePaie:
    rubrique_code: str
    base: Decimal
    taux: Decimal
    montant: Decimal

    @property
    def type_rubrique(self):
        return "gain" if self.montant >= 0 else "retenue"

    @property
    def montant_absolu(self):
        return abs(self.montant)


@dataclass
class PeriodePaie:
    mois: int
    annee: int
    date_debut: date
    date_fin: date
    est_cloturee: bool = False

    @property
    def libelle(self):
        return f"{self.mois:02d}/{self.annee}"

    @classmethod
    def from_libelle(cls, libelle: str):
        from datetime import date
        from calendar import monthrange
        mois, annee = libelle.split("/")
        mois, annee = int(mois), int(annee)
        date_debut = date(annee, mois, 1)
        _, dernier_jour = monthrange(annee, mois)
        date_fin = date(annee, mois, dernier_jour)
        return cls(mois=mois, annee=annee, date_debut=date_debut, date_fin=date_fin)


@dataclass
class BulletinPaie:
    employe_id: str
    periode: str
    date_edition: date
    lignes: list = field(default_factory=list)
    est_verrouille: bool = False

    def total_gains(self):
        return sum(l.montant for l in self.lignes if l.montant > 0)

    def total_retenues(self):
        return sum(abs(l.montant) for l in self.lignes if l.montant < 0)

    def net_a_payer(self):
        return self.total_gains() - self.total_retenues()

    def get_ligne(self, rubrique_code):
        for l in self.lignes:
            if l.rubrique_code == rubrique_code:
                return l
        return None

    def to_dict(self):
        return {
            "employe_id": self.employe_id,
            "periode": self.periode,
            "date_edition": self.date_edition.isoformat(),
            "lignes": [
                {
                    "rubrique_code": l.rubrique_code,
                    "base": float(l.base),
                    "taux": float(l.taux),
                    "montant": float(l.montant),
                }
                for l in self.lignes
            ],
            "total_gains": float(self.total_gains()),
            "total_retenues": float(self.total_retenues()),
            "net_a_payer": float(self.net_a_payer()),
            "est_verrouille": self.est_verrouille,
        }
