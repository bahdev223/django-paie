from django.contrib import admin
from .models import EcheanceSalariale, PaiementSalarial, PeriodePaie, ParametrePaie


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
