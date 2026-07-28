from decimal import Decimal
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from ..conf import paie_settings


class EcheanceSalariale(models.Model):
    STATUT_CHOICES = [
        ("A_PAYER", "À payer"),
        ("PARTIELLEMENT_PAYE", "Partiellement payé"),
        ("PAYE", "Payé"),
        ("EN_RETARD", "En retard"),
        ("PAYE_EN_AVANCE", "Payé en avance"),
        ("ANNULE", "Annulé"),
    ]

    MODE_CHOICES = [
        ("SIMPLE", "Simple"),
        ("COMPLET", "Complet"),
    ]

    employe_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    employe_object_id = models.CharField(max_length=255)
    employe = GenericForeignKey("employe_content_type", "employe_object_id")

    periode = models.CharField(max_length=7, db_index=True)
    date_debut = models.DateField()
    date_fin = models.DateField()
    date_echeance = models.DateField()

    montant_brut = models.DecimalField(max_digits=14, decimal_places=0, default=0)
    montant_net = models.DecimalField(max_digits=14, decimal_places=0, default=0)
    montant_paye = models.DecimalField(max_digits=14, decimal_places=0, default=0)

    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="A_PAYER", db_index=True)
    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default="SIMPLE")

    entreprise_id = models.CharField(max_length=255, blank=True, default="", db_index=True)

    notes = models.TextField(blank=True, default="")
    date_cloture = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Échéance salariale"
        verbose_name_plural = "Échéances salariales"
        indexes = [
            models.Index(fields=["employe_content_type", "employe_object_id"]),
            models.Index(fields=["entreprise_id", "statut"]),
            models.Index(fields=["periode", "entreprise_id"]),
        ]
        unique_together = ["employe_content_type", "employe_object_id", "periode", "entreprise_id"]

    def __str__(self):
        return f"{self.employe_object_id} - {self.periode} ({self.get_statut_display()})"

    @property
    def reste_a_payer(self):
        return self.montant_net - self.montant_paye

    @property
    def est_paye(self):
        return self.statut == "PAYE"

    @property
    def est_annule(self):
        return self.statut == "ANNULE"

    def mettre_a_jour_statut(self):
        if self.statut == "ANNULE":
            return
        if self.montant_paye <= 0:
            self.statut = "A_PAYER"
        elif self.montant_paye < self.montant_net:
            self.statut = "PARTIELLEMENT_PAYE"
        else:
            self.statut = "PAYE"
        self.save(update_fields=["statut"])


class PaiementSalarial(models.Model):
    TYPE_CHOICES = [
        ("PAIEMENT", "Paiement"),
        ("AVANCE", "Avance"),
        ("ARRIERE", "Arriéré"),
        ("REGULARISATION", "Régularisation"),
        ("ANNULATION", "Annulation"),
    ]

    STATUT_CHOICES = [
        ("VALIDE", "Valide"),
        ("ANNULE", "Annulé"),
        ("CORRIGE", "Corrigé"),
    ]

    echeance = models.ForeignKey(
        EcheanceSalariale, on_delete=models.CASCADE, related_name="paiements"
    )
    montant = models.DecimalField(max_digits=14, decimal_places=0)
    type_paiement = models.CharField(max_length=20, choices=TYPE_CHOICES, default="PAIEMENT")
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="VALIDE")

    date_paiement = models.DateField()
    periode_concernee = models.CharField(max_length=7, db_index=True)

    mois_concerne_debut = models.CharField(max_length=7, blank=True, default="")
    mois_concerne_fin = models.CharField(max_length=7, blank=True, default="")

    reference = models.CharField(max_length=100, blank=True, default="")
    notes = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Paiement salarial"
        verbose_name_plural = "Paiements salariaux"
        ordering = ["-date_paiement"]

    def __str__(self):
        return f"{self.montant} F CFA - {self.echeance} ({self.get_type_paiement_display()})"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new or self.statut == "VALIDE":
            self._recalculer_echeance()

    def _recalculer_echeance(self):
        total = (
            PaiementSalarial.objects.filter(
                echeance=self.echeance, statut="VALIDE"
            ).aggregate(total=models.Sum("montant"))["total"] or Decimal("0")
        )
        self.echeance.montant_paye = total
        self.echeance.mettre_a_jour_statut()

    def annuler(self):
        self.statut = "ANNULE"
        self.save(update_fields=["statut"])
        self._recalculer_echeance()
