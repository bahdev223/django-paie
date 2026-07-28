class DjangoStockageRH:
    def __init__(self, employe_model=None, contrat_model=None, absence_model=None,
                 entreprise_id=""):
        self.employe_model = employe_model
        self.contrat_model = contrat_model
        self.absence_model = absence_model
        self.entreprise_id = entreprise_id

    def get_employe(self, matricule):
        if self.employe_model:
            return self.employe_model.objects.get(pk=matricule)
        from django.apps import apps
        from ..conf import paie_settings
        model = apps.get_model(paie_settings.EMPLOYE_MODEL)
        return model.objects.get(pk=matricule)

    def get_contrat_actif(self, matricule):
        if self.contrat_model:
            return self.contrat_model.objects.filter(
                employe_id=matricule, est_actif=True
            ).first()
        from ..conf import paie_settings
        if paie_settings.CONTRAT_MODEL:
            from django.apps import apps
            model = apps.get_model(paie_settings.CONTRAT_MODEL)
            return model.objects.filter(employe_id=matricule, est_actif=True).first()
        return None

    def get_absences_mois(self, matricule, annee, mois):
        model = self.absence_model
        if model is None:
            from django.apps import apps
            from ..conf import paie_settings
            if paie_settings.ABSENCE_MODEL:
                model = apps.get_model(paie_settings.ABSENCE_MODEL)
        if model:
            return model.objects.filter(
                employe_id=matricule, annee=annee, mois=mois
            ).count()
        return 0

    def get_heures_mois(self, matricule, annee, mois):
        return 151.67

    def get_variables_mois(self, matricule, annee, mois):
        from django.apps import apps
        from django.contrib.contenttypes.models import ContentType
        from ..conf import paie_settings
        employe_model = apps.get_model(paie_settings.EMPLOYE_MODEL)
        ct = ContentType.objects.get_for_model(employe_model)
        from ..models import VariablePaieMensuelle
        variable = VariablePaieMensuelle.objects.filter(
            employe_content_type=ct,
            employe_object_id=str(matricule),
            annee=annee,
            mois=mois,
            entreprise_id=self.entreprise_id,
        ).first()
        return variable.to_moteur_dict() if variable else {}


class RHConnectorDjango:
    def __init__(self, stockage_rh=None, entreprise_id=""):
        if stockage_rh is None:
            from django.utils.module_loading import import_string
            from ..conf import paie_settings
            adapter = paie_settings.RH_ADAPTER
            stockage_rh = (
                import_string(adapter)()
                if adapter
                else DjangoStockageRH(entreprise_id=entreprise_id)
            )
        self.stockage_rh = stockage_rh

    def get_employe(self, matricule):
        return self.stockage_rh.get_employe(matricule)

    def get_contrat_actif(self, matricule):
        return self.stockage_rh.get_contrat_actif(matricule)

    def get_absences_mois(self, matricule, annee, mois):
        return self.stockage_rh.get_absences_mois(matricule, annee, mois)

    def get_heures_mois(self, matricule, annee, mois):
        return self.stockage_rh.get_heures_mois(matricule, annee, mois)

    def get_variables_mois(self, matricule, annee, mois):
        method = getattr(self.stockage_rh, "get_variables_mois", None)
        return method(matricule, annee, mois) if method else {}
