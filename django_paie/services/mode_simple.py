from datetime import date, datetime
from decimal import Decimal
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from ..models import EcheanceSalariale, PaiementSalarial, PeriodePaie
from ..conf import paie_settings


class ModeSimpleService:
    def __init__(self, entreprise_id=""):
        self.entreprise_id = entreprise_id

    def creer_echeance(self, employe, periode, montant_brut, montant_net=None, date_echeance=None):
        if montant_net is None:
            montant_net = montant_brut
        if date_echeance is None:
            today = date.today()
            date_echeance = date(today.year, today.month, 5)

        periode_obj = PeriodePaie.from_libelle(periode, entreprise_id=self.entreprise_id)
        ct = ContentType.objects.get_for_model(employe)

        echeance, created = EcheanceSalariale.objects.update_or_create(
            employe_content_type=ct,
            employe_object_id=str(employe.pk),
            periode=periode,
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

        echeance = EcheanceSalariale.objects.get(id=echeance_id)

        if type_paiement == "AVANCE":
            mois, annee = echeance.periode.split("/")
            prochain_mois = int(mois) + 1
            prochain_annee = int(annee)
            if prochain_mois > 12:
                prochain_mois = 1
                prochain_annee += 1
            periode_concernee = f"{prochain_mois:02d}/{prochain_annee}"
        else:
            periode_concernee = echeance.periode

        paiement = PaiementSalarial.objects.create(
            echeance=echeance,
            montant=montant,
            type_paiement=type_paiement,
            date_paiement=date_paiement,
            periode_concernee=periode_concernee,
            notes=notes,
        )
        return paiement

    def payer_plusieurs_mois(self, employe, montant, mois_debut, mois_fin, date_paiement=None):
        if date_paiement is None:
            date_paiement = date.today()

        ct = ContentType.objects.get_for_model(employe)
        echeances = EcheanceSalariale.objects.filter(
            employe_content_type=ct,
            employe_object_id=str(employe.pk),
            entreprise_id=self.entreprise_id,
            periode__gte=mois_debut,
            periode__lte=mois_fin,
        ).order_by("periode")

        montant_restant = Decimal(str(montant))
        paiements = []

        for echeance in echeances:
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
                periode_concernee=echeance.periode,
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
        prefix = str(annee)
        echeances = EcheanceSalariale.objects.filter(
            employe_content_type=ct,
            employe_object_id=str(employe.pk),
            entreprise_id=self.entreprise_id,
            periode__endswith=f"/{annee}",
        ).exclude(statut="ANNULE")

        impayes = []
        for e in echeances:
            if e.statut in ("A_PAYER", "EN_RETARD", "PARTIELLEMENT_PAYE"):
                impayes.append(e)
        return impayes

    def dashboard(self, annee=None):
        if annee is None:
            annee = date.today().year

        qs = EcheanceSalariale.objects.filter(
            entreprise_id=self.entreprise_id,
            periode__endswith=f"/{annee}",
        ).exclude(statut="ANNULE")

        return {
            "total_echeances": qs.count(),
            "total_montant_du": sum(qs.values_list("montant_net", flat=True)),
            "total_montant_paye": sum(qs.values_list("montant_paye", flat=True)),
            "reste_global": sum(e.montant_net - e.montant_paye for e in qs),
            "a_payer": qs.filter(statut="A_PAYER").count(),
            "paye": qs.filter(statut="PAYE").count(),
            "partiel": qs.filter(statut="PARTIELLEMENT_PAYE").count(),
            "en_retard": qs.filter(statut="EN_RETARD").count(),
        }
