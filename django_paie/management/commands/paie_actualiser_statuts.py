from datetime import date
from django.core.management.base import BaseCommand, CommandError
from django_paie.models import EcheanceSalariale
from django_paie.conf import paie_settings


class Command(BaseCommand):
    help = "Met à jour les statuts des échéances (retard, avance, etc.)"

    def add_arguments(self, parser):
        parser.add_argument("--entreprise-source", default="")
        parser.add_argument("--entreprise-reference", default="")
        parser.add_argument("--all-entreprises", action="store_true")

    def handle(self, *args, **options):
        today = date.today()
        total = 0
        modifies = 0

        source = options.get("entreprise_source", "")
        reference = options.get("entreprise_reference", "")
        toutes = options.get("all_entreprises", False)
        if bool(source) != bool(reference):
            raise CommandError(
                "--entreprise-source et --entreprise-reference doivent être fournis ensemble."
            )
        if paie_settings.MODE_PAR_ENTREPRISE and not reference and not toutes:
            raise CommandError(
                "Ciblez une entreprise ou utilisez explicitement --all-entreprises."
            )

        echeances = EcheanceSalariale.objects.exclude(
            statut__in=["ANNULE", "TROPPERCU"]
        )
        if reference:
            echeances = echeances.filter(
                entreprise_source=source,
                entreprise_reference=reference,
            )

        for e in echeances:
            total += 1
            ancien_statut = e.statut

            e.mettre_a_jour_statut()
            e.refresh_from_db(fields=["statut"])
            if e.statut != ancien_statut:
                modifies += 1
                self.stdout.write(
                    f"  {e.employe_object_id} - {e.periode}: {ancien_statut} → {e.statut}"
                )

        self.stdout.write(self.style.SUCCESS(
            f"{total} échéances examinées, {modifies} statut(s) mis à jour."
        ))
