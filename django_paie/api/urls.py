from django.urls import path
from . import views

app_name = "django_paie_api"

urlpatterns = [
    path("echeances/", views.EcheanceListAPI.as_view(), name="echeance-list"),
    path("echeances/<int:pk>/", views.EcheanceDetailAPI.as_view(), name="echeance-detail"),
    path("paiements/", views.PaiementListAPI.as_view(), name="paiement-list"),
    path("paiements/<int:pk>/annuler/", views.PaiementAnnulerAPI.as_view(), name="paiement-annuler"),
    path("avance/", views.AvanceAPI.as_view(), name="avance-create"),
    path("bulletins/", views.BulletinListAPI.as_view(), name="bulletin-list"),
    path("bulletins/calculer/", views.BulletinCalculAPI.as_view(), name="bulletin-calculer"),
    path("masse/calculer/", views.MasseSalarialeAPI.as_view(), name="masse-calculer"),
    path("stats/resume/", views.StatsResumeAPI.as_view(), name="stats-resume"),
    path("stats/arrieres/", views.StatsArrieresAPI.as_view(), name="stats-arrieres"),
    path("stats/avances/", views.StatsAvancesAPI.as_view(), name="stats-avances"),
    path("dashboard/", views.DashboardAPI.as_view(), name="api-dashboard"),
    path("docs/", views.DocsAPI.as_view(), name="api-docs"),
]
