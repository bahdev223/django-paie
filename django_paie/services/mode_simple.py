import calendar
from datetime import date, datetime
from decimal import Decimal
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from ..models import EcheanceSalariale, PaiementSalarial, PeriodePaie
from ..conf import paie_settings
from ..utils import extraire_mois_annee
from .context import ContextePaieMixin


class ModeSimpleService(ContextePaieMixin):
    def __init__(self, entreprise_id="", entreprise=None):
        self._initialiser_contexte_entreprise(entreprise_id, entreprise)

    def _verifier_mode(self):
        if paie_settings.get_mode(
            self.entreprise_id,
            entreprise_source=self.entreprise_source,
            entreprise_reference=self.entreprise_reference,
        ) != "SIMPLE":
            raise ValueError("Le mode SIMPLE n'est pas activé.")

    def _verifier_entreprise_employe(self, employe):
        if not paie_settings.MODE_PAR_ENTREPRISE:
            return
        if employe is None:
            return
        source = getattr(employe, "entreprise_source", None)
        reference = getattr(employe, "entreprise_reference", None)
        if source is not None or reference is not None:
            if (
                str(source or "") != self.entreprise_source
                or str(reference or "") != self.entreprise_reference
            ):
                raise ValueError(
                    "Employé introuvable ou rattaché à une autre entreprise."
                )
            return
        champ = paie_settings.EMPLOYE_ENTREPRISE_FIELD
        valeur = getattr(employe, champ, None)
        if valeur is None or str(valeur) not in {
            str(self.entreprise_reference),
            str(self.entreprise_id),
        }:
            raise ValueError(
                "Employé introuvable ou rattaché à une autre entreprise."
            )

    def _verifier_periode_ouverte(self, echeance):
        if echeance.date_cloture or PeriodePaie.objects.filter(
            mois=echeance.mois,
            annee=echeance.annee,
            entreprise_source=echeance.entreprise_source,
            entreprise_reference=echeance.entreprise_reference,
            est_cloturee=True,
        ).exists():
            raise ValueError(
                f"La période {echeance.periode} est clôturée et ne peut plus être modifiée."
            )

    def creer_echeance(self, employe, periode, montant_brut, montant_net=None, date_echeance=None):
        self._verifier_mode()
        self._verifier_entreprise_employe(employe)
        if montant_net is None:
            montant_net = montant_brut
        montant_brut = Decimal(str(montant_brut))
        montant_net = Decimal(str(montant_net))
        if montant_brut < 0 or montant_net < 0:
            raise ValueError("Les montants d'une échéance doivent être positifs ou nuls.")

        mois, annee = extraire_mois_annee(periode)
        if date_echeance is None:
            jour = paie_settings.JOUR_PAIEMENT
            dernier_jour = calendar.monthrange(annee, mois)[1]
            date_echeance = date(annee, mois, min(jour, dernier_jour))

        periode_obj = PeriodePaie.from_libelle(
            periode,
            entreprise_id=self.entreprise_id,
            entreprise_source=self.entreprise_source,
            entreprise_reference=self.entreprise_reference,
            entreprise_libelle=self.entreprise_libelle,
        )
        ct = ContentType.objects.get_for_model(employe)

        with transaction.atomic():
            if periode_obj.est_cloturee:
                raise ValueError(
                    f"Impossible de créer/modifier une échéance en période clôturée ({periode})."
                )

            existante = EcheanceSalariale.objects.select_for_update().filter(
                employe_content_type=ct,
                employe_object_id=str(employe.pk),
                mois=mois,
                annee=annee,
                **self.entreprise_filtres(),
            ).first()

            if existante and existante.montant_paye > 0:
                raise ValueError(
                    f"Impossible de modifier l'échéance {existante.periode} : "
                    f"déjà payée ({existante.montant_paye} F CFA)."
                )

            echeance, created = EcheanceSalariale.objects.update_or_create(
                employe_content_type=ct,
                employe_object_id=str(employe.pk),
                mois=mois,
                annee=annee,
                **self.entreprise_filtres(),
                defaults={
                    **self.entreprise_kwargs(),
                    "date_debut": periode_obj.date_debut,
                    "date_fin": periode_obj.date_fin,
                    "date_echeance": date_echeance,
                    "montant_brut": montant_brut,
                    "montant_net": montant_net,
                    "mode": "SIMPLE",
                },
            )
        return echeance

    def enregistrer_paiement(
        self, echeance_id=None, montant=0, date_paiement=None,
        type_paiement="PAIEMENT", notes="", employe=None, periode=None,
        periode_cible=None, montant_mensuel=None, cle_idempotence=None,
        compte_reference="", reference=""
    ):
        self._verifier_mode()
        self._verifier_entreprise_employe(employe)
        if date_paiement is None:
            date_paiement = date.today()
        if Decimal(str(montant)) <= 0:
            raise ValueError("Le montant du paiement doit être positif.")
        if cle_idempotence:
            existant = PaiementSalarial.objects.filter(
                cle_idempotence=cle_idempotence
            ).first()
            if existant:
                if self.entreprise and (
                    existant.echeance.entreprise_source != self.entreprise_source
                    or existant.echeance.entreprise_reference != self.entreprise_reference
                ):
                    raise ValueError(
                        "Cette clé d'idempotence appartient à une autre entreprise."
                    )
                return existant

        with transaction.atomic():
            if echeance_id:
                qs = EcheanceSalariale.objects.select_for_update()
                if self.entreprise:
                    qs = qs.filter(**self.entreprise_filtres())
                try:
                    echeance = qs.get(pk=echeance_id)
                except EcheanceSalariale.DoesNotExist:
                    raise ValueError("Échéance introuvable ou accès refusé.")
                mois_concerne, annee_concerne = echeance.mois, echeance.annee
                employe = employe or echeance.employe
            elif employe and periode:
                self._verifier_entreprise_employe(employe)
                mois_concerne, annee_concerne = extraire_mois_annee(periode)
                ct = ContentType.objects.get_for_model(employe)
                periode_obj = PeriodePaie.from_libelle(
                    periode,
                    entreprise_id=self.entreprise_id,
                    entreprise_source=self.entreprise_source,
                    entreprise_reference=self.entreprise_reference,
                    entreprise_libelle=self.entreprise_libelle,
                )
                dernier_jour = calendar.monthrange(annee_concerne, mois_concerne)[1]
                echeance, _ = EcheanceSalariale.objects.get_or_create(
                    employe_content_type=ct,
                    employe_object_id=str(employe.pk),
                    mois=mois_concerne,
                    annee=annee_concerne,
                    **self.entreprise_filtres(),
                    defaults={
                        **self.entreprise_kwargs(),
                        "date_debut": periode_obj.date_debut,
                        "date_fin": periode_obj.date_fin,
                        "date_echeance": date(annee_concerne, mois_concerne, min(paie_settings.JOUR_PAIEMENT, dernier_jour)),
                        "montant_brut": 0,
                        "montant_net": 0,
                        "mode": "SIMPLE",
                    },
                )
                echeance = EcheanceSalariale.objects.select_for_update().get(pk=echeance.pk)
            else:
                raise ValueError("Fournissez echeance_id ou (employe + periode).")

            if montant <= 0:
                raise ValueError("Le montant du paiement doit être positif.")

            if type_paiement == "AVANCE":
                reference_brut = echeance.montant_brut
                reference_net = echeance.montant_net
                if reference_net <= 0 and montant_mensuel is not None:
                    reference_brut = reference_net = Decimal(str(montant_mensuel))
                if reference_net <= 0:
                    reference = EcheanceSalariale.objects.filter(
                        employe_content_type=echeance.employe_content_type,
                        employe_object_id=echeance.employe_object_id,
                        **self.entreprise_filtres(),
                        montant_net__gt=0,
                    ).order_by("-annee", "-mois").first()
                    if reference:
                        reference_brut = reference.montant_brut
                        reference_net = reference.montant_net
                if reference_net <= 0:
                    raise ValueError(
                        "Aucun salaire de référence disponible. Fournissez montant_mensuel."
                    )
                if periode_cible:
                    target_mois, target_annee = extraire_mois_annee(periode_cible)
                else:
                    target_mois, target_annee = self._periode_suivante(echeance.mois, echeance.annee)
                target_periode = f"{target_mois:02d}/{target_annee}"
                periode_obj = PeriodePaie.from_libelle(
                    target_periode,
                    entreprise_id=self.entreprise_id,
                    entreprise_source=self.entreprise_source,
                    entreprise_reference=self.entreprise_reference,
                    entreprise_libelle=self.entreprise_libelle,
                )
                dernier_jour = calendar.monthrange(target_annee, target_mois)[1]
                ct = ContentType.objects.get_for_model(employe or echeance.employe)
                emp_id = str(getattr(employe, "pk", echeance.employe_object_id))
                montant_brut_cible = reference_brut
                montant_net_cible = reference_net
                target_echeance, _ = EcheanceSalariale.objects.get_or_create(
                    employe_content_type=echeance.employe_content_type,
                    employe_object_id=emp_id,
                    mois=target_mois,
                    annee=target_annee,
                    **self.entreprise_filtres(),
                    defaults={
                        **self.entreprise_kwargs(),
                        "date_debut": periode_obj.date_debut,
                        "date_fin": periode_obj.date_fin,
                        "date_echeance": date(target_annee, target_mois, min(paie_settings.JOUR_PAIEMENT, dernier_jour)),
                        "montant_brut": montant_brut_cible,
                        "montant_net": montant_net_cible,
                        "mode": "SIMPLE",
                    },
                )
                echeance = EcheanceSalariale.objects.select_for_update().get(pk=target_echeance.pk)
                mois_concerne, annee_concerne = target_mois, target_annee

            self._verifier_periode_ouverte(echeance)
            type_detecte = self._detecter_type_paiement(echeance, date_paiement, mois_concerne, annee_concerne)

            paiement = PaiementSalarial.objects.create(
                echeance=echeance,
                montant=montant,
                type_paiement=type_paiement if type_paiement != "PAIEMENT" else type_detecte,
                date_paiement=date_paiement,
                mois_concerne=mois_concerne,
                annee_concerne=annee_concerne,
                notes=notes,
                reference=reference,
                cle_idempotence=cle_idempotence,
                compte_reference=compte_reference,
            )
        return paiement

    def _periode_suivante(self, mois, annee):
        if mois == 12:
            return 1, annee + 1
        return mois + 1, annee

    def _detecter_type_paiement(self, echeance, date_paiement, mois_concerne, annee_concerne):
        if (annee_concerne, mois_concerne) > (date_paiement.year, date_paiement.month):
            return "AVANCE"
        if date_paiement > echeance.date_fin:
            return "ARRIERE"
        return "PAIEMENT"

    def payer_plusieurs_mois(self, employe, montant, mois_debut, mois_fin, date_paiement=None):
        self._verifier_mode()
        if date_paiement is None:
            date_paiement = date.today()

        ct = ContentType.objects.get_for_model(employe)
        m_debut, a_debut = extraire_mois_annee(mois_debut)
        m_fin, a_fin = extraire_mois_annee(mois_fin)

        echeances = EcheanceSalariale.objects.filter(
            employe_content_type=ct,
            employe_object_id=str(employe.pk),
            **self.entreprise_filtres(),
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
                self._verifier_periode_ouverte(echeance)
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

        return {
            "paiements": paiements,
            "montant_affecte": Decimal(str(montant)) - montant_restant,
            "reliquat": montant_restant,
        }

    def mois_impayes(self, employe, annee=None):
        if annee is None:
            annee = date.today().year

        ct = ContentType.objects.get_for_model(employe)
        echeances = EcheanceSalariale.objects.filter(
            employe_content_type=ct,
            employe_object_id=str(employe.pk),
            **self.entreprise_filtres(),
            annee=annee,
        ).exclude(statut="ANNULE")

        return [e for e in echeances if e.statut in ("A_PAYER", "EN_RETARD", "PARTIELLEMENT_PAYE")]

    def dashboard(self, annee=None):
        if annee is None:
            annee = date.today().year

        qs = EcheanceSalariale.objects.filter(
            **self.entreprise_filtres(),
            annee=annee,
        ).exclude(statut="ANNULE")

        echeances = list(qs)
        reste_global = sum(int(e.reste_a_payer) for e in echeances)

        return {
            "total_echeances": qs.count(),
            "total_montant_du": sum(int(e.montant_net) for e in echeances),
            "total_montant_paye": sum(int(e.montant_paye) for e in echeances),
            "reste_global": reste_global,
            "a_payer": qs.filter(statut="A_PAYER").count(),
            "paye": qs.filter(statut="PAYE").count(),
            "partiel": qs.filter(statut="PARTIELLEMENT_PAYE").count(),
            "en_retard": qs.filter(statut="EN_RETARD").count(),
        }
