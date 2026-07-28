from datetime import date, timedelta
from django.db import models
from django.utils import timezone


class PeriodePaieManager(models.Manager):
    def active(self):
        return self.filter(est_cloturee=False)

    def cloturees(self):
        return self.filter(est_cloturee=True)


class PeriodePaie(models.Model):
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
        unique_together = ["mois", "annee", "entreprise_id"]
        ordering = ["-annee", "-mois"]

    def __str__(self):
        return f"{self.mois:02d}/{self.annee}"

    @property
    def libelle(self):
        return f"{self.mois:02d}/{self.annee}"

    @classmethod
    def from_libelle(cls, libelle, entreprise_id=""):
        from datetime import date
        mois, annee = libelle.split("/")
        mois, annee = int(mois), int(annee)
        date_debut = date(annee, mois, 1)
        if mois == 12:
            date_fin = date(annee + 1, 1, 1) - timedelta(days=1)
        else:
            date_fin = date(annee, mois + 1, 1) - timedelta(days=1)
        if date_fin.day > 28:
            date_fin = date(annee, mois, 28)
        obj, _ = cls.objects.get_or_create(
            mois=mois, annee=annee, entreprise_id=entreprise_id,
            defaults={"date_debut": date_debut, "date_fin": date_fin},
        )
        return obj
