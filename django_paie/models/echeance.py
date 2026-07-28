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
        constraints = [
            models.CheckConstraint(
                condition=models.Q(mois__gte=1, mois__lte=12),
                name="paie_echeance_mois_valide",
            ),
            models.CheckConstraint(
                condition=models.Q(annee__gte=2000, annee__lte=2100),
                name="paie_echeance_annee_valide",
            ),
            models.CheckConstraint(
                condition=models.Q(date_debut__lte=models.F("date_fin")),
                name="paie_echeance_dates_valides",
            ),
            models.CheckConstraint(
                condition=models.Q(montant_brut__gte=0),
                name="paie_echeance_brut_non_negatif",
            ),
            models.CheckConstraint(
                condition=models.Q(montant_net__gte=0),
                name="paie_echeance_net_non_negatif",
            ),
            models.CheckConstraint(
                condition=models.Q(montant_paye__gte=0),
                name="paie_echeance_paye_non_negatif",
            ),
        ]

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
        today = date.today()
        if (self.annee, self.mois) > (today.year, today.month):
            return self.paiements.filter(statut="VALIDE", type_paiement="AVANCE").exists()
        return self.paiements.filter(
            statut="VALIDE",
            type_paiement="AVANCE",
            date_paiement__gt=today,
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
        EcheanceSalariale, on_delete=models.PROTECT, related_name="paiements"
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
        constraints = [
            models.CheckConstraint(
                condition=models.Q(montant__gt=0),
                name="paie_paiement_montant_positif",
            ),
            models.CheckConstraint(
                condition=models.Q(mois_concerne__gte=1, mois_concerne__lte=12),
                name="paie_paiement_mois_valide",
            ),
            models.CheckConstraint(
                condition=models.Q(annee_concerne__gte=2000, annee_concerne__lte=2100),
                name="paie_paiement_annee_valide",
            ),
        ]

    def __str__(self):
        return f"{self.montant} F CFA - {self.echeance} ({self.get_type_paiement_display()})"

    def save(self, *args, **kwargs):
        with transaction.atomic():
            ancien_echeance_id = None
            ancien_statut = None
            if self.pk:
                ancien = PaiementSalarial.objects.select_for_update().get(pk=self.pk)
                ancien_echeance_id = ancien.echeance_id
                ancien_statut = ancien.statut
                if ancien_statut == "VALIDE" and ancien_echeance_id != self.echeance_id:
                    raise ValueError(
                        "Un paiement validé ne peut pas être déplacé. Annulez-le puis créez un nouveau paiement."
                    )
                update_fields = kwargs.get("update_fields")
                if update_fields is not None:
                    update_fields = set(update_fields)
                if ancien_statut == "VALIDE" and update_fields != {"statut"}:
                    raise ValueError(
                        "Un paiement validé ne peut pas être modifié. Annulez-le puis créez un nouveau paiement."
                    )
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
            if ancien_echeance_id and ancien_echeance_id != self.echeance_id:
                ancienne = EcheanceSalariale.objects.select_for_update().get(pk=ancien_echeance_id)
                self._recalculer_echeance(ancienne)

    def _recalculer_echeance(self, echeance=None):
        echeance = echeance or self.echeance
        total = (
            PaiementSalarial.objects.filter(
                echeance=echeance, statut="VALIDE"
            ).aggregate(total=models.Sum("montant"))["total"] or Decimal("0")
        )
        echeance.montant_paye = total
        echeance.mettre_a_jour_statut()

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

    def delete(self, *args, **kwargs):
        if self.statut == "VALIDE":
            raise ValueError(
                "Un paiement validé ne peut pas être supprimé. Utilisez l'annulation."
            )
        return super().delete(*args, **kwargs)
