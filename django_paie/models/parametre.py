from django.db import models
from .entreprise import ContexteEntrepriseModel


class ParametrePaie(ContexteEntrepriseModel):
    MODE_CHOICES = [
        ("SIMPLE", "Simple"),
        ("COMPLET", "Complet"),
    ]

    entreprise_id = models.CharField(max_length=255, blank=True, default="", db_index=True)
    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default="SIMPLE")
    devise = models.CharField(max_length=5, default="XOF")
    employe_model = models.CharField(max_length=255, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Paramètre de paie"
        verbose_name_plural = "Paramètres de paie"
        constraints = [
            models.UniqueConstraint(
                fields=["entreprise_source", "entreprise_reference"],
                name="paie_parametre_unique_entreprise",
            ),
        ]

    def __str__(self):
        return f"{self.entreprise_id} - Mode {self.mode}"
