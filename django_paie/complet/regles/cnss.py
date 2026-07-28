from decimal import Decimal


class ReglesCNSS:
    PLAFOND = Decimal("350000")
    TAUX_SALARIAL = Decimal("0.036")
    TAUX_PATRONAL = Decimal("0.072")

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
