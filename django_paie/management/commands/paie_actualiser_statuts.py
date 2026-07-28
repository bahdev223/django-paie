from datetime import date
from django.core.management.base import BaseCommand
from django_paie.models import EcheanceSalariale


class Command(BaseCommand):
    help = "Met à jour les statuts des échéances (retard, avance, etc.)"

    def handle(self, *args, **options):
        today = date.today()
        total = 0
        modifies = 0

        echeances = EcheanceSalariale.objects.exclude(statut__in=["PAYE", "ANNULE", "TROPPERCU"])

        for e in echeances:
            total += 1
            ancien_statut = e.statut

            if today > e.date_echeance and e.statut == "A_PAYER":
                e.statut = "EN_RETARD"
            elif today > e.date_echeance and e.statut == "PARTIELLEMENT_PAYE":
                e.statut = "EN_RETARD"
            elif today <= e.date_echeance and e.statut == "EN_RETARD":
                e.statut = "A_PAYER"

            if e.statut != ancien_statut:
                e.save(update_fields=["statut"])
                modifies += 1
                self.stdout.write(
                    f"  {e.employe_object_id} - {e.periode}: {ancien_statut} → {e.statut}"
                )

        self.stdout.write(self.style.SUCCESS(
            f"{total} échéances examinées, {modifies} statut(s) mis à jour."
        ))
