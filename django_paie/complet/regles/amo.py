from decimal import Decimal


class ReglesAMO:
    TAUX_SALARIAL = Decimal("0.05")
    TAUX_PATRONAL = Decimal("0.06")

    def __init__(self, taux_salarial=None, taux_patronal=None, plafond=None):
        self.TAUX_SALARIAL = Decimal(str(taux_salarial)) if taux_salarial is not None else self.TAUX_SALARIAL
        self.TAUX_PATRONAL = Decimal(str(taux_patronal)) if taux_patronal is not None else self.TAUX_PATRONAL
        self.PLAFOND = Decimal(str(plafond)) if plafond is not None else None

    def calculer_cotisation_salariale(self, salaire_brut):
        base = Decimal(str(salaire_brut))
        if self.PLAFOND is not None:
            base = min(base, self.PLAFOND)
        montant = (base * self.TAUX_SALARIAL).quantize(Decimal("1"))
        return {
            "base": int(base),
            "taux": float(self.TAUX_SALARIAL),
            "montant": int(montant),
            "type": "salariale",
        }

    def calculer_cotisation_patronale(self, salaire_brut):
        base = Decimal(str(salaire_brut))
        if self.PLAFOND is not None:
            base = min(base, self.PLAFOND)
        montant = (base * self.TAUX_PATRONAL).quantize(Decimal("1"))
        return {
            "base": int(base),
            "taux": float(self.TAUX_PATRONAL),
            "montant": int(montant),
            "type": "patronale",
        }
