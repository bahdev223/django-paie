from ..tenancy import ContexteEntreprise, normaliser_contexte


class ContextePaieMixin:
    def _initialiser_contexte_entreprise(self, entreprise_id="", entreprise=None):
        contexte = normaliser_contexte(entreprise)
        if contexte is None and entreprise_id:
            texte = str(entreprise_id)
            if ":" in texte:
                source, reference = texte.split(":", 1)
                contexte = ContexteEntreprise(source, reference)
            else:
                contexte = ContexteEntreprise("legacy", texte)
        self.entreprise = contexte
        self.entreprise_id = contexte.legacy_id if contexte else ""

    @property
    def entreprise_source(self):
        return self.entreprise.source if self.entreprise else ""

    @property
    def entreprise_reference(self):
        return self.entreprise.reference if self.entreprise else ""

    @property
    def entreprise_libelle(self):
        return self.entreprise.libelle if self.entreprise else ""

    def entreprise_kwargs(self):
        return self.entreprise.as_kwargs() if self.entreprise else {
            "entreprise_source": "",
            "entreprise_reference": "",
            "entreprise_libelle": "",
            "entreprise_id": "",
        }

    def entreprise_filtres(self, prefix=""):
        if not self.entreprise:
            return {
                f"{prefix}entreprise_source": "",
                f"{prefix}entreprise_reference": "",
            }
        return {
            f"{prefix}entreprise_source": self.entreprise_source,
            f"{prefix}entreprise_reference": self.entreprise_reference,
        }
