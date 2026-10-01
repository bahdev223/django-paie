from decimal import Decimal

from django.db.models.signals import post_delete
from django.dispatch import Signal, receiver

from .models import PaiementSalarial


paiement_paie_enregistre = Signal()
paiement_paie_annule = Signal()
bulletin_paie_calcule = Signal()
periode_paie_cloturee = Signal()


@receiver(post_delete, sender=PaiementSalarial)
def recalculer_echeance_sur_suppression(sender, instance, **kwargs):
    echeance = instance.echeance
    if instance.statut == "VALIDE":
        total = sum(
            p.montant
            for p in PaiementSalarial.objects.filter(
                echeance=echeance,
                statut="VALIDE",
            )
        )
        echeance.montant_paye = Decimal(str(total))
        echeance.mettre_a_jour_statut()
