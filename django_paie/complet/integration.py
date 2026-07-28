class DjangoStockageRH:
    def __init__(self, employe_model=None, contrat_model=None, absence_model=None):
        self.employe_model = employe_model
        self.contrat_model = contrat_model
        self.absence_model = absence_model

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
        if self.absence_model:
            return self.absence_model.objects.filter(
                employe_id=matricule, annee=annee, mois=mois
            ).count()
        return 0

    def get_heures_mois(self, matricule, annee, mois):
        return 151.67


class RHConnectorDjango:
    def __init__(self, stockage_rh=None):
        self.stockage_rh = stockage_rh or DjangoStockageRH()

    def get_employe(self, matricule):
        return self.stockage_rh.get_employe(matricule)

    def get_contrat_actif(self, matricule):
        return self.stockage_rh.get_contrat_actif(matricule)

    def get_absences_mois(self, matricule, annee, mois):
        return self.stockage_rh.get_absences_mois(matricule, annee, mois)

    def get_heures_mois(self, matricule, annee, mois):
        return self.stockage_rh.get_heures_mois(matricule, annee, mois)
