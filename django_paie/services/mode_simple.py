from datetime import date, datetime
from decimal import Decimal
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from ..models import EcheanceSalariale, PaiementSalarial, PeriodePaie
from ..utils import extraire_mois_annee


class ModeSimpleService:
    def __init__(self, entreprise_id=""):
        self.entreprise_id = entreprise_id

    def creer_echeance(self, employe, periode, montant_brut, montant_net=None, date_echeance=None):
        if montant_net is None:
            montant_net = montant_brut
        if date_echeance is None:
            today = date.today()
            date_echeance = date(today.year, today.month, 5)

        mois, annee = extraire_mois_annee(periode)
        periode_obj = PeriodePaie.from_libelle(periode, entreprise_id=self.entreprise_id)
        ct = ContentType.objects.get_for_model(employe)

        echeance, created = EcheanceSalariale.objects.update_or_create(
            employe_content_type=ct,
            employe_object_id=str(employe.pk),
            mois=mois,
            annee=annee,
            entreprise_id=self.entreprise_id,
            defaults={
                "date_debut": periode_obj.date_debut,
                "date_fin": periode_obj.date_fin,
                "date_echeance": date_echeance,
                "montant_brut": montant_brut,
                "montant_net": montant_net,
                "mode": "SIMPLE",
            },
        )
        return echeance

    def enregistrer_paiement(self, echeance_id, montant, date_paiement=None, type_paiement="PAIEMENT", notes=""):
        if date_paiement is None:
            date_paiement = date.today()

        with transaction.atomic():
            echeance = (
                EcheanceSalariale.objects
                .select_for_update()
                .get(pk=echeance_id)
            )

            if montant <= 0:
                raise ValueError("Le montant du paiement doit être positif.")

            reste = echeance.reste_a_payer
            if reste <= 0 and type_paiement not in ("AVANCE", "REGULARISATION", "ANNULATION"):
                raise ValueError(f"Cette échéance est déjà payée. Reste à payer : {reste}")

            if type_paiement == "AVANCE":
                mois_concerne, annee_concerne = self._periode_suivante(echeance.mois, echeance.annee)
            else:
                mois_concerne, annee_concerne = echeance.mois, echeance.annee

            paiement = PaiementSalarial.objects.create(
                echeance=echeance,
                montant=montant,
                type_paiement=self._detecter_type_paiement(echeance, date_paiement, mois_concerne, annee_concerne),
                date_paiement=date_paiement,
                mois_concerne=mois_concerne,
                annee_concerne=annee_concerne,
                notes=notes,
            )
        return paiement

    def _periode_suivante(self, mois, annee):
        if mois == 12:
            return 1, annee + 1
        return mois + 1, annee

    def _detecter_type_paiement(self, echeance, date_paiement, mois_concerne, annee_concerne):
        if (annee_concerne, mois_concerne) > (echeance.annee, echeance.mois):
            return "AVANCE"
        periode_fin = echeance.date_fin
        if date_paiement > periode_fin:
            return "ARRIERE"
        return "PAIEMENT"

    def payer_plusieurs_mois(self, employe, montant, mois_debut, mois_fin, date_paiement=None):
        if date_paiement is None:
            date_paiement = date.today()

        ct = ContentType.objects.get_for_model(employe)
        m_debut, a_debut = extraire_mois_annee(mois_debut)
        m_fin, a_fin = extraire_mois_annee(mois_fin)

        echeances = EcheanceSalariale.objects.filter(
            employe_content_type=ct,
            employe_object_id=str(employe.pk),
            entreprise_id=self.entreprise_id,
            annee__gte=a_debut,
            annee__lte=a_fin,
        ).order_by("annee", "mois")

        montant_restant = Decimal(str(montant))
        paiements = []

        with transaction.atomic():
            for echeance in echeances:
                if (echeance.annee, echeance.mois) < (a_debut, m_debut):
                    continue
                if (echeance.annee, echeance.mois) > (a_fin, m_fin):
                    continue

                echeance = EcheanceSalariale.objects.select_for_update().get(pk=echeance.pk)
                reste = echeance.reste_a_payer
                if reste <= 0:
                    continue
                a_payer = min(montant_restant, reste)
                if a_payer <= 0:
                    continue

                paiement = PaiementSalarial.objects.create(
                    echeance=echeance,
                    montant=a_payer,
                    type_paiement="PAIEMENT",
                    date_paiement=date_paiement,
                    mois_concerne=echeance.mois,
                    annee_concerne=echeance.annee,
                    mois_concerne_debut=mois_debut,
                    mois_concerne_fin=mois_fin,
                )
                paiements.append(paiement)
                montant_restant -= a_payer

        return paiements

    def mois_impayes(self, employe, annee=None):
        if annee is None:
            annee = date.today().year

        ct = ContentType.objects.get_for_model(employe)
        echeances = EcheanceSalariale.objects.filter(
            employe_content_type=ct,
            employe_object_id=str(employe.pk),
            entreprise_id=self.entreprise_id,
            annee=annee,
        ).exclude(statut="ANNULE")

        return [e for e in echeances if e.statut in ("A_PAYER", "EN_RETARD", "PARTIELLEMENT_PAYE")]

    def dashboard(self, annee=None):
        if annee is None:
            annee = date.today().year

        qs = EcheanceSalariale.objects.filter(
            entreprise_id=self.entreprise_id,
            annee=annee,
        ).exclude(statut="ANNULE")

        net_values = list(qs.values_list("montant_net", flat=True))
        paye_values = list(qs.values_list("montant_paye", flat=True))

        return {
            "total_echeances": qs.count(),
            "total_montant_du": sum(net_values),
            "total_montant_paye": sum(paye_values),
            "reste_global": sum(n - p for n, p in zip(net_values, paye_values)),
            "a_payer": qs.filter(statut="A_PAYER").count(),
            "paye": qs.filter(statut="PAYE").count(),
            "partiel": qs.filter(statut="PARTIELLEMENT_PAYE").count(),
            "en_retard": qs.filter(statut="EN_RETARD").count(),
        }
