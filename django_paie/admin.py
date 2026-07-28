from django.contrib import admin
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
)


class PaiementSalarialInline(admin.TabularInline):
    model = PaiementSalarial
    extra = 0
    readonly_fields = ("created_at",)
    fields = ("montant", "type_paiement", "date_paiement", "mois_concerne", "annee_concerne", "statut", "notes")


@admin.register(EcheanceSalariale)
class EcheanceSalarialeAdmin(admin.ModelAdmin):
    list_display = ("employe_object_id", "periode", "montant_brut", "montant_net", "montant_paye", "statut", "mode")
    list_filter = ("statut", "mode", "mois", "annee", "entreprise_id")
    search_fields = ("employe_object_id", "notes")
    readonly_fields = ("montant_paye", "created_at", "updated_at")
    inlines = [PaiementSalarialInline]


@admin.register(PaiementSalarial)
class PaiementSalarialAdmin(admin.ModelAdmin):
    list_display = ("echeance", "montant", "type_paiement", "date_paiement", "periode_concernee", "statut")
    list_filter = ("type_paiement", "statut", "date_paiement")
    search_fields = ("echeance__employe_object_id", "reference", "notes")
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="Période concernée")
    def periode_concernee(self, obj):
        return f"{obj.mois_concerne:02d}/{obj.annee_concerne}"


@admin.register(PeriodePaie)
class PeriodePaieAdmin(admin.ModelAdmin):
    list_display = ("libelle", "date_debut", "date_fin", "est_cloturee", "entreprise_id")
    list_filter = ("est_cloturee", "entreprise_id")


@admin.register(ParametrePaie)
class ParametrePaieAdmin(admin.ModelAdmin):
    list_display = ("entreprise_id", "mode", "devise", "employe_model")


class LigneBulletinInline(admin.TabularInline):
    model = LigneBulletin
    extra = 0
    readonly_fields = ("rubrique", "base", "taux", "montant", "ordre")
    can_delete = False


class CotisationBulletinInline(admin.TabularInline):
    model = CotisationBulletin
    extra = 0
    readonly_fields = ("rubrique", "type_cotisation", "base", "taux", "montant")
    can_delete = False


class ValidationPaieInline(admin.TabularInline):
    model = ValidationPaie
    extra = 0
    readonly_fields = ("statut", "valide_par", "date_action", "notes")
    can_delete = False


@admin.register(BulletinPaie)
class BulletinPaieAdmin(admin.ModelAdmin):
    list_display = ("echeance", "total_gains", "total_retenues", "net_a_payer", "statut", "est_verrouille")
    list_filter = ("statut", "est_verrouille")
    readonly_fields = ("total_gains", "total_retenues", "net_a_payer", "created_at", "updated_at")
    inlines = [LigneBulletinInline, CotisationBulletinInline, ValidationPaieInline]


@admin.register(RubriquePaie)
class RubriquePaieAdmin(admin.ModelAdmin):
    list_display = ("code", "libelle", "type_rubrique", "imposable", "cotisable", "actif", "ordre")
    list_filter = ("type_rubrique", "actif", "imposable", "cotisable")
    search_fields = ("code", "libelle")
    list_editable = ("actif", "ordre")


@admin.register(VariablePaieMensuelle)
class VariablePaieMensuelleAdmin(admin.ModelAdmin):
    list_display = ("employe_object_id", "mois", "annee", "entreprise_id", "updated_at")
    list_filter = ("annee", "mois", "entreprise_id")
    search_fields = ("employe_object_id",)


@admin.register(ReglePaie)
class ReglePaieAdmin(admin.ModelAdmin):
    list_display = (
        "organisme", "pays", "version", "date_debut", "date_fin",
        "entreprise_id", "actif",
    )
    list_filter = ("organisme", "pays", "actif", "entreprise_id")
