from django.conf import settings
from django.db import models


class BulletinPaie(models.Model):
    STATUT_CHOICES = [
        ("BROUILLON", "Brouillon"),
        ("CALCULE", "Calculé"),
        ("VERIFIE", "Vérifié"),
        ("VALIDE", "Validé"),
        ("CLOTURE", "Clôturé"),
    ]

    echeance = models.OneToOneField(
        "EcheanceSalariale", on_delete=models.PROTECT, related_name="bulletin_detail"
    )
    total_gains = models.DecimalField(max_digits=14, decimal_places=0, default=0)
    total_retenues = models.DecimalField(max_digits=14, decimal_places=0, default=0)
    net_a_payer = models.DecimalField(max_digits=14, decimal_places=0, default=0)
    date_edition = models.DateField()
    est_verrouille = models.BooleanField(default=False)
    statut = models.CharField(
        max_length=10, choices=STATUT_CHOICES, default="BROUILLON"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Bulletin de paie"
        verbose_name_plural = "Bulletins de paie"

    def __str__(self):
        return f"Bulletin {self.echeance.periode} - {self.echeance.employe_object_id}"

    def delete(self, *args, **kwargs):
        if self.est_verrouille or self.statut in ("VALIDE", "CLOTURE"):
            raise ValueError("Un bulletin validé ou clôturé ne peut pas être supprimé.")
        return super().delete(*args, **kwargs)


class LigneBulletin(models.Model):
    bulletin = models.ForeignKey(
        BulletinPaie, on_delete=models.CASCADE, related_name="lignes"
    )
    rubrique = models.ForeignKey("RubriquePaie", on_delete=models.PROTECT)
    base = models.DecimalField(max_digits=14, decimal_places=0)
    taux = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    montant = models.DecimalField(max_digits=14, decimal_places=0)
    ordre = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "Ligne de bulletin"
        verbose_name_plural = "Lignes de bulletin"
        ordering = ["ordre"]

    def __str__(self):
        return f"{self.rubrique.code}: {self.montant} F"


class CotisationBulletin(models.Model):
    TYPE_CHOICES = [
        ("SALARIALE", "Salariale"),
        ("PATRONALE", "Patronale"),
    ]

    bulletin = models.ForeignKey(
        BulletinPaie, on_delete=models.CASCADE, related_name="cotisations"
    )
    rubrique = models.ForeignKey("RubriquePaie", on_delete=models.PROTECT)
    type_cotisation = models.CharField(max_length=10, choices=TYPE_CHOICES)
    base = models.DecimalField(max_digits=14, decimal_places=0)
    taux = models.DecimalField(max_digits=10, decimal_places=4)
    montant = models.DecimalField(max_digits=14, decimal_places=0)

    class Meta:
        verbose_name = "Cotisation du bulletin"
        verbose_name_plural = "Cotisations du bulletin"

    def __str__(self):
        return f"{self.rubrique.code} ({self.get_type_cotisation_display()})"


class ValidationPaie(models.Model):
    bulletin = models.ForeignKey(
        BulletinPaie, on_delete=models.CASCADE, related_name="validations"
    )
    statut = models.CharField(max_length=10, choices=BulletinPaie.STATUT_CHOICES)
    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    date_action = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Validation de paie"
        verbose_name_plural = "Validations de paie"
        ordering = ["-date_action"]

    def __str__(self):
        return f"{self.bulletin} -> {self.get_statut_display()}"
