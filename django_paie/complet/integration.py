from decimal import Decimal

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.utils.module_loading import import_string

from ..conf import paie_settings
from ..tenancy import ContexteEntreprise, normaliser_contexte


class AdaptateurRHBase:
    """Contrat stable entre le moteur RH et django-paie."""

    def __init__(self, entreprise=None):
        self.entreprise = normaliser_contexte(entreprise)

    def get_employe(self, employe_id):
        raise NotImplementedError

    def get_contrat_actif(self, employe_id):
        raise NotImplementedError

    def get_absences_mois(self, employe_id, annee, mois):
        return 0

    def get_heures_mois(self, employe_id, annee, mois):
        return Decimal(str(paie_settings.HEURES_MENSUELLES_DEFAUT))

    def get_jours_ouvres(self, employe_id, annee, mois):
        return int(paie_settings.JOURS_OUVRES_DEFAUT)

    def get_variables_mois(self, employe_id, annee, mois):
        return {}

    def get_snapshot_employe(self, employe, contrat=None):
        nom_complet = getattr(employe, "nom_complet", None)
        if callable(nom_complet):
            nom_complet = nom_complet()
        if not nom_complet:
            nom = getattr(employe, "nom", "") or ""
            prenom = getattr(employe, "prenom", "") or getattr(employe, "first_name", "") or ""
            nom_complet = f"{nom} {prenom}".strip() or str(employe)

        poste = getattr(employe, "poste", None)
        poste_libelle = (
            getattr(poste, "intitule", None)
            or getattr(poste, "libelle", None)
            or getattr(employe, "poste_code", "")
            or ""
        )
        departement = getattr(employe, "departement", None)
        departement_libelle = (
            getattr(departement, "libelle", None)
            or getattr(departement, "nom", None)
            or getattr(employe, "departement_code", "")
            or ""
        )
        salaire = None
        if contrat is not None:
            for champ in (
                "salaire_base",
                "salaire_brut_mensuel",
                "salaire_mensuel",
                "salaire_contractuel",
            ):
                valeur = getattr(contrat, champ, None)
                if valeur is not None:
                    salaire = Decimal(str(valeur))
                    break

        return {
            "matricule": str(
                getattr(employe, "matricule", None)
                or getattr(employe, "code", None)
                or getattr(employe, "pk", "")
            ),
            "nom_complet": str(nom_complet),
            "poste": str(poste_libelle),
            "departement": str(departement_libelle),
            "salaire_contractuel": salaire,
        }


class DjangoStockageRH(AdaptateurRHBase):
    """Adaptateur Django générique pour les projets ne fournissant pas RH_ADAPTER."""

    def __init__(
        self,
        employe_model=None,
        contrat_model=None,
        absence_model=None,
        pointage_model=None,
        entreprise=None,
        entreprise_id="",
    ):
        if entreprise is None and entreprise_id:
            entreprise = ContexteEntreprise("legacy", str(entreprise_id))
        super().__init__(entreprise=entreprise)
        self.employe_model = employe_model
        self.contrat_model = contrat_model
        self.absence_model = absence_model
        self.pointage_model = pointage_model

    def _model(self, configured, setting_name):
        if configured is not None:
            return configured
        label = getattr(paie_settings, setting_name)
        return apps.get_model(label) if label else None

    def _filtrer_entreprise(self, qs):
        if not self.entreprise or not paie_settings.MODE_PAR_ENTREPRISE:
            return qs
        model = qs.model
        field_names = {f.name for f in model._meta.fields}
        if {"entreprise_source", "entreprise_reference"} <= field_names:
            return qs.filter(
                entreprise_source=self.entreprise.source,
                entreprise_reference=self.entreprise.reference,
            )
        champ = paie_settings.EMPLOYE_ENTREPRISE_FIELD
        if champ in field_names:
            return qs.filter(**{champ: self.entreprise.reference})
        return qs

    def get_employe(self, employe_id):
        model = self._model(self.employe_model, "EMPLOYE_MODEL")
        if model is None:
            raise LookupError("Aucun EMPLOYE_MODEL configuré.")
        return self._filtrer_entreprise(model.objects.all()).get(pk=employe_id)

    def get_contrat_actif(self, employe_id):
        model = self._model(self.contrat_model, "CONTRAT_MODEL")
        if model is None:
            return None

        qs = self._filtrer_entreprise(model.objects.all())
        fields = {f.name for f in model._meta.fields}
        if "employe" in fields:
            qs = qs.filter(employe_id=employe_id)
        elif "employe_id" in fields:
            qs = qs.filter(employe_id=employe_id)
        elif "matricule_employe" in fields:
            qs = qs.filter(matricule_employe=str(employe_id))

        if "est_actif" in fields:
            qs = qs.filter(est_actif=True)
        elif "actif" in fields:
            qs = qs.filter(actif=True)
        return qs.order_by("-pk").first()

    def get_absences_mois(self, employe_id, annee, mois):
        model = self._model(self.absence_model, "ABSENCE_MODEL")
        if model is None:
            return 0

        qs = self._filtrer_entreprise(model.objects.all())
        fields = {f.name for f in model._meta.fields}
        if "employe" in fields:
            qs = qs.filter(employe_id=employe_id)
        elif "employe_id" in fields:
            qs = qs.filter(employe_id=employe_id)
        elif "matricule_employe" in fields:
            qs = qs.filter(matricule_employe=str(employe_id))

        if {"annee", "mois"} <= fields:
            qs = qs.filter(annee=annee, mois=mois)
        elif "date_debut" in fields:
            qs = qs.filter(date_debut__year=annee, date_debut__month=mois)

        total = Decimal("0")
        for absence in qs:
            jours = getattr(absence, "nb_jours", None)
            if callable(jours):
                jours = jours()
            if jours is None:
                jours = getattr(absence, "jours", 1)
            total += Decimal(str(jours or 0))
        return total

    def get_heures_mois(self, employe_id, annee, mois):
        model = self._model(self.pointage_model, "POINTAGE_MODEL")
        if model is None:
            return super().get_heures_mois(employe_id, annee, mois)

        qs = self._filtrer_entreprise(model.objects.all())
        fields = {f.name for f in model._meta.fields}
        if "employe" in fields:
            qs = qs.filter(employe_id=employe_id)
        elif "employe_id" in fields:
            qs = qs.filter(employe_id=employe_id)
        elif "matricule_employe" in fields:
            qs = qs.filter(matricule_employe=str(employe_id))
        if "date_pointage" in fields:
            qs = qs.filter(date_pointage__year=annee, date_pointage__month=mois)
        elif "date" in fields:
            qs = qs.filter(date__year=annee, date__month=mois)

        total = Decimal("0")
        for pointage in qs:
            heures = getattr(pointage, "heures_travaillees", 0)
            if callable(heures):
                heures = heures()
            total += Decimal(str(heures or 0))
        return total

    def get_variables_mois(self, employe_id, annee, mois):
        from ..models import VariablePaieMensuelle

        employe_model = self._model(self.employe_model, "EMPLOYE_MODEL")
        ct = ContentType.objects.get_for_model(employe_model)
        filtres = {
            "employe_content_type": ct,
            "employe_object_id": str(employe_id),
            "annee": annee,
            "mois": mois,
        }
        if self.entreprise:
            filtres.update({
                "entreprise_source": self.entreprise.source,
                "entreprise_reference": self.entreprise.reference,
            })
        else:
            filtres.update({
                "entreprise_source": "",
                "entreprise_reference": "",
            })
        variable = VariablePaieMensuelle.objects.filter(**filtres).first()
        return variable.to_moteur_dict() if variable else {}


class RHConnectorDjango:
    def __init__(self, stockage_rh=None, entreprise=None, entreprise_id=""):
        if entreprise is None and entreprise_id:
            entreprise = ContexteEntreprise("legacy", str(entreprise_id))
        self.entreprise = normaliser_contexte(entreprise)

        if stockage_rh is None:
            adapter = paie_settings.RH_ADAPTER
            if adapter:
                cls = import_string(adapter)
                try:
                    stockage_rh = cls(entreprise=self.entreprise)
                except TypeError:
                    stockage_rh = cls()
            else:
                stockage_rh = DjangoStockageRH(entreprise=self.entreprise)
        self.stockage_rh = stockage_rh

    def get_employe(self, employe_id):
        return self.stockage_rh.get_employe(employe_id)

    def get_contrat_actif(self, employe_id):
        return self.stockage_rh.get_contrat_actif(employe_id)

    def get_absences_mois(self, employe_id, annee, mois):
        return self.stockage_rh.get_absences_mois(employe_id, annee, mois)

    def get_heures_mois(self, employe_id, annee, mois):
        return self.stockage_rh.get_heures_mois(employe_id, annee, mois)

    def get_jours_ouvres(self, employe_id, annee, mois):
        method = getattr(self.stockage_rh, "get_jours_ouvres", None)
        return (
            method(employe_id, annee, mois)
            if method
            else int(paie_settings.JOURS_OUVRES_DEFAUT)
        )

    def get_variables_mois(self, employe_id, annee, mois):
        method = getattr(self.stockage_rh, "get_variables_mois", None)
        return method(employe_id, annee, mois) if method else {}

    def get_snapshot_employe(self, employe, contrat=None):
        method = getattr(self.stockage_rh, "get_snapshot_employe", None)
        if method:
            return method(employe, contrat)
        return AdaptateurRHBase().get_snapshot_employe(employe, contrat)
