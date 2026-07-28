from django.urls import path
from . import views

app_name = "django_paie"

urlpatterns = [
    path("echeances/", views.EcheanceListView.as_view(), name="echeance-list"),
    path("echeances/<uuid:pk>/", views.EcheanceDetailView.as_view(), name="echeance-detail"),
    path("paiements/", views.PaiementListView.as_view(), name="paiement-list"),
    path("paiements/creer/", views.PaiementCreateView.as_view(), name="paiement-create"),
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
]
