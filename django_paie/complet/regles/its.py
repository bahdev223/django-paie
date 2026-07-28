from decimal import Decimal


class ReglesITS:
    ABATTEMENT_FORFAITAIRE = Decimal("0.10")
    DECOTE_SEUIL = Decimal("100000")
    DECOTE_MONTANT = Decimal("10000")

    BAREMES = [
        (Decimal("51000"), Decimal("0")),
        (Decimal("86000"), Decimal("0.03")),
        (Decimal("149000"), Decimal("0.10")),
        (Decimal("262000"), Decimal("0.15")),
        (Decimal("400000"), Decimal("0.20")),
        (Decimal("700000"), Decimal("0.25")),
        (None, Decimal("0.30")),
    ]

    def __init__(self, parametres=None):
        parametres = parametres or {}
        self.ABATTEMENT_FORFAITAIRE = Decimal(
            str(parametres.get("abattement_forfaitaire", self.ABATTEMENT_FORFAITAIRE))
        )
        self.DECOTE_SEUIL = Decimal(
            str(parametres.get("decote_seuil", self.DECOTE_SEUIL))
        )
        self.DECOTE_MONTANT = Decimal(
            str(parametres.get("decote_montant", self.DECOTE_MONTANT))
        )
        baremes = parametres.get("baremes")
        if baremes:
            self.BAREMES = [
                (
                    Decimal(str(item["seuil"])) if item.get("seuil") is not None else None,
                    Decimal(str(item["taux"])),
                )
                for item in baremes
            ]

    def calculer_impot(self, salaire_imposable):
        base = Decimal(str(salaire_imposable))
        abattement = (base * self.ABATTEMENT_FORFAITAIRE).quantize(Decimal("1"))
        base_imposable = base - abattement

        if base_imposable <= 0:
            return {"base": int(base), "montant": 0, "taux_effectif": 0.0}

        impot = Decimal("0")
        tranche_inferieure = Decimal("0")

        for seuil, taux in self.BAREMES:
            if seuil is None:
                tranche = base_imposable - tranche_inferieure
            else:
                if base_imposable <= tranche_inferieure:
                    break
                tranche = min(base_imposable, seuil) - tranche_inferieure
                tranche_inferieure = seuil

            if tranche > 0:
                impot += (tranche * taux).quantize(Decimal("1"))

        if base_imposable <= self.DECOTE_SEUIL:
            impot = max(Decimal("0"), impot - self.DECOTE_MONTANT)

        taux_effectif = float((impot / base_imposable).quantize(Decimal("0.0001"))) if base_imposable > 0 else 0

        return {
            "base": int(base),
            "abattement": int(abattement),
            "base_imposable": int(base_imposable),
            "montant": int(impot),
            "taux_effectif": taux_effectif,
        }
