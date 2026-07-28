from decimal import Decimal
from datetime import date
from ..conf import paie_settings
from ..models import EcheanceSalariale, PeriodePaie


class ModeCompletService:
    def __init__(self, entreprise_id=""):
        self.entreprise_id = entreprise_id

    def calculer_bulletin(self, employe, periode):
        try:
            from paie_sahel.noyau.moteur_paie import MoteurPaie
            from paie_sahel.integration.rh_connector import RHConnector
        except ImportError:
            raise ImportError(
                "Le paquet 'paie-sahel' est requis pour le mode COMPLET. "
                "Installez-le avec: pip install paie-sahel"
            )

        moteur = MoteurPaie(stockage=None, rh_connector=RHConnector(stockage_rh=None))
        bulletin = moteur.calculer_bulletin(
            employe_id=str(employe.pk),
            periode=periode,
        )

        echeance = self._sauvegarder_bulletin(employe, periode, bulletin)
        return bulletin, echeance

    def _sauvegarder_bulletin(self, employe, periode, bulletin):
        from django.contrib.contenttypes.models import ContentType

        periode_obj = PeriodePaie.from_libelle(periode, entreprise_id=self.entreprise_id)
        ct = ContentType.objects.get_for_model(employe)

        echeance, _ = EcheanceSalariale.objects.update_or_create(
            employe_content_type=ct,
            employe_object_id=str(employe.pk),
            periode=periode,
            entreprise_id=self.entreprise_id,
            defaults={
                "date_debut": periode_obj.date_debut,
                "date_fin": periode_obj.date_fin,
                "date_echeance": date.today(),
                "montant_brut": int(bulletin.total_gains() * 100),
                "montant_net": int(bulletin.net_a_payer() * 100),
                "mode": "COMPLET",
            },
        )
        return echeance

    def calculer_masse(self, employes_ids, periode):
        resultats = []
        for eid in employes_ids:
            try:
                from django.apps import apps
                model = apps.get_model(paie_settings.EMPLOYE_MODEL)
                employe = model.objects.get(pk=eid)
                bulletin, echeance = self.calculer_bulletin(employe, periode)
                resultats.append({"employe_id": eid, "succes": True, "echeance_id": echeance.id})
            except Exception as e:
                resultats.append({"employe_id": eid, "succes": False, "erreur": str(e)})
        return resultats
