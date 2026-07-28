from datetime import date
from decimal import Decimal
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from ..complet import MoteurPaie
from ..complet.modeles import RubriquePaie as RubriqueMoteur
from ..complet.regles import ReglesCNSS, ReglesAMO, ReglesITS
from ..complet.integration import RHConnectorDjango
from ..complet.services import CotisationService
from ..conf import paie_settings
from ..models import EcheanceSalariale, PeriodePaie, RubriquePaie, ReglePaie
from ..models.bulletin import BulletinPaie, LigneBulletin, CotisationBulletin, ValidationPaie
from ..utils import extraire_mois_annee


class ModeCompletService:
    def __init__(self, entreprise_id=""):
        self.entreprise_id = entreprise_id

    def _verifier_mode(self):
        if paie_settings.get_mode(self.entreprise_id) != "COMPLET":
            raise ValueError("Le mode COMPLET n'est pas activé.")

    def calculer_bulletin(self, employe, periode, rh_stockage=None):
        self._verifier_mode()
        self._verifier_entreprise_employe(employe)
        mois, annee = extraire_mois_annee(periode)
        date_calcul = date(annee, mois, 1)
        rh = RHConnectorDjango(
            stockage_rh=rh_stockage, entreprise_id=self.entreprise_id
        )
        moteur = MoteurPaie(
            stockage=None,
            rh_connector=rh,
            regles=self._charger_regles(date_calcul),
            rubriques=[
                RubriqueMoteur(
                    code=r.code,
                    libelle=r.libelle,
                    type=r.type_rubrique,
                    imposable=r.imposable,
                    cotisable=r.cotisable,
                )
                for r in RubriquePaie.objects.filter(actif=True)
            ],
        )
        bulletin = moteur.calculer_bulletin(
            employe_id=str(employe.pk),
            periode=periode,
        )

        echeance = self._sauvegarder_bulletin(employe, periode, bulletin, bulletin_dataclass_originel=bulletin)
        return bulletin, echeance

    def _verifier_entreprise_employe(self, employe):
        if not paie_settings.MODE_PAR_ENTREPRISE:
            return
        champ = paie_settings.EMPLOYE_ENTREPRISE_FIELD
        valeur = getattr(employe, champ, None)
        if valeur is None or str(valeur) != str(self.entreprise_id):
            raise ValueError("Employé introuvable ou rattaché à une autre entreprise.")

    def _charger_regles(self, date_calcul):
        resultat = {}
        for organisme in ("CNSS", "AMO", "ITS"):
            regle = ReglePaie.pour_date(
                organisme, date_calcul, entreprise_id=self.entreprise_id
            )
            if not regle:
                continue
            if organisme == "CNSS":
                resultat[organisme] = ReglesCNSS(
                    regle.taux_salarial, regle.taux_patronal, regle.plafond
                )
            elif organisme == "AMO":
                resultat[organisme] = ReglesAMO(
                    regle.taux_salarial, regle.taux_patronal, regle.plafond
                )
            else:
                resultat[organisme] = ReglesITS(regle.parametres)
        return resultat

    @transaction.atomic
    def _sauvegarder_bulletin(self, employe, periode, bulletin_dataclass, bulletin_dataclass_originel=None):
        mois, annee = extraire_mois_annee(periode)
        periode_obj = PeriodePaie.from_libelle(periode, entreprise_id=self.entreprise_id)
        if periode_obj.est_cloturee:
            raise ValueError(f"La période {periode} est clôturée.")
        ct = ContentType.objects.get_for_model(employe)
        existant = BulletinPaie.objects.filter(
            echeance__employe_content_type=ct,
            echeance__employe_object_id=str(employe.pk),
            echeance__mois=mois,
            echeance__annee=annee,
            echeance__entreprise_id=self.entreprise_id,
        ).first()
        if existant and (
            existant.est_verrouille or existant.statut in ("VALIDE", "CLOTURE")
        ):
            raise ValueError(
                "Un bulletin validé ou clôturé ne peut pas être recalculé."
            )

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

        self._creer_cotisations_bulletin(bulletin_model, bulletin_dataclass_originel or bulletin_dataclass, salaire_brut=montant_brut)

        ValidationPaie.objects.create(
            bulletin=bulletin_model,
            statut=bulletin_model.statut,
            notes=f"Bulletin créé pour {periode}",
        )

        return echeance

    def _creer_cotisations_bulletin(self, bulletin_model, bulletin_dataclass, salaire_brut):
        cotisation_service = CotisationService(
            date_calcul=bulletin_model.echeance.date_debut,
            entreprise_id=self.entreprise_id,
        )
        codes_cotisations = {
            "CNSS": cotisation_service.cnss,
            "AMO": cotisation_service.amo,
        }

        bulletin_model.cotisations.all().delete()

        for code, regle in codes_cotisations.items():
            rubrique, _ = RubriquePaie.objects.get_or_create(
                code=code,
                defaults={
                    "libelle": f"Cotisation {code}",
                    "type_rubrique": "retenue",
                },
            )

            ligne_moteur = next(
                (
                    ligne for ligne in bulletin_dataclass.lignes
                    if ligne.rubrique_code == code
                ),
                None,
            )
            assiette = ligne_moteur.base if ligne_moteur else salaire_brut
            salariale = regle.calculer_cotisation_salariale(assiette)
            patronale = regle.calculer_cotisation_patronale(assiette)

            CotisationBulletin.objects.create(
                bulletin=bulletin_model,
                rubrique=rubrique,
                type_cotisation="SALARIALE",
                base=salariale["base"],
                taux=Decimal(str(salariale["taux"])),
                montant=salariale["montant"],
            )

            if patronale["montant"] > 0:
                CotisationBulletin.objects.create(
                    bulletin=bulletin_model,
                    rubrique=rubrique,
                    type_cotisation="PATRONALE",
                    base=patronale["base"],
                    taux=Decimal(str(patronale["taux"])),
                    montant=patronale["montant"],
                )

    def calculer_masse(self, employes_ids, periode, rh_stockage=None):
        resultats = []
        for eid in employes_ids:
            try:
                from django.apps import apps
                model = apps.get_model(paie_settings.EMPLOYE_MODEL)
                employe = model.objects.get(pk=eid)
                bulletin, echeance = self.calculer_bulletin(employe, periode, rh_stockage=rh_stockage)
                resultats.append({"employe_id": eid, "succes": True, "echeance_id": echeance.id})
            except Exception as e:
                resultats.append({"employe_id": eid, "succes": False, "erreur": str(e)})
        return resultats
