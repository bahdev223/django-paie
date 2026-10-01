from dataclasses import dataclass

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.utils.module_loading import import_string

from .conf import paie_settings


@dataclass(frozen=True)
class ContexteEntreprise:
    source: str
    reference: str
    libelle: str = ""

    @property
    def legacy_id(self):
        return self.reference

    @property
    def est_valide(self):
        return bool(self.source and self.reference)

    def as_kwargs(self):
        return {
            "entreprise_source": self.source,
            "entreprise_reference": self.reference,
            "entreprise_libelle": self.libelle,
            "entreprise_id": self.reference,
        }


def normaliser_contexte(value):
    if value is None:
        return None
    if isinstance(value, ContexteEntreprise):
        return value if value.est_valide else None
    if isinstance(value, dict):
        contexte = ContexteEntreprise(
            source=str(value.get("source") or value.get("entreprise_source") or ""),
            reference=str(
                value.get("reference")
                or value.get("entreprise_reference")
                or value.get("entreprise_id")
                or ""
            ),
            libelle=str(value.get("libelle") or value.get("entreprise_libelle") or ""),
        )
        return contexte if contexte.est_valide else None

    reference = (
        getattr(value, "reference", "")
        or getattr(value, "entreprise_reference", "")
        or getattr(value, "entreprise_id", "")
    )
    source = (
        getattr(value, "source", "")
        or getattr(value, "entreprise_source", "")
        or ("legacy" if reference else "")
    )
    contexte = ContexteEntreprise(
        source=str(source),
        reference=str(reference),
        libelle=str(
            getattr(value, "libelle", "")
            or getattr(value, "entreprise_libelle", "")
            or getattr(value, "nom", "")
        ),
    )
    return contexte if contexte.est_valide else None


def resoudre_entreprise(request=None, *, required=None):
    if not paie_settings.MODE_PAR_ENTREPRISE:
        return None

    contexte = None
    resolver = getattr(paie_settings, "ENTREPRISE_RESOLVER", None)
    if resolver:
        callable_resolver = import_string(resolver) if isinstance(resolver, str) else resolver
        contexte = normaliser_contexte(callable_resolver(request))
    elif request is not None:
        contexte = normaliser_contexte(getattr(request, "entreprise", None))
        if contexte is None:
            user = getattr(request, "user", None)
            legacy_id = getattr(user, "entreprise_id", "") if user else ""
            if legacy_id:
                contexte = ContexteEntreprise(
                    source="legacy",
                    reference=str(legacy_id),
                    libelle=str(getattr(user, "entreprise_nom", "") or ""),
                )

    if required is None:
        required = True

    if contexte is None and required:
        raise PermissionDenied(
            "Contexte entreprise obligatoire pour la paie. Configurez "
            "DJANGO_PAIE['ENTREPRISE_RESOLVER'] ou injectez request.entreprise."
        )
    return contexte


def filtrer_par_entreprise(queryset, contexte, *, prefix="", include_global=False):
    if contexte is None:
        return queryset

    source = f"{prefix}entreprise_source"
    reference = f"{prefix}entreprise_reference"
    tenant_q = Q(**{source: contexte.source, reference: contexte.reference})
    if include_global:
        return queryset.filter(tenant_q | Q(**{source: "", reference: ""}))
    return queryset.filter(tenant_q)


def appartient_a_entreprise(obj, contexte, *, allow_global=False):
    if obj is None or contexte is None:
        return True
    source = getattr(obj, "entreprise_source", "")
    reference = getattr(obj, "entreprise_reference", "")
    if allow_global and not source and not reference:
        return True
    return source == contexte.source and reference == contexte.reference


def verifier_appartenance(obj, contexte, *, allow_global=False, label="Objet"):
    if not appartient_a_entreprise(obj, contexte, allow_global=allow_global):
        raise PermissionDenied(f"{label} rattaché à une autre entreprise.")
