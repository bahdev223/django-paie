from django.contrib import admin

from .conf import paie_settings
from .tenancy import filtrer_par_entreprise, resoudre_entreprise
from .models import (
    EcheanceSalariale,
    PaiementSalarial,
    PeriodePaie,
    ParametrePaie,
    RubriquePaie,
    BulletinPaie,
    LigneBulletin,
    CotisationBulletin,
    ValidationPaie,
    VariablePaieMensuelle,
    ReglePaie,
    EvenementPaie,
)


class EntrepriseAdminMixin:
    entreprise_prefix = ""
    include_global_entreprise = False

    def _contexte_entreprise(self, request):
        if not paie_settings.MODE_PAR_ENTREPRISE:
            return None
        if (
            request.user.is_superuser
            and paie_settings.SUPERUSER_GLOBAL_ENTREPRISE
        ):
            return None
        return resoudre_entreprise(request, required=True)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        contexte = self._contexte_entreprise(request)
        if contexte is None:
            return qs
        return filtrer_par_entreprise(
            qs,
            contexte,
            prefix=self.entreprise_prefix,
            include_global=self.include_global_entreprise,
        )

    def _injecter_entreprise(self, obj, request):
        contexte = self._contexte_entreprise(request)
        if contexte is None or self.entreprise_prefix:
            return
        obj.entreprise_source = contexte.source
        obj.entreprise_reference = contexte.reference
        obj.entreprise_libelle = contexte.libelle
        if hasattr(obj, "entreprise_id"):
            obj.entreprise_id = contexte.legacy_id

    def save_model(self, request, obj, form, change):
        self._injecter_entreprise(obj, request)
        obj.full_clean()
        super().save_model(request, obj, form, change)

    def _global_protege(self, request, obj):
        if not (
            paie_settings.MODE_PAR_ENTREPRISE
            and self.include_global_entreprise
            and obj is not None
            and getattr(obj, "est_global", False)
        ):
            return False
        return not (
            request.user.is_superuser
            and paie_settings.SUPERUSER_GLOBAL_ENTREPRISE
        )

    def has_change_permission(self, request, obj=None):
        if self._global_protege(request, obj):
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if self._global_protege(request, obj):
            return False
        return super().has_delete_permission(request, obj)


class LectureSeuleAdminMixin:
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ()
        return tuple(field.name for field in obj._meta.fields)


class PaiementSalarialInline(admin.TabularInline):
    model = PaiementSalarial
    extra = 0
    can_delete = False
    fields = (
        "montant",
        "type_paiement",
        "date_paiement",
        "mois_concerne",
        "annee_concerne",
        "statut",
        "reference",
        "compte_reference",
        "created_at",
    )
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(EcheanceSalariale)
class EcheanceSalarialeAdmin(
    LectureSeuleAdminMixin,
    EntrepriseAdminMixin,
    admin.ModelAdmin,
):
    list_display = (
        "employe_object_id",
        "employe_nom_snapshot",
        "periode",
        "montant_brut",
        "montant_net",
        "montant_paye",
        "statut",
        "mode",
        "entreprise_reference",
    )
    list_filter = ("statut", "mode", "mois", "annee", "entreprise_source")
    search_fields = (
        "employe_object_id",
        "employe_matricule_snapshot",
        "employe_nom_snapshot",
        "notes",
    )
    inlines = [PaiementSalarialInline]


@admin.register(PaiementSalarial)
class PaiementSalarialAdmin(
    LectureSeuleAdminMixin,
    EntrepriseAdminMixin,
    admin.ModelAdmin,
):
    entreprise_prefix = "echeance__"
    list_display = (
        "echeance",
        "montant",
        "type_paiement",
        "date_paiement",
        "periode_concernee",
        "statut",
        "compte_reference",
    )
    list_filter = ("type_paiement", "statut", "date_paiement")
    search_fields = (
        "echeance__employe_object_id",
        "reference",
        "cle_idempotence",
        "compte_reference",
        "notes",
    )

    @admin.display(description="Période concernée")
    def periode_concernee(self, obj):
        return f"{obj.mois_concerne:02d}/{obj.annee_concerne}"


@admin.register(PeriodePaie)
class PeriodePaieAdmin(
    LectureSeuleAdminMixin,
    EntrepriseAdminMixin,
    admin.ModelAdmin,
):
    list_display = (
        "libelle",
        "date_debut",
        "date_fin",
        "est_cloturee",
        "entreprise_reference",
    )
    list_filter = ("est_cloturee", "entreprise_source")


@admin.register(ParametrePaie)
class ParametrePaieAdmin(EntrepriseAdminMixin, admin.ModelAdmin):
    list_display = (
        "entreprise_reference",
        "entreprise_libelle",
        "mode",
        "devise",
        "employe_model",
    )
    search_fields = ("entreprise_reference", "entreprise_libelle")


class LigneBulletinInline(admin.TabularInline):
    model = LigneBulletin
    extra = 0
    readonly_fields = ("rubrique", "base", "taux", "montant", "ordre")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class CotisationBulletinInline(admin.TabularInline):
    model = CotisationBulletin
    extra = 0
    readonly_fields = (
        "rubrique",
        "type_cotisation",
        "base",
        "taux",
        "montant",
    )
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class ValidationPaieInline(admin.TabularInline):
    model = ValidationPaie
    extra = 0
    readonly_fields = ("statut", "valide_par", "date_action", "notes")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(BulletinPaie)
class BulletinPaieAdmin(
    LectureSeuleAdminMixin,
    EntrepriseAdminMixin,
    admin.ModelAdmin,
):
    entreprise_prefix = "echeance__"
    list_display = (
        "echeance",
        "total_gains",
        "total_retenues",
        "net_a_payer",
        "statut",
        "est_verrouille",
    )
    list_filter = ("statut", "est_verrouille")
    inlines = [
        LigneBulletinInline,
        CotisationBulletinInline,
        ValidationPaieInline,
    ]


@admin.register(RubriquePaie)
class RubriquePaieAdmin(EntrepriseAdminMixin, admin.ModelAdmin):
    include_global_entreprise = True
    list_display = (
        "code",
        "libelle",
        "type_rubrique",
        "imposable",
        "cotisable",
        "actif",
        "ordre",
        "entreprise_reference",
    )
    list_filter = (
        "type_rubrique",
        "actif",
        "imposable",
        "cotisable",
        "entreprise_source",
    )
    search_fields = ("code", "libelle", "entreprise_reference")


@admin.register(VariablePaieMensuelle)
class VariablePaieMensuelleAdmin(EntrepriseAdminMixin, admin.ModelAdmin):
    list_display = (
        "employe_object_id",
        "mois",
        "annee",
        "entreprise_reference",
        "updated_at",
    )
    list_filter = ("annee", "mois", "entreprise_source")
    search_fields = ("employe_object_id",)


@admin.register(ReglePaie)
class ReglePaieAdmin(EntrepriseAdminMixin, admin.ModelAdmin):
    include_global_entreprise = True
    list_display = (
        "organisme",
        "pays",
        "version",
        "date_debut",
        "date_fin",
        "entreprise_reference",
        "actif",
    )
    list_filter = ("organisme", "pays", "actif", "entreprise_source")
    search_fields = ("entreprise_reference",)


@admin.register(EvenementPaie)
class EvenementPaieAdmin(
    LectureSeuleAdminMixin,
    EntrepriseAdminMixin,
    admin.ModelAdmin,
):
    list_display = (
        "cree_le",
        "action",
        "type_objet",
        "reference",
        "acteur",
        "entreprise_reference",
    )
    list_filter = ("action", "type_objet", "entreprise_source", "cree_le")
    search_fields = ("reference", "objet_id", "entreprise_reference")
