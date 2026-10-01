from django.conf import settings
from .defaults import DJANGO_PAIE_DEFAULTS


class DjangoPaieSettings:
    def __getattr__(self, attr):
        user_settings = getattr(settings, "DJANGO_PAIE", {})
        merged = dict(DJANGO_PAIE_DEFAULTS)
        merged.update(user_settings)
        if attr in merged:
            return merged[attr]
        raise AttributeError(f"Invalid DjangoPaie setting: {attr}")

    @property
    def all(self):
        user_settings = getattr(settings, "DJANGO_PAIE", {})
        merged = dict(DJANGO_PAIE_DEFAULTS)
        merged.update(user_settings)
        return merged

    def get_mode(
        self, entreprise_id=None, *, entreprise_source="", entreprise_reference=""
    ):
        if not self.MODE_PAR_ENTREPRISE:
            return self.MODE

        from .models import ParametrePaie

        if entreprise_reference:
            parametre = ParametrePaie.objects.filter(
                entreprise_source=entreprise_source,
                entreprise_reference=str(entreprise_reference),
            ).first()
            return parametre.mode if parametre else self.MODE

        if entreprise_id:
            parametre = ParametrePaie.objects.filter(
                entreprise_source="legacy",
                entreprise_reference=str(entreprise_id),
            ).first()
            if not parametre:
                parametre = ParametrePaie.objects.filter(
                    entreprise_id=str(entreprise_id)
                ).first()
            return parametre.mode if parametre else self.MODE

        return self.MODE


paie_settings = DjangoPaieSettings()
