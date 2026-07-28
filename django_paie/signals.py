from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from .models import PaiementSalarial


@receiver(pre_delete, sender=PaiementSalarial)
def recalculer_echeance_sur_suppression(sender, instance, **kwargs):
    echeance = instance.echeance
    if instance.statut == "VALIDE":
        later_payments = PaiementSalarial.objects.filter(
            echeance=echeance, statut="VALIDE"
        ).exclude(pk=instance.pk)
        total = sum(p.montant for p in later_payments)
        from decimal import Decimal
        echeance.montant_paye = Decimal(str(total))
        echeance.mettre_a_jour_statut()
