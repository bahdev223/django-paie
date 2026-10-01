from django.conf import settings
from django.db import models

from .entreprise import ContexteEntrepriseModel


class EvenementPaie(ContexteEntrepriseModel):
    entreprise_id = models.CharField(
        max_length=255, blank=True, default="", db_index=True
    )
    action = models.CharField(max_length=80, db_index=True)
    type_objet = models.CharField(max_length=80, db_index=True)
    objet_id = models.CharField(max_length=120, blank=True, default="", db_index=True)
    reference = models.CharField(max_length=160, blank=True, default="", db_index=True)
    acteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="evenements_paie",
    )
    donnees = models.JSONField(default=dict, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-cree_le", "-id"]
        verbose_name = "Événement de paie"
        verbose_name_plural = "Événements de paie"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(entreprise_source="", entreprise_reference="")
                    | (~models.Q(entreprise_source="") & ~models.Q(entreprise_reference=""))
                ),
                name="paie_evt_ent_coherent",
            ),
        ]

    def __str__(self):
        return f"{self.action} - {self.type_objet} - {self.reference or self.objet_id}"
