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
from .tenancy import resoudre_entreprise, filtrer_par_entreprise


class EnterpriseFilterMixin:
    entreprise_prefix = ""

    def get_contexte_entreprise(self):
        if not paie_settings.MODE_PAR_ENTREPRISE:
            return None
        contexte = getattr(self, "_contexte_entreprise", None)
        if contexte is None:
            contexte = resoudre_entreprise(self.request, required=True)
            self._contexte_entreprise = contexte
        return contexte

    def get_entreprise_id(self):
        contexte = self.get_contexte_entreprise()
        return contexte.legacy_id if contexte else ""

    def get_queryset(self):
        qs = super().get_queryset()
        contexte = self.get_contexte_entreprise()
        if contexte is None:
            return qs
        prefix = self.entreprise_prefix
        model = getattr(self, "model", None)
        if model is PaiementSalarial:
            prefix = "echeance__"
        return filtrer_par_entreprise(qs, contexte, prefix=prefix)


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
        entreprise = kwargs.pop("entreprise", None)
        super().__init__(*args, **kwargs)
        qs = EcheanceSalariale.objects.all()
        if entreprise:
            qs = filtrer_par_entreprise(qs, entreprise)
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
        kwargs["entreprise"] = self.get_contexte_entreprise()
        return kwargs

    def form_valid(self, form):
        entreprise_id = self.get_entreprise_id()
        service = ModeSimpleService(
            entreprise_id=entreprise_id,
            entreprise=self.get_contexte_entreprise(),
            acteur=self.request.user,
        )
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
        contexte = self.get_contexte_entreprise()
        if contexte:
            paiements_qs = filtrer_par_entreprise(
                paiements_qs,
                contexte,
                prefix="echeance__",
            )
        ctx["derniers_paiements"] = paiements_qs.order_by("-date_paiement")[:10]

        contexte = self.get_contexte_entreprise()
        mode = paie_settings.get_mode(
            entreprise_id,
            entreprise_source=contexte.source if contexte else "",
            entreprise_reference=contexte.reference if contexte else "",
        )
        ctx["mode"] = mode
        if mode == "COMPLET":
            periode_courante = f"{date.today().month:02d}/{date.today().year}"
            ctx["masse_salariale"] = stats.masse_salariale(periode_courante)
            ctx["cout_employeur"] = stats.cout_employeur(periode_courante)

        return ctx
