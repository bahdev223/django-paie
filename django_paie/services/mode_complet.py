from datetime import date
from django.contrib.contenttypes.models import ContentType
from ..complet import MoteurPaie
from ..complet.integration import RHConnectorDjango
from ..conf import paie_settings
from ..models import EcheanceSalariale, PeriodePaie, RubriquePaie
from ..models.bulletin import BulletinPaie, LigneBulletin
from ..utils import extraire_mois_annee


class ModeCompletService:
    def __init__(self, entreprise_id=""):
        self.entreprise_id = entreprise_id

    def calculer_bulletin(self, employe, periode, rh_stockage=None):
        rh = RHConnectorDjango(stockage_rh=rh_stockage)
        moteur = MoteurPaie(stockage=None, rh_connector=rh)
        bulletin = moteur.calculer_bulletin(
            employe_id=str(employe.pk),
            periode=periode,
        )

        echeance = self._sauvegarder_bulletin(employe, periode, bulletin)
        return bulletin, echeance

    def _sauvegarder_bulletin(self, employe, periode, bulletin_dataclass):
        mois, annee = extraire_mois_annee(periode)
        periode_obj = PeriodePaie.from_libelle(periode, entreprise_id=self.entreprise_id)
        ct = ContentType.objects.get_for_model(employe)

        montant_brut = int(bulletin_dataclass.total_gains())
        montant_net = int(bulletin_dataclass.net_a_payer())
        total_retenues = int(bulletin_dataclass.total_retenues())

        echeance, _ = EcheanceSalariale.objects.update_or_create(
            employe_content_type=ct,
            employe_object_id=str(employe.pk),
            mois=mois,
            annee=annee,
            entreprise_id=self.entreprise_id,
            defaults={
                "date_debut": periode_obj.date_debut,
                "date_fin": periode_obj.date_fin,
                "date_echeance": date.today(),
                "montant_brut": montant_brut,
                "montant_net": montant_net,
                "mode": "COMPLET",
            },
        )

        bulletin_model, _ = BulletinPaie.objects.update_or_create(
            echeance=echeance,
            defaults={
                "total_gains": montant_brut,
                "total_retenues": total_retenues,
                "net_a_payer": montant_net,
                "date_edition": bulletin_dataclass.date_edition,
                "est_verrouille": bulletin_dataclass.est_verrouille,
                "statut": "VALIDE" if bulletin_dataclass.est_verrouille else "BROUILLON",
            },
        )

        bulletin_model.lignes.all().delete()
        for i, ligne in enumerate(bulletin_dataclass.lignes):
            rubrique, _ = RubriquePaie.objects.get_or_create(
                code=ligne.rubrique_code,
                defaults={
                    "libelle": ligne.rubrique_code,
                    "type_rubrique": "gain" if ligne.montant >= 0 else "retenue",
                },
            )
            LigneBulletin.objects.create(
                bulletin=bulletin_model,
                rubrique=rubrique,
                base=ligne.base,
                taux=ligne.taux,
                montant=ligne.montant,
                ordre=i,
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
