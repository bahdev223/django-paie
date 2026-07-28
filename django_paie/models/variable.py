from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class VariablePaieMensuelle(models.Model):
    employe_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    employe_object_id = models.CharField(max_length=255)
    employe = GenericForeignKey("employe_content_type", "employe_object_id")
    mois = models.PositiveSmallIntegerField()
    annee = models.PositiveSmallIntegerField()
    entreprise_id = models.CharField(max_length=255, blank=True, default="", db_index=True)

    primes = models.DecimalField(max_digits=14, decimal_places=0, default=0)
    indemnites = models.DecimalField(max_digits=14, decimal_places=0, default=0)
    heures_supplementaires = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    taux_majoration_heures = models.DecimalField(max_digits=6, decimal_places=4, default=1.25)
    avantages_nature = models.DecimalField(max_digits=14, decimal_places=0, default=0)
    prets_avances = models.DecimalField(max_digits=14, decimal_places=0, default=0)
    retenues_personnalisees = models.DecimalField(max_digits=14, decimal_places=0, default=0)
    rappels = models.DecimalField(max_digits=14, decimal_places=0, default=0)
    conges_payes = models.DecimalField(max_digits=14, decimal_places=0, default=0)
    regularisations = models.DecimalField(max_digits=14, decimal_places=0, default=0)
    jours_absence = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    autres = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Variable mensuelle de paie"
        verbose_name_plural = "Variables mensuelles de paie"
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "employe_content_type",
                    "employe_object_id",
                    "mois",
                    "annee",
                    "entreprise_id",
                ],
                name="paie_variable_unique",
            )
        ]

    def to_moteur_dict(self):
        return {
            "primes": self.primes,
            "indemnites": self.indemnites,
            "heures_supplementaires": self.heures_supplementaires,
            "taux_majoration_heures": self.taux_majoration_heures,
            "avantages_nature": self.avantages_nature,
            "prets_avances": self.prets_avances,
            "retenues_personnalisees": self.retenues_personnalisees,
            "rappels": self.rappels,
            "conges_payes": self.conges_payes,
            "regularisations": self.regularisations,
            "jours_absence": self.jours_absence,
            "autres": self.autres,
        }
