from django.db import models
from django.db.models import Q


class ReglePaie(models.Model):
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
            models.UniqueConstraint(
                fields=["pays", "organisme", "version", "entreprise_id"],
                name="paie_regle_version_unique",
            )
        ]
        ordering = ["organisme", "-date_debut", "-version"]

    @classmethod
    def pour_date(cls, organisme, date_calcul, entreprise_id="", pays="ML"):
        base = cls.objects.filter(
            organisme=organisme,
            pays=pays,
            actif=True,
            date_debut__lte=date_calcul,
        ).filter(Q(date_fin__isnull=True) | Q(date_fin__gte=date_calcul))
        if entreprise_id:
            specifique = base.filter(entreprise_id=entreprise_id).first()
            if specifique:
                return specifique
        return base.filter(entreprise_id="").first()
