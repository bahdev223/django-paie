from ..models import EvenementPaie


def journaliser_paie(
    *,
    action,
    type_objet,
    objet=None,
    reference="",
    acteur=None,
    entreprise=None,
    donnees=None,
):
    kwargs = {
        "action": action,
        "type_objet": type_objet,
        "objet_id": str(getattr(objet, "pk", "") or ""),
        "reference": str(reference or ""),
        "acteur": acteur,
        "donnees": donnees or {},
    }
    if entreprise is not None:
        kwargs.update(entreprise.as_kwargs())
    elif objet is not None:
        kwargs.update({
            "entreprise_source": getattr(objet, "entreprise_source", ""),
            "entreprise_reference": getattr(objet, "entreprise_reference", ""),
            "entreprise_libelle": getattr(objet, "entreprise_libelle", ""),
            "entreprise_id": getattr(objet, "entreprise_id", ""),
        })
    return EvenementPaie.objects.create(**kwargs)
