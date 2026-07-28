from datetime import date
from django.views.generic import ListView, DetailView, TemplateView
from django.views.generic.edit import FormView
from django import forms
from django.urls import reverse_lazy
from django.shortcuts import redirect
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from .models import EcheanceSalariale, PaiementSalarial, PeriodePaie
from .services import ModeSimpleService, StatistiquesPaieService
from .conf import paie_settings


class EnterpriseFilterMixin:
    def get_entreprise_id(self):
        if paie_settings.MODE_PAR_ENTREPRISE:
            entreprise_id = getattr(self.request.user, "entreprise_id", "")
            if not entreprise_id:
                raise PermissionDenied(
                    "Aucune entreprise associée à cet utilisateur."
                )
            return str(entreprise_id)
        return ""

    def get_queryset(self):
        qs = super().get_queryset()
        entreprise_id = self.get_entreprise_id()
        if entreprise_id:
            model = getattr(self, "model", None)
            if model and model is PaiementSalarial:
                qs = qs.filter(echeance__entreprise_id=entreprise_id)
            elif entreprise_id:
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

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["statut_choices"] = EcheanceSalariale.STATUT_CHOICES
        return ctx


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


class PaiementForm(forms.Form):
    echeance = forms.ModelChoiceField(
        queryset=EcheanceSalariale.objects.none(),
        label="Échéance",
    )

    def __init__(self, *args, **kwargs):
        entreprise_id = kwargs.pop("entreprise_id", "")
        super().__init__(*args, **kwargs)
        qs = EcheanceSalariale.objects.all()
        if entreprise_id:
            qs = qs.filter(entreprise_id=entreprise_id)
        self.fields["echeance"].queryset = qs
    montant = forms.DecimalField(label="Montant", min_value=1, max_digits=14, decimal_places=0)
    type_paiement = forms.ChoiceField(
        choices=[("", "Détection automatique")] + list(PaiementSalarial.TYPE_CHOICES),
        label="Type", required=False,
    )
    date_paiement = forms.DateField(
        label="Date de paiement",
        widget=forms.DateInput(attrs={"type": "date"}),
        initial=date.today,
    )
    notes = forms.CharField(label="Notes", required=False, widget=forms.Textarea)


class PaiementCreateView(PermissionRequiredMixin, EnterpriseFilterMixin, FormView):
    template_name = "django_paie/paiement_form.html"
    form_class = PaiementForm
    success_url = reverse_lazy("django_paie:paiement-list")
    permission_required = "django_paie.add_paiementsalarial"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["entreprise_id"] = self.get_entreprise_id()
        return kwargs

    def form_valid(self, form):
        entreprise_id = self.get_entreprise_id()
        service = ModeSimpleService(entreprise_id=entreprise_id)
        service.enregistrer_paiement(
            echeance_id=form.cleaned_data["echeance"].id,
            montant=form.cleaned_data["montant"],
            date_paiement=form.cleaned_data["date_paiement"],
            type_paiement=form.cleaned_data.get("type_paiement") or "PAIEMENT",
            notes=form.cleaned_data.get("notes", ""),
        )
        return redirect(self.success_url)


class DashboardView(PermissionRequiredMixin, EnterpriseFilterMixin, TemplateView):
    template_name = "django_paie/dashboard.html"
    permission_required = "django_paie.view_echeancesalariale"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        entreprise_id = self.get_entreprise_id()

        stats = StatistiquesPaieService(entreprise_id=entreprise_id)
        annee = self.request.GET.get("annee") or None
        if annee:
            try:
                annee = int(annee)
            except ValueError:
                annee = None

        ctx["resume"] = stats.resume_annuel(annee=annee)
        ctx["evolution"] = stats.evolution_mensuelle(annee=annee)
        ctx["arrieres"] = stats.arrieres()
        ctx["avances"] = stats.avances()
        ctx["alertes"] = stats.alertes()
        ctx["annee_selectionnee"] = annee or date.today().year

        paiements_qs = PaiementSalarial.objects.select_related("echeance")
        if entreprise_id:
            paiements_qs = paiements_qs.filter(echeance__entreprise_id=entreprise_id)
        ctx["derniers_paiements"] = paiements_qs.order_by("-date_paiement")[:10]

        mode = paie_settings.get_mode(entreprise_id)
        ctx["mode"] = mode
        if mode == "COMPLET":
            periode_courante = f"{date.today().month:02d}/{date.today().year}"
            ctx["masse_salariale"] = stats.masse_salariale(periode_courante)
            ctx["cout_employeur"] = stats.cout_employeur(periode_courante)

        return ctx
