from django.db import models
from django.db.models import Q
from .entreprise import ContexteEntrepriseModel


class ReglePaie(ContexteEntrepriseModel):
    ORGANISME_CHOICES = [
        ("CNSS", "CNSS"),
        ("AMO", "AMO"),
        ("ITS", "ITS"),
    ]

    pays = models.CharField(max_length=2, default="ML")
    organisme = models.CharField(max_length=20, choices=ORGANISME_CHOICES)
    version = models.PositiveIntegerField(default=1)
    date_debut = models.DateField()
    date_fin = models.DateField(null=True, blank=True)
    entreprise_id = models.CharField(max_length=255, blank=True, default="", db_index=True)
    taux_salarial = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    taux_patronal = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    plafond = models.DecimalField(max_digits=14, decimal_places=0, null=True, blank=True)
    parametres = models.JSONField(default=dict, blank=True)
    actif = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Règle de paie"
        verbose_name_plural = "Règles de paie"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(entreprise_source="", entreprise_reference="")
                    | (~models.Q(entreprise_source="") & ~models.Q(entreprise_reference=""))
                ),
                name="django_paie_reglepaie_ent_coherent",
            ),
            models.UniqueConstraint(
                fields=[
                    "pays", "organisme", "version",
                    "entreprise_source", "entreprise_reference",
                ],
                name="paie_regle_version_unique",
            )
        ]
        ordering = ["organisme", "-date_debut", "-version"]

    @classmethod
    def pour_date(
        cls, organisme, date_calcul, entreprise_id="", pays="ML",
        entreprise_source="", entreprise_reference=""
    ):
        base = cls.objects.filter(
            organisme=organisme,
            pays=pays,
            actif=True,
            date_debut__lte=date_calcul,
        ).filter(Q(date_fin__isnull=True) | Q(date_fin__gte=date_calcul))
        if entreprise_reference:
            specifique = base.filter(
                entreprise_source=entreprise_source,
                entreprise_reference=entreprise_reference,
            ).first()
            if specifique:
                return specifique
        elif entreprise_id:
            specifique = base.filter(
                entreprise_source="legacy",
                entreprise_reference=str(entreprise_id),
            ).first()
            if specifique:
                return specifique
        return base.filter(
            entreprise_source="",
            entreprise_reference="",
        ).first()
