from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from .models import EcheanceSalariale


PERMISSIONS_METIER = [
    "valider_bulletin",
    "cloturer_periode",
    "annuler_paiement",
    "exporter_paie",
]

PERMISSIONS_LABELS = {
    "valider_bulletin": "Valider un bulletin de paie",
    "cloturer_periode": "Clôturer une période de paie",
    "annuler_paiement": "Annuler un paiement salarial",
    "exporter_paie": "Exporter les données de paie",
}


def creer_permissions_paie():
    ct, _ = ContentType.objects.get_or_create(
        app_label="django_paie", model="echeancesalariale"
    )
    for codename, label in PERMISSIONS_LABELS.items():
        Permission.objects.get_or_create(
            content_type=ct, codename=codename, defaults={"name": label}
        )
