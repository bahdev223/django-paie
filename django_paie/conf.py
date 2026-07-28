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

    def get_mode(self, entreprise_id=None):
        if self.MODE_PAR_ENTREPRISE and entreprise_id:
            from .models import ParametrePaie
            try:
                return ParametrePaie.objects.get(entreprise_id=entreprise_id).mode
            except ParametrePaie.DoesNotExist:
                return self.MODE
        return self.MODE


paie_settings = DjangoPaieSettings()
