from decimal import Decimal


class ReglesCNSS:
    PLAFOND = Decimal("350000")
    TAUX_SALARIAL = Decimal("0.036")
    TAUX_PATRONAL = Decimal("0.072")

    def __init__(self, taux_salarial=None, taux_patronal=None, plafond=None):
        self.TAUX_SALARIAL = Decimal(str(taux_salarial)) if taux_salarial is not None else self.TAUX_SALARIAL
        self.TAUX_PATRONAL = Decimal(str(taux_patronal)) if taux_patronal is not None else self.TAUX_PATRONAL
        self.PLAFOND = Decimal(str(plafond)) if plafond is not None else self.PLAFOND

    def calculer_cotisation_salariale(self, salaire_brut):
        base = min(Decimal(str(salaire_brut)), self.PLAFOND)
        montant = (base * self.TAUX_SALARIAL).quantize(Decimal("1"))
        return {
            "base": int(base),
            "taux": float(self.TAUX_SALARIAL),
            "montant": int(montant),
            "type": "salariale",
        }

    def calculer_cotisation_patronale(self, salaire_brut):
        base = min(Decimal(str(salaire_brut)), self.PLAFOND)
        montant = (base * self.TAUX_PATRONAL).quantize(Decimal("1"))
        return {
            "base": int(base),
            "taux": float(self.TAUX_PATRONAL),
            "montant": int(montant),
            "type": "patronale",
        }
