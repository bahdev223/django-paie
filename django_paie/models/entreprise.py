from django.core.exceptions import ValidationError
from django.db import models


class ContexteEntrepriseModel(models.Model):
    entreprise_source = models.CharField(max_length=80, blank=True, db_index=True)
    entreprise_reference = models.CharField(max_length=255, blank=True, db_index=True)
    entreprise_libelle = models.CharField(max_length=240, blank=True)

    class Meta:
        abstract = True

    @property
    def entreprise(self):
        if not self.entreprise_reference:
            return None
        return {
            "source": self.entreprise_source,
            "reference": self.entreprise_reference,
            "libelle": self.entreprise_libelle,
        }

    @property
    def est_global(self):
        return not self.entreprise_source and not self.entreprise_reference

    def clean(self):
        super().clean()
        if bool(self.entreprise_source) != bool(self.entreprise_reference):
            raise ValidationError({
                "entreprise_reference": (
                    "entreprise_source et entreprise_reference doivent être renseignés ensemble."
                )
            })

    def save(self, *args, **kwargs):
        # Compatibilité v0.3 : les anciens projets utilisent encore entreprise_id.
        if hasattr(self, "entreprise_id"):
            legacy = getattr(self, "entreprise_id", "")
            if self.entreprise_reference:
                legacy_value = (
                    self.entreprise_reference
                    if self.entreprise_source == "legacy"
                    else f"{self.entreprise_source}:{self.entreprise_reference}"
                )
                setattr(self, "entreprise_id", legacy_value)
            elif legacy:
                self.entreprise_source = self.entreprise_source or "legacy"
                self.entreprise_reference = str(legacy)
        return super().save(*args, **kwargs)
