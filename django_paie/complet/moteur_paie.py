from datetime import date
from decimal import Decimal

from .modeles import BulletinPaie, LignePaie, RubriquePaie, PeriodePaie as PeriodePaieComplet
from .exceptions import (
    ErreurPaie,
    ErreurCalcul,
    ErreurEmployeNonTrouve,
    ErreurContratInvalide,
    ErreurBulletinVerrouille,
    ErreurPeriodeInvalide,
    ConfigurationPaieInvalide,
)
from .regles import ReglesCNSS, ReglesAMO, ReglesITS
from ..conf import paie_settings


class MoteurPaie:

    def __init__(self, stockage=None, rh_connector=None, regles=None, rubriques=None):
        self.stockage = stockage
        self.rh_connector = rh_connector
        self.regles = regles or {}

        self.rubriques = {}
        self._enregistrer_rubriques_defaut()
        if rubriques is not None:
            self.rubriques = {r.code: r for r in rubriques if getattr(r, "actif", True)}

    def _enregistrer_rubriques_defaut(self):
        rubriques_defaut = [
            ("BASE", "Salaire de base", "gain"),
            ("PRIME", "Primes", "gain"),
            ("HSUP", "Heures supplémentaires", "gain"),
            ("AVANTAGE", "Avantages en nature", "gain"),
            ("INDEMNITE", "Indemnités", "gain"),
            ("RAPPEL", "Rappels", "gain"),
            ("CONGE", "Congés payés", "gain"),
            ("REGULARISATION", "Régularisations", "gain"),
            ("ABSENCE", "Absences", "retenue"),
            ("PRET_AVANCE", "Prêts et avances récupérables", "retenue", False, False),
            ("RETENUE", "Retenues personnalisées", "retenue", False, False),
            ("CNSS", "Cotisation CNSS", "retenue", False, True),
            ("AMO", "Cotisation AMO", "retenue", False, True),
            ("ITS", "Impôt sur le traitement et le salaire", "retenue", False, False),
        ]
        for rub in rubriques_defaut:
            self.rubriques[rub[0]] = RubriquePaie(
                code=rub[0], libelle=rub[1], type=rub[2],
                imposable=rub[3] if len(rub) > 3 else True,
                cotisable=rub[4] if len(rub) > 4 else True,
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
            mois, annee_str = periode.split("/")
        except Exception:
            raise ErreurPeriodeInvalide(f"Période invalide : {periode}")

        try:
            periode_obj = PeriodePaieComplet.from_libelle(periode)
        except Exception:
            raise ErreurPeriodeInvalide(f"Période invalide : {periode}")

        salaire_base = self._salaire_contractuel(contrat)
        absences = self.rh_connector.get_absences_mois(
            employe_id, int(annee_str), int(mois)
        )
        heures_travaillees = self.rh_connector.get_heures_mois(
            employe_id, int(annee_str), int(mois)
        )
        jours_ouvres = self.rh_connector.get_jours_ouvres(
            employe_id, int(annee_str), int(mois)
        )
        variables = self.rh_connector.get_variables_mois(
            employe_id, int(annee_str), int(mois)
        )
        variables = variables or {}
        if variables.get("jours_absence") is not None:
            absences = variables["jours_absence"]

        retenue_absence = salaire_base - self._ajuster_pour_absence(
            salaire_base, absences, jours_ouvres
        )

        bulletin = BulletinPaie(
            employe_id=employe_id,
            periode=periode,
            date_edition=date.today(),
        )

        self._ajouter_ligne(bulletin, "BASE", salaire_base, Decimal("1"), salaire_base)
        self._ajouter_variable(bulletin, "PRIME", variables.get("primes", 0))
        self._ajouter_variable(bulletin, "INDEMNITE", variables.get("indemnites", 0))
        self._ajouter_variable(bulletin, "AVANTAGE", variables.get("avantages_nature", 0))
        self._ajouter_variable(bulletin, "RAPPEL", variables.get("rappels", 0))
        self._ajouter_variable(bulletin, "CONGE", variables.get("conges_payes", 0))

        heures_sup = Decimal(str(variables.get("heures_supplementaires", 0)))
        if heures_sup > 0:
            heures_reference = Decimal(str(
                getattr(contrat, "duree_heures_mois", None)
                or paie_settings.HEURES_MENSUELLES_DEFAUT
            ))
            if heures_reference <= 0:
                heures_reference = Decimal(str(paie_settings.HEURES_MENSUELLES_DEFAUT))
            taux_horaire = salaire_base / heures_reference
            majoration = Decimal(str(variables.get("taux_majoration_heures", "1.25")))
            montant_hsup = (heures_sup * taux_horaire * majoration).quantize(Decimal("1"))
            self._ajouter_ligne(bulletin, "HSUP", taux_horaire, majoration, montant_hsup)

        if retenue_absence > 0:
            self._ajouter_ligne(
                bulletin, "ABSENCE", salaire_base, Decimal(str(absences)),
                -retenue_absence,
            )

        regularisation = Decimal(str(variables.get("regularisations", 0)))
        if regularisation:
            self._ajouter_ligne(
                bulletin, "REGULARISATION", abs(regularisation), Decimal("1"),
                regularisation,
            )
        self._ajouter_variable(
            bulletin, "PRET_AVANCE", variables.get("prets_avances", 0), retenue=True
        )
        self._ajouter_variable(
            bulletin, "RETENUE", variables.get("retenues_personnalisees", 0),
            retenue=True,
        )
        for autre in variables.get("autres", []) or []:
            montant = Decimal(str(autre.get("montant", 0)))
            code = autre.get("code")
            if code and montant and code in self.rubriques:
                if self.rubriques[code].est_retenue:
                    montant = -abs(montant)
                self._ajouter_ligne(
                    bulletin, code, Decimal(str(autre.get("base", abs(montant)))),
                    Decimal(str(autre.get("taux", 1))), montant,
                )

        salaire_brut = sum(
            ligne.montant for ligne in bulletin.lignes
            if self.rubriques.get(ligne.rubrique_code)
            and self.rubriques[ligne.rubrique_code].cotisable
        )
        salaire_imposable_brut = sum(
            ligne.montant for ligne in bulletin.lignes
            if self.rubriques.get(ligne.rubrique_code)
            and self.rubriques[ligne.rubrique_code].imposable
        )
        salaire_brut = max(salaire_brut, Decimal("0"))
        salaire_imposable_brut = max(salaire_imposable_brut, Decimal("0"))

        manquantes = [code for code in ("CNSS", "AMO", "ITS") if code not in self.regles]
        if manquantes:
            raise ConfigurationPaieInvalide(
                f"Règles manquantes : {', '.join(manquantes)}"
            )

        regles_cnss = self.regles["CNSS"]
        regles_amo = self.regles["AMO"]
        regles_its = self.regles["ITS"]

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
        salaire_imposable = salaire_imposable_brut - total_retenues_sociales

        its = regles_its.calculer_impot(salaire_imposable)
        bulletin.lignes.append(
            LignePaie(rubrique_code="ITS", base=Decimal(str(its["base"])),
                      taux=Decimal(str(its["taux_effectif"])), montant=Decimal(str(-its["montant"])))
        )

        return bulletin

    def _ajouter_ligne(self, bulletin, code, base, taux, montant):
        if code not in self.rubriques or not montant:
            return
        bulletin.lignes.append(
            LignePaie(
                rubrique_code=code,
                base=Decimal(str(base)),
                taux=Decimal(str(taux)),
                montant=Decimal(str(montant)),
            )
        )

    def _ajouter_variable(self, bulletin, code, montant, retenue=False):
        montant = Decimal(str(montant or 0))
        if montant:
            self._ajouter_ligne(
                bulletin, code, abs(montant), Decimal("1"),
                -abs(montant) if retenue else montant,
            )

    def _calculer_bulletin_standalone(self, employe_id: str, periode: str) -> BulletinPaie:
        try:
            periode_obj = PeriodePaieComplet.from_libelle(periode)
        except Exception:
            raise ErreurPeriodeInvalide(f"Période invalide : {periode}")

        return BulletinPaie(
            employe_id=employe_id,
            periode=periode,
            date_edition=date.today(),
        )

    def _salaire_contractuel(self, contrat):
        for champ in (
            "salaire_base",
            "salaire_brut_mensuel",
            "salaire_mensuel",
            "salaire_contractuel",
        ):
            valeur = getattr(contrat, champ, None)
            if valeur is not None:
                return Decimal(str(valeur))
        raise ErreurContratInvalide(
            "Le contrat actif ne fournit aucun salaire contractuel reconnu."
        )

    def _ajuster_pour_absence(self, salaire_base, jours_absence, jours_ouvres):
        if jours_absence <= 0:
            return salaire_base
        jours_ouvres = Decimal(str(
            jours_ouvres or paie_settings.JOURS_OUVRES_DEFAUT
        ))
        if jours_ouvres <= 0:
            raise ErreurCalcul("Le nombre de jours ouvrés doit être supérieur à zéro.")
        taux_journalier = salaire_base / jours_ouvres
        retenue = taux_journalier * Decimal(str(jours_absence))
        return (salaire_base - retenue).quantize(Decimal("1"))

    def verrouiller_bulletin(self, bulletin):
        bulletin.est_verrouille = True
        return bulletin
