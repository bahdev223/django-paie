from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from .models import EcheanceSalariale


PERMISSIONS_PAIE = [
    "view_echeancesalariale",
    "add_echeancesalariale",
    "change_echeancesalariale",
    "delete_echeancesalariale",
    "view_paiementsalarial",
    "add_paiementsalarial",
    "change_paiementsalarial",
    "delete_paiementsalarial",
]

PERMISSIONS_LABELS = {
    "paie": {
        "view_echeancesalariale": "Consulter les échéances salariales",
        "add_echeancesalariale": "Créer des échéances salariales",
        "change_echeancesalariale": "Modifier les échéances salariales",
        "delete_echeancesalariale": "Supprimer des échéances salariales",
        "view_paiementsalarial": "Consulter les paiements salariaux",
        "add_paiementsalarial": "Enregistrer des paiements salariaux",
        "change_paiementsalarial": "Modifier des paiements salariaux",
        "delete_paiementsalarial": "Supprimer des paiements salariaux",
    },
}


def creer_permissions_paie():
    ct, _ = ContentType.objects.get_or_create(
        app_label="django_paie", model="echeancesalariale"
    )
    for codename, label in PERMISSIONS_LABELS["paie"].items():
        Permission.objects.get_or_create(
            content_type=ct, codename=codename, defaults={"name": label}
        )
