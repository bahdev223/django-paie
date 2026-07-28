from datetime import date
from decimal import Decimal
from typing import Optional

from .modeles import BulletinPaie, LignePaie, RubriquePaie, PeriodePaie as PeriodePaieComplet
from .exceptions import (
    ErreurPaie,
    ErreurCalcul,
    ErreurEmployeNonTrouve,
    ErreurContratInvalide,
    ErreurBulletinVerrouille,
    ErreurPeriodeInvalide,
)
from .regles import ReglesCNSS, ReglesAMO, ReglesITS


class MoteurPaie:
    NB_JOURS_TRAVAILLES = 22

    def __init__(self, stockage=None, rh_connector=None):
        self.stockage = stockage
        self.rh_connector = rh_connector

        self.rubriques = {}
        self._enregistrer_rubriques_defaut()

    def _enregistrer_rubriques_defaut(self):
        rubriques_defaut = [
            ("BASE", "Salaire de base", "gain"),
            ("PRIME", "Primes", "gain"),
            ("HSUP", "Heures supplémentaires", "gain"),
            ("AVANTAGE", "Avantages en nature", "gain"),
            ("ABSENCE", "Absences", "retenue"),
            ("CNSS", "Cotisation CNSS", "retenue", False, True),
            ("AMO", "Cotisation AMO", "retenue", False, True),
            ("ITS", "Impôt sur le traitement et le salaire", "retenue", False, False),
            ("NET", "Net à payer", "gain"),
        ]
        for rub in rubriques_defaut:
            code = rub[0]
            libelle = rub[1]
            typ = rub[2]
            imposable = rub[3] if len(rub) > 3 else True
            cotisable = rub[4] if len(rub) > 4 else True
            self.rubriques[code] = RubriquePaie(
                code=code, libelle=libelle, type=typ,
                imposable=imposable, cotisable=cotisable,
            )

    def calculer_bulletin(self, employe_id: str, periode: str) -> BulletinPaie:
        if not self.rh_connector:
            return self._calculer_bulletin_standalone(employe_id, periode)

        try:
            employe = self.rh_connector.get_employe(employe_id)
        except Exception as e:
            raise ErreurEmployeNonTrouve(f"Employé {employe_id} introuvable : {e}")

        contrat = self.rh_connector.get_contrat_actif(employe_id)
        if not contrat:
            raise ErreurContratInvalide(f"Aucun contrat actif pour {employe_id}")

        try:
            mois, annee = periode.split("/")
            periode_obj = PeriodePaieComplet.from_libelle(periode)
        except Exception:
            raise ErreurPeriodeInvalide(f"Période invalide : {periode}")

        bulletin = BulletinPaie(
            employe_id=employe_id,
            periode=periode,
            date_edition=date.today(),
        )

        salaire_base = Decimal(str(getattr(contrat, "salaire_base", 0)))
        absences = self.rh_connector.get_absences_mois(employe_id, int(annee), int(mois))
        heures_travaillees = self.rh_connector.get_heures_mois(employe_id, int(annee), int(mois))

        salaire_ajuste = self._ajuster_pour_absence(salaire_base, absences)

        bulletin.lignes.append(
            LignePaie(rubrique_code="BASE", base=salaire_ajuste, taux=Decimal("1"), montant=salaire_ajuste)
        )

        salaire_brut = salaire_ajuste
        regles_cnss = ReglesCNSS()
        regles_amo = ReglesAMO()
        regles_its = ReglesITS()

        cnss = regles_cnss.calculer_cotisation_salariale(salaire_brut)
        bulletin.lignes.append(
            LignePaie(rubrique_code="CNSS", base=Decimal(str(cnss["base"])),
                      taux=Decimal(str(cnss["taux"])), montant=Decimal(str(-cnss["montant"])))
        )

        amo = regles_amo.calculer_cotisation_salariale(salaire_brut)
        bulletin.lignes.append(
            LignePaie(rubrique_code="AMO", base=Decimal(str(amo["base"])),
                      taux=Decimal(str(amo["taux"])), montant=Decimal(str(-amo["montant"])))
        )

        total_retenues_sociales = Decimal(str(cnss["montant"])) + Decimal(str(amo["montant"]))
        salaire_imposable = salaire_brut - total_retenues_sociales

        its = regles_its.calculer_impot(salaire_imposable)
        bulletin.lignes.append(
            LignePaie(rubrique_code="ITS", base=Decimal(str(its["base"])),
                      taux=Decimal(str(its["taux_effectif"])), montant=Decimal(str(-its["montant"])))
        )

        salaire_net = salaire_brut - total_retenues_sociales - Decimal(str(its["montant"]))
        bulletin.lignes.append(
            LignePaie(rubrique_code="NET", base=salaire_net, taux=Decimal("1"), montant=salaire_net)
        )

        return bulletin

    def _calculer_bulletin_standalone(self, employe_id: str, periode: str) -> BulletinPaie:
        try:
            periode_obj = PeriodePaieComplet.from_libelle(periode)
        except Exception:
            raise ErreurPeriodeInvalide(f"Période invalide : {periode}")

        bulletin = BulletinPaie(
            employe_id=employe_id,
            periode=periode,
            date_edition=date.today(),
        )
        bulletin.lignes.append(
            LignePaie(rubrique_code="BASE", base=Decimal("0"), taux=Decimal("1"), montant=Decimal("0"))
        )
        bulletin.lignes.append(
            LignePaie(rubrique_code="NET", base=Decimal("0"), taux=Decimal("1"), montant=Decimal("0"))
        )
        return bulletin

    def _ajuster_pour_absence(self, salaire_base, jours_absence):
        if jours_absence <= 0:
            return salaire_base
        taux_journalier = salaire_base / Decimal(str(self.NB_JOURS_TRAVAILLES))
        retenue = taux_journalier * Decimal(str(jours_absence))
        return (salaire_base - retenue).quantize(Decimal("1"))

    def verrouiller_bulletin(self, bulletin):
        bulletin.est_verrouille = True
        return bulletin
