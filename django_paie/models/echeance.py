from datetime import date
from decimal import Decimal
from django.db import models, transaction
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class EcheanceSalariale(models.Model):
    STATUT_CHOICES = [
        ("A_PAYER", "À payer"),
        ("PARTIELLEMENT_PAYE", "Partiellement payé"),
        ("PAYE", "Payé"),
        ("EN_RETARD", "En retard"),
        ("PAYE_EN_AVANCE", "Payé en avance"),
        ("TROPPERCU", "Trop-perçu"),
        ("ANNULE", "Annulé"),
    ]

    MODE_CHOICES = [
        ("SIMPLE", "Simple"),
        ("COMPLET", "Complet"),
    ]

    employe_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    employe_object_id = models.CharField(max_length=255)
    employe = GenericForeignKey("employe_content_type", "employe_object_id")

    mois = models.PositiveSmallIntegerField()
    annee = models.PositiveSmallIntegerField()
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
            models.Index(fields=["annee", "mois", "entreprise_id"]),
        ]
        unique_together = ["employe_content_type", "employe_object_id", "mois", "annee", "entreprise_id"]

    def __str__(self):
        return f"{self.employe_object_id} - {self.periode} ({self.get_statut_display()})"

    @property
    def periode(self):
        return f"{self.mois:02d}/{self.annee}"

    @property
    def reste_a_payer(self):
        return max(self.montant_net - self.montant_paye, Decimal("0"))

    @property
    def trop_percu(self):
        return max(self.montant_paye - self.montant_net, Decimal("0"))

    @property
    def est_paye(self):
        return self.statut == "PAYE"

    @property
    def est_annule(self):
        return self.statut == "ANNULE"

    def mettre_a_jour_statut(self):
        if self.statut == "ANNULE":
            return

        today = date.today()
        est_en_retard = today > self.date_echeance

        if self.montant_paye > self.montant_net:
            self.statut = "TROPPERCU"
        elif self.montant_paye >= self.montant_net:
            if self._a_paiements_futurs():
                self.statut = "PAYE_EN_AVANCE"
            else:
                self.statut = "PAYE"
        elif self.montant_paye <= 0:
            if est_en_retard and not self._a_paiements_futurs():
                self.statut = "EN_RETARD"
            else:
                self.statut = "A_PAYER"
        else:
            if est_en_retard:
                self.statut = "EN_RETARD"
            elif self._a_paiements_futurs():
                self.statut = "PAYE_EN_AVANCE"
            else:
                self.statut = "PARTIELLEMENT_PAYE"

        self.save(update_fields=["statut", "montant_paye"])

    def _a_paiements_futurs(self):
        return self.paiements.filter(
            statut="VALIDE",
            type_paiement="AVANCE",
        ).exists() or self.paiements.filter(
            statut="VALIDE",
            annee_concerne__gt=self.annee,
        ).exists() or self.paiements.filter(
            statut="VALIDE",
            annee_concerne=self.annee,
            mois_concerne__gt=self.mois,
        ).exists()


class PaiementSalarial(models.Model):
    TYPE_CHOICES = [
        ("PAIEMENT", "Paiement"),
        ("AVANCE", "Avance"),
        ("ARRIERE", "Arriéré"),
        ("REGULARISATION", "Régularisation"),
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
    mois_concerne = models.PositiveSmallIntegerField()
    annee_concerne = models.PositiveSmallIntegerField()

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
        with transaction.atomic():
            echeance = EcheanceSalariale.objects.select_for_update().get(pk=self.echeance_id)
            from .periode import PeriodePaie
            if echeance.date_cloture or PeriodePaie.objects.filter(
                mois=echeance.mois,
                annee=echeance.annee,
                entreprise_id=echeance.entreprise_id,
                est_cloturee=True,
            ).exists():
                raise ValueError(
                    "Une période clôturée ne peut recevoir aucune modification de paiement."
                )
            super().save(*args, **kwargs)
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
        with transaction.atomic():
            echeance = EcheanceSalariale.objects.select_for_update().get(pk=self.echeance_id)
            from .periode import PeriodePaie
            if echeance.date_cloture or PeriodePaie.objects.filter(
                mois=echeance.mois,
                annee=echeance.annee,
                entreprise_id=echeance.entreprise_id,
                est_cloturee=True,
            ).exists():
                raise ValueError(
                    "Un paiement d'une période clôturée ne peut pas être annulé."
                )
            self.statut = "ANNULE"
            self.save(update_fields=["statut"])
