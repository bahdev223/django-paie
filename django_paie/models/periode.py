from datetime import date, timedelta
from django.db import models
from django.utils import timezone
from .entreprise import ContexteEntrepriseModel


class PeriodePaieManager(models.Manager):
    def active(self):
        return self.filter(est_cloturee=False)

    def cloturees(self):
        return self.filter(est_cloturee=True)


class PeriodePaie(ContexteEntrepriseModel):
    mois = models.IntegerField()
    annee = models.IntegerField()
    date_debut = models.DateField()
    date_fin = models.DateField()
    est_cloturee = models.BooleanField(default=False)
    entreprise_id = models.CharField(max_length=255, blank=True, default="", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = PeriodePaieManager()

    class Meta:
        verbose_name = "Période de paie"
        verbose_name_plural = "Périodes de paie"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(entreprise_source="", entreprise_reference="")
                    | (~models.Q(entreprise_source="") & ~models.Q(entreprise_reference=""))
                ),
                name="paie_per_ent_coherent",
            ),
            models.UniqueConstraint(
                fields=["mois", "annee", "entreprise_source", "entreprise_reference"],
                name="paie_periode_unique_entreprise",
            ),
            models.CheckConstraint(
                condition=models.Q(mois__gte=1, mois__lte=12),
                name="paie_periode_mois_valide",
            ),
            models.CheckConstraint(
                condition=models.Q(annee__gte=2000, annee__lte=2100),
                name="paie_periode_annee_valide",
            ),
        ]
        ordering = ["-annee", "-mois"]

    def __str__(self):
        return f"{self.mois:02d}/{self.annee}"

    @property
    def libelle(self):
        return f"{self.mois:02d}/{self.annee}"

    @classmethod
    def from_libelle(
        cls, libelle, entreprise_id="", entreprise_source="", entreprise_reference="",
        entreprise_libelle=""
    ):
        from datetime import date
        mois, annee = libelle.split("/")
        mois, annee = int(mois), int(annee)
        date_debut = date(annee, mois, 1)
        if mois == 12:
            date_fin = date(annee + 1, 1, 1) - timedelta(days=1)
        else:
            date_fin = date(annee, mois + 1, 1) - timedelta(days=1)
        if entreprise_reference:
            entreprise_id = entreprise_reference
        elif entreprise_id and not entreprise_source:
            entreprise_source = "legacy"
            entreprise_reference = str(entreprise_id)
        obj, _ = cls.objects.get_or_create(
            mois=mois,
            annee=annee,
            entreprise_source=entreprise_source,
            entreprise_reference=entreprise_reference,
            defaults={
                "entreprise_id": entreprise_id,
                "entreprise_libelle": entreprise_libelle,
                "date_debut": date_debut,
                "date_fin": date_fin,
            },
        )
        return obj
