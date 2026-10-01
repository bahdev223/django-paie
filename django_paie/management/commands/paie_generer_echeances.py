from django.core.management.base import BaseCommand, CommandError
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django_paie.conf import paie_settings
from django_paie.services import ModeSimpleService
from django_paie.tenancy import ContexteEntreprise


class Command(BaseCommand):
    help = "Génère les échéances salariales pour tous les employés actifs"

    def add_arguments(self, parser):
        parser.add_argument("--periode", type=str, help="Période au format MM/AAAA")
        parser.add_argument(
            "--employe-model", type=str, help="Chemin du modèle employé (ex: rh.Employe)"
        )
        parser.add_argument("--employe-id", type=str, help="ID employé spécifique")
        parser.add_argument(
            "--montant", type=int, help="Montant mensuel (mode SIMPLE)", default=0
        )
        parser.add_argument("--entreprise-source", default="")
        parser.add_argument("--entreprise-reference", default="")
        parser.add_argument("--entreprise-libelle", default="")

    def handle(self, *args, **options):
        model_path = options.get("employe_model") or paie_settings.EMPLOYE_MODEL
        if not model_path:
            raise CommandError(
                "EMPLOYE_MODEL doit être configuré dans DJANGO_PAIE "
                "ou passé via --employe-model"
            )

        try:
            model = apps.get_model(model_path)
        except LookupError:
            raise CommandError(f"Modèle introuvable : {model_path}")

        source = options.get("entreprise_source", "")
        reference = options.get("entreprise_reference", "")
        if bool(source) != bool(reference):
            raise CommandError(
                "--entreprise-source et --entreprise-reference doivent être fournis ensemble."
            )
        entreprise = (
            ContexteEntreprise(
                source,
                reference,
                options.get("entreprise_libelle", ""),
            )
            if reference else None
        )
        if paie_settings.MODE_PAR_ENTREPRISE and entreprise is None:
            raise CommandError(
                "Une entreprise est obligatoire en mode multi-entreprise."
            )

        employes = model.objects.all()
        if entreprise:
            fields = {f.name for f in model._meta.fields}
            if {"entreprise_source", "entreprise_reference"} <= fields:
                employes = employes.filter(
                    entreprise_source=entreprise.source,
                    entreprise_reference=entreprise.reference,
                )
            elif paie_settings.EMPLOYE_ENTREPRISE_FIELD in fields:
                employes = employes.filter(
                    **{paie_settings.EMPLOYE_ENTREPRISE_FIELD: entreprise.reference}
                )
        if options.get("employe_id"):
            employes = employes.filter(pk=options["employe_id"])

        if employes.count() == 0:
            self.stdout.write("Aucun employé trouvé.")
            return

        from datetime import date
        periode = options.get("periode") or f"{date.today().month:02d}/{date.today().year}"

        service = ModeSimpleService(entreprise=entreprise)
        count = 0
        for emp in employes:
            montant = options["montant"]
            if hasattr(emp, "salaire_mensuel") and not montant:
                montant = emp.salaire_mensuel
            if not montant and hasattr(emp, "montant_mensuel"):
                montant = emp.montant_mensuel
            if not montant:
                self.stdout.write(
                    self.style.WARNING(
                        f"Aucun montant pour {emp}, utilisez --montant"
                    )
                )
                continue

            service.creer_echeance(emp, periode, montant)
            count += 1

        self.stdout.write(
            self.style.SUCCESS(f"{count} échéances créées pour la période {periode}.")
        )
