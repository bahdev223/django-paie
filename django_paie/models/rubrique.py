from django.db import models
from .entreprise import ContexteEntrepriseModel


class RubriquePaie(ContexteEntrepriseModel):
    TYPE_CHOICES = [
        ("gain", "Gain"),
        ("retenue", "Retenue"),
    ]

    code = models.CharField(max_length=20, db_index=True)
    libelle = models.CharField(max_length=100)
    type_rubrique = models.CharField(max_length=10, choices=TYPE_CHOICES)
    imposable = models.BooleanField(default=True)
    cotisable = models.BooleanField(default=False)
    actif = models.BooleanField(default=True)
    ordre = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "Rubrique de paie"
        verbose_name_plural = "Rubriques de paie"
        ordering = ["ordre", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["entreprise_source", "entreprise_reference", "code"],
                name="paie_rubrique_code_unique_entreprise",
            ),
        ]

    def __str__(self):
        return f"{self.code} - {self.libelle}"
