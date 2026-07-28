from decimal import Decimal


class ReglesAMO:
    TAUX_SALARIAL = Decimal("0.05")
    TAUX_PATRONAL = Decimal("0.06")

    def calculer_cotisation_salariale(self, salaire_brut):
        base = Decimal(str(salaire_brut))
        montant = (base * self.TAUX_SALARIAL).quantize(Decimal("1"))
        return {
            "base": int(base),
            "taux": float(self.TAUX_SALARIAL),
            "montant": int(montant),
            "type": "salariale",
        }

    def calculer_cotisation_patronale(self, salaire_brut):
        base = Decimal(str(salaire_brut))
        montant = (base * self.TAUX_PATRONAL).quantize(Decimal("1"))
        return {
            "base": int(base),
            "taux": float(self.TAUX_PATRONAL),
            "montant": int(montant),
            "type": "patronale",
        }
