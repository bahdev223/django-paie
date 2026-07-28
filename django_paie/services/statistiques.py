from datetime import date
from decimal import Decimal
from django.db.models import Sum, Count, Q
from ..models import EcheanceSalariale, PaiementSalarial
from ..conf import paie_settings


class StatistiquesPaieService:
    def __init__(self, entreprise_id=""):
        self.entreprise_id = entreprise_id

    def _base_qs(self):
        qs = EcheanceSalariale.objects.all()
        if self.entreprise_id:
            qs = qs.filter(entreprise_id=self.entreprise_id)
        return qs

    def resume_periode(self, periode):
        try:
            mois, annee = periode.split("/")
            mois, annee = int(mois), int(annee)
        except (ValueError, AttributeError):
            raise ValueError(f"Période invalide : {periode}")

        qs = self._base_qs().filter(mois=mois, annee=annee).exclude(statut="ANNULE")

        net_values = list(qs.values_list("montant_net", flat=True))
        paye_values = list(qs.values_list("montant_paye", flat=True))
        total_du = sum(net_values)
        total_paye = sum(paye_values)

        echeances = list(qs)
        employes_payes = sum(1 for e in echeances if e.statut == "PAYE" or e.statut == "PAYE_EN_AVANCE")
        employes_non_payes = sum(1 for e in echeances if e.statut == "A_PAYER" or e.statut == "EN_RETARD")
        paiements_partiels = sum(1 for e in echeances if e.statut == "PARTIELLEMENT_PAYE")

        paiements_qs = PaiementSalarial.objects.filter(
            echeance__in=qs, statut="VALIDE"
        )
        arrieres = paiements_qs.filter(type_paiement="ARRIERE").aggregate(
            total=Sum("montant")
        )["total"] or 0
        avances = paiements_qs.filter(type_paiement="AVANCE").aggregate(
            total=Sum("montant")
        )["total"] or 0

        return {
            "periode": periode,
            "nombre_employes": qs.count(),
            "montant_du": total_du,
            "montant_paye": total_paye,
            "reste_a_payer": total_du - total_paye,
            "employes_payes": employes_payes,
            "employes_non_payes": employes_non_payes,
            "paiements_partiels": paiements_partiels,
            "montant_arrieres": arrieres,
            "montant_avances": avances,
        }

    def resume_annuel(self, annee=None):
        if annee is None:
            annee = date.today().year

        qs = self._base_qs().filter(annee=annee).exclude(statut="ANNULE")

        total_du = qs.aggregate(total=Sum("montant_net"))["total"] or 0
        total_paye = qs.aggregate(total=Sum("montant_paye"))["total"] or 0

        return {
            "annee": annee,
            "total_echeances": qs.count(),
            "total_montant_du": total_du,
            "total_montant_paye": total_paye,
            "reste_global": total_du - total_paye,
            "a_payer": qs.filter(statut="A_PAYER").count(),
            "paye": qs.filter(statut="PAYE").count(),
            "partiel": qs.filter(statut="PARTIELLEMENT_PAYE").count(),
            "en_retard": qs.filter(statut="EN_RETARD").count(),
            "trop_percu": qs.filter(statut="TROPPERCU").count(),
        }

    def evolution_mensuelle(self, annee=None):
        if annee is None:
            annee = date.today().year

        resultats = []
        for m in range(1, 13):
            qs = self._base_qs().filter(mois=m, annee=annee).exclude(statut="ANNULE")
            paye = qs.aggregate(total=Sum("montant_paye"))["total"] or 0
            du = qs.aggregate(total=Sum("montant_net"))["total"] or 0
            resultats.append({
                "mois": m,
                "libelle": f"{m:02d}/{annee}",
                "montant_du": du,
                "montant_paye": paye,
                "reste": du - paye,
            })
        return resultats

    def arrieres(self):
        qs = self._base_qs().filter(
            statut__in=["EN_RETARD", "PARTIELLEMENT_PAYE"]
        ).exclude(statut="ANNULE")

        montant_total = sum(e.reste_a_payer for e in qs)
        employes_ids = set(e.employe_object_id for e in qs)

        plus_ancien = qs.order_by("annee", "mois").first()

        details = []
        for e in qs:
            if e.reste_a_payer > 0:
                details.append({
                    "employe_id": e.employe_object_id,
                    "periode": e.periode,
                    "montant_du": e.montant_net,
                    "montant_paye": e.montant_paye,
                    "reste": e.reste_a_payer,
                })

        return {
            "nombre_echeances": qs.count(),
            "nombre_employes": len(employes_ids),
            "montant_total": montant_total,
            "plus_ancien": plus_ancien.periode if plus_ancien else None,
            "details": details,
        }

    def avances(self):
        paiements = PaiementSalarial.objects.filter(
            echeance__in=self._base_qs(),
            type_paiement="AVANCE",
            statut="VALIDE",
        )

        total = paiements.aggregate(total=Sum("montant"))["total"] or 0
        employes_ids = set(
            p.echeance.employe_object_id for p in paiements.select_related("echeance")
        )
        nb_employes = len(employes_ids)
        moyenne = int(total / nb_employes) if nb_employes > 0 else 0

        return {
            "montant_total": total,
            "nombre_employes": nb_employes,
            "moyenne": moyenne,
            "nombre_paiements": paiements.count(),
        }

    def masse_salariale(self, periode):
        try:
            mois, annee = periode.split("/")
            mois, annee = int(mois), int(annee)
        except (ValueError, AttributeError):
            raise ValueError(f"Période invalide : {periode}")

        qs = self._base_qs().filter(mois=mois, annee=annee, mode="COMPLET").exclude(statut="ANNULE")

        total_brut = qs.aggregate(total=Sum("montant_brut"))["total"] or 0
        total_net = qs.aggregate(total=Sum("montant_net"))["total"] or 0
        total_paye = qs.aggregate(total=Sum("montant_paye"))["total"] or 0

        return {
            "periode": periode,
            "nombre_bulletins": qs.count(),
            "masse_brute": total_brut,
            "masse_nette": total_net,
            "total_paye": total_paye,
            "reste_a_payer": total_net - total_paye,
            "charges_salariales": total_brut - total_net,
        }

    def cout_employeur(self, periode):
        masse = self.masse_salariale(periode)
        charges_patronales_cnss = int(masse["masse_brute"] * 0.072)
        charges_patronales_amo = int(masse["masse_brute"] * 0.06)
        total_charges = charges_patronales_cnss + charges_patronales_amo

        return {
            "periode": periode,
            "salaires_nets": masse["masse_nette"],
            "charges_salariales": masse["charges_salariales"],
            "charges_patronales_cnss": charges_patronales_cnss,
            "charges_patronales_amo": charges_patronales_amo,
            "total_charges_patronales": total_charges,
            "cout_total": masse["masse_brute"] + total_charges,
        }

    def alertes(self):
        today = date.today()
        alertes = []

        non_payes = self._base_qs().filter(statut="A_PAYER").exclude(statut="ANNULE").count()
        if non_payes > 0:
            alertes.append({
                "type": "warning",
                "message": f"{non_payes} employé(s) ne sont pas encore payé(s).",
            })

        en_retard = self._base_qs().filter(statut="EN_RETARD").exclude(statut="ANNULE").count()
        if en_retard > 0:
            alertes.append({
                "type": "danger",
                "message": f"{en_retard} échéance(s) sont en retard.",
            })

        partiels = self._base_qs().filter(statut="PARTIELLEMENT_PAYE").exclude(statut="ANNULE").count()
        if partiels > 0:
            alertes.append({
                "type": "info",
                "message": f"{partiels} paiement(s) partiel(s) en cours.",
            })

        trop_percu = self._base_qs().filter(statut="TROPPERCU").exclude(statut="ANNULE").count()
        if trop_percu > 0:
            alertes.append({
                "type": "danger",
                "message": f"{trop_percu} échéance(s) ont un trop-perçu.",
            })

        non_cloture = self._base_qs().filter(date_cloture__isnull=True).exclude(statut="ANNULE").count()
        if non_cloture > 150:
            alertes.append({
                "type": "info",
                "message": f"La période en cours n'est pas clôturée.",
            })

        return alertes

    def repartition_salaires(self, periode):
        try:
            mois, annee = periode.split("/")
            mois, annee = int(mois), int(annee)
        except (ValueError, AttributeError):
            raise ValueError(f"Période invalide : {periode}")

        nets = list(
            self._base_qs()
            .filter(mois=mois, annee=annee)
            .exclude(statut="ANNULE")
            .values_list("montant_net", flat=True)
        )

        if not nets:
            return {}

        nets_sorted = sorted(nets)
        n = len(nets_sorted)
        mediane = nets_sorted[n // 2] if n % 2 else (nets_sorted[n // 2 - 1] + nets_sorted[n // 2]) // 2

        return {
            "nombre_employes": n,
            "moyen": sum(nets) // n,
            "median": mediane,
            "minimum": min(nets),
            "maximum": max(nets),
            "tranches": {
                "moins_100k": sum(1 for v in nets if v < 100000),
                "entre_100k_250k": sum(1 for v in nets if 100000 <= v < 250000),
                "entre_250k_500k": sum(1 for v in nets if 250000 <= v < 500000),
                "plus_500k": sum(1 for v in nets if v >= 500000),
            },
        }
