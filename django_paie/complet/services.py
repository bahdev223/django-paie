from decimal import Decimal
from .regles import ReglesCNSS, ReglesAMO, ReglesITS


class CotisationService:
    def __init__(self, date_calcul=None, entreprise_id=""):
        self.cnss = ReglesCNSS()
        self.amo = ReglesAMO()
        self.its = ReglesITS()
        if date_calcul is not None:
            self._charger_regles(date_calcul, entreprise_id)

    def _charger_regles(self, date_calcul, entreprise_id):
        from ..models import ReglePaie
        for organisme in ("CNSS", "AMO", "ITS"):
            regle = ReglePaie.pour_date(
                organisme, date_calcul, entreprise_id=entreprise_id
            )
            if not regle:
                continue
            if organisme == "CNSS":
                self.cnss = ReglesCNSS(
                    regle.taux_salarial, regle.taux_patronal, regle.plafond
                )
            elif organisme == "AMO":
                self.amo = ReglesAMO(
                    regle.taux_salarial, regle.taux_patronal, regle.plafond
                )
            else:
                self.its = ReglesITS(regle.parametres)

    def calculer_toutes_cotisations(self, salaire_brut):
        return {
            "cnss": self.cnss.calculer_cotisation_salariale(salaire_brut),
            "amo": self.amo.calculer_cotisation_salariale(salaire_brut),
            "its": self.its.calculer_impot(salaire_brut),
        }

    def calculer_charges_patronales(self, salaire_brut):
        return {
            "cnss": self.cnss.calculer_cotisation_patronale(salaire_brut),
            "amo": self.amo.calculer_cotisation_patronale(salaire_brut),
        }
