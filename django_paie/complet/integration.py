class RHConnectorDjango:
    def __init__(self, stockage_rh=None):
        self.stockage_rh = stockage_rh

    def get_employe(self, matricule):
        if self.stockage_rh:
            return self.stockage_rh.get_employe(matricule)
        raise NotImplementedError(
            "Aucun stockage RH fourni. Passez un objet stockage_rh "
            "implémentant get_employe, get_contrat_actif, etc."
        )

    def get_contrat_actif(self, matricule):
        if self.stockage_rh:
            return self.stockage_rh.get_contrat_actif(matricule)
        return None

    def get_absences_mois(self, matricule, annee, mois):
        if self.stockage_rh:
            return self.stockage_rh.get_absences_mois(matricule, annee, mois)
        return 0

    def get_heures_mois(self, matricule, annee, mois):
        if self.stockage_rh:
            return self.stockage_rh.get_heures_mois(matricule, annee, mois)
        return 151.67
