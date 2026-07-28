from django.views.generic import ListView, DetailView, TemplateView
from django.views.generic.edit import CreateView
from django.urls import reverse_lazy
from .models import EcheanceSalariale, PaiementSalarial
from .services import ModeSimpleService


class EcheanceListView(ListView):
    model = EcheanceSalariale
    template_name = "django_paie/echeance_list.html"
    context_object_name = "echeances"
    paginate_by = 50

    def get_queryset(self):
        qs = super().get_queryset()
        if statut := self.request.GET.get("statut"):
            qs = qs.filter(statut=statut)
        if periode := self.request.GET.get("periode"):
            qs = qs.filter(periode=periode)
        return qs.select_related("employe_content_type")


class EcheanceDetailView(DetailView):
    model = EcheanceSalariale
    template_name = "django_paie/echeance_detail.html"
    context_object_name = "echeance"


class PaiementListView(ListView):
    model = PaiementSalarial
    template_name = "django_paie/paiement_list.html"
    context_object_name = "paiements"
    paginate_by = 50


class PaiementCreateView(CreateView):
    model = PaiementSalarial
    template_name = "django_paie/paiement_form.html"
    fields = ["echeance", "montant", "type_paiement", "date_paiement", "notes"]
    success_url = reverse_lazy("django_paie:paiement-list")


class DashboardView(TemplateView):
    template_name = "django_paie/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        service = ModeSimpleService()
        ctx["dashboard"] = service.dashboard()
        ctx["derniers_paiements"] = PaiementSalarial.objects.select_related(
            "echeance"
        ).order_by("-date_paiement")[:20]
        return ctx
