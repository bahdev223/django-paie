from django.views.generic import ListView, DetailView, TemplateView
from django.views.generic.edit import CreateView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import PermissionRequiredMixin
from .models import EcheanceSalariale, PaiementSalarial
from .services import ModeSimpleService
from .conf import paie_settings


class EnterpriseFilterMixin:
    def get_entreprise_id(self):
        if paie_settings.MODE_PAR_ENTREPRISE:
            return getattr(self.request.user, "entreprise_id", "")
        return ""

    def get_queryset(self):
        qs = super().get_queryset()
        entreprise_id = self.get_entreprise_id()
        if entreprise_id:
            qs = qs.filter(entreprise_id=entreprise_id)
        return qs


class EcheanceListView(PermissionRequiredMixin, EnterpriseFilterMixin, ListView):
    model = EcheanceSalariale
    template_name = "django_paie/echeance_list.html"
    context_object_name = "echeances"
    paginate_by = 50
    permission_required = "django_paie.view_echeancesalariale"

    def get_queryset(self):
        qs = super().get_queryset()
        if statut := self.request.GET.get("statut"):
            qs = qs.filter(statut=statut)
        if periode := self.request.GET.get("periode"):
            try:
                mois, annee = periode.split("/")
                qs = qs.filter(mois=int(mois), annee=int(annee))
            except (ValueError, AttributeError):
                pass
        return qs.select_related("employe_content_type")


class EcheanceDetailView(PermissionRequiredMixin, EnterpriseFilterMixin, DetailView):
    model = EcheanceSalariale
    template_name = "django_paie/echeance_detail.html"
    context_object_name = "echeance"
    permission_required = "django_paie.view_echeancesalariale"


class PaiementListView(PermissionRequiredMixin, EnterpriseFilterMixin, ListView):
    model = PaiementSalarial
    template_name = "django_paie/paiement_list.html"
    context_object_name = "paiements"
    paginate_by = 50
    permission_required = "django_paie.view_paiementsalarial"

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.select_related("echeance")


class PaiementCreateView(PermissionRequiredMixin, CreateView):
    model = PaiementSalarial
    template_name = "django_paie/paiement_form.html"
    fields = ["echeance", "montant", "type_paiement", "date_paiement", "notes"]
    success_url = reverse_lazy("django_paie:paiement-list")
    permission_required = "django_paie.add_paiementsalarial"


class DashboardView(PermissionRequiredMixin, TemplateView):
    template_name = "django_paie/dashboard.html"
    permission_required = "django_paie.view_echeancesalariale"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        entreprise_id = getattr(self.request.user, "entreprise_id", "") if paie_settings.MODE_PAR_ENTREPRISE else ""
        service = ModeSimpleService(entreprise_id=entreprise_id)
        ctx["dashboard"] = service.dashboard()
        ctx["derniers_paiements"] = PaiementSalarial.objects.select_related(
            "echeance"
        ).order_by("-date_paiement")[:20]
        return ctx
