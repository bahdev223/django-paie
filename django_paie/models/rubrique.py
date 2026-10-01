from django.db import models
from django.db.models import Q
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
            models.CheckConstraint(
                condition=(
                    models.Q(entreprise_source="", entreprise_reference="")
                    | (~models.Q(entreprise_source="") & ~models.Q(entreprise_reference=""))
                ),
                name="paie_rub_ent_coherent",
            ),
            models.UniqueConstraint(
                fields=["entreprise_source", "entreprise_reference", "code"],
                name="paie_rubrique_code_unique_entreprise",
            ),
        ]

    @classmethod
    def actives_pour(cls, entreprise_source="", entreprise_reference=""):
        globales = list(
            cls.objects.filter(
                actif=True,
                entreprise_source="",
                entreprise_reference="",
            ).order_by("ordre", "code")
        )
        if not entreprise_reference:
            return globales

        specifiques = list(
            cls.objects.filter(
                actif=True,
                entreprise_source=entreprise_source,
                entreprise_reference=entreprise_reference,
            ).order_by("ordre", "code")
        )
        par_code = {rubrique.code: rubrique for rubrique in globales}
        par_code.update({rubrique.code: rubrique for rubrique in specifiques})
        return sorted(par_code.values(), key=lambda r: (r.ordre, r.code))

    @classmethod
    def pour_code(cls, code, entreprise_source="", entreprise_reference=""):
        if entreprise_reference:
            specifique = cls.objects.filter(
                code=code,
                entreprise_source=entreprise_source,
                entreprise_reference=entreprise_reference,
            ).first()
            if specifique:
                return specifique
        return cls.objects.filter(
            code=code,
            entreprise_source="",
            entreprise_reference="",
        ).first()

    def __str__(self):
        suffixe = (
            f" [{self.entreprise_reference}]"
            if self.entreprise_reference else " [global]"
        )
        return f"{self.code} - {self.libelle}{suffixe}"
