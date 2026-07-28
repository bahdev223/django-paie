from django.core.management.base import BaseCommand
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Permission
from django_paie.permissions import creer_permissions_paie


class Command(BaseCommand):
    help = "Initialise les permissions et les paramètres de base de django-paie"

    def handle(self, *args, **options):
        creer_permissions_paie()
        self.stdout.write(self.style.SUCCESS("Permissions de paie créées avec succès."))
