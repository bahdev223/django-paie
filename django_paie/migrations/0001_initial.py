from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.CreateModel(
            name="EcheanceSalariale",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("employe_object_id", models.CharField(max_length=255)),
                ("mois", models.PositiveSmallIntegerField()),
                ("annee", models.PositiveSmallIntegerField()),
                ("date_debut", models.DateField()),
                ("date_fin", models.DateField()),
                ("date_echeance", models.DateField()),
                ("montant_brut", models.DecimalField(decimal_places=0, default=0, max_digits=14)),
                ("montant_net", models.DecimalField(decimal_places=0, default=0, max_digits=14)),
                ("montant_paye", models.DecimalField(decimal_places=0, default=0, max_digits=14)),
                ("statut", models.CharField(choices=[
                    ("A_PAYER", "À payer"),
                    ("PARTIELLEMENT_PAYE", "Partiellement payé"),
                    ("PAYE", "Payé"),
                    ("EN_RETARD", "En retard"),
                    ("PAYE_EN_AVANCE", "Payé en avance"),
                    ("TROPPERCU", "Trop-perçu"),
                    ("ANNULE", "Annulé"),
                ], db_index=True, default="A_PAYER", max_length=20)),
                ("mode", models.CharField(choices=[("SIMPLE", "Simple"), ("COMPLET", "Complet")], default="SIMPLE", max_length=10)),
                ("entreprise_id", models.CharField(blank=True, db_index=True, default="", max_length=255)),
                ("notes", models.TextField(blank=True, default="")),
                ("date_cloture", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("employe_content_type", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="contenttypes.contenttype")),
            ],
            options={
                "verbose_name": "Échéance salariale",
                "verbose_name_plural": "Échéances salariales",
                "unique_together": {("employe_content_type", "employe_object_id", "mois", "annee", "entreprise_id")},
            },
        ),
        migrations.CreateModel(
            name="PeriodePaie",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("mois", models.IntegerField()),
                ("annee", models.IntegerField()),
                ("date_debut", models.DateField()),
                ("date_fin", models.DateField()),
                ("est_cloturee", models.BooleanField(default=False)),
                ("entreprise_id", models.CharField(blank=True, db_index=True, default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Période de paie",
                "verbose_name_plural": "Périodes de paie",
                "ordering": ["-annee", "-mois"],
                "unique_together": {("mois", "annee", "entreprise_id")},
            },
        ),
        migrations.CreateModel(
            name="ParametrePaie",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("entreprise_id", models.CharField(db_index=True, max_length=255, unique=True)),
                ("mode", models.CharField(choices=[("SIMPLE", "Simple"), ("COMPLET", "Complet")], default="SIMPLE", max_length=10)),
                ("devise", models.CharField(default="XOF", max_length=5)),
                ("employe_model", models.CharField(blank=True, default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Paramètre de paie",
                "verbose_name_plural": "Paramètres de paie",
            },
        ),
        migrations.CreateModel(
            name="PaiementSalarial",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("montant", models.DecimalField(decimal_places=0, max_digits=14)),
                ("type_paiement", models.CharField(choices=[
                    ("PAIEMENT", "Paiement"),
                    ("AVANCE", "Avance"),
                    ("ARRIERE", "Arriéré"),
                    ("REGULARISATION", "Régularisation"),
                    ("ANNULATION", "Annulation"),
                ], default="PAIEMENT", max_length=20)),
                ("statut", models.CharField(choices=[
                    ("VALIDE", "Valide"),
                    ("ANNULE", "Annulé"),
                    ("CORRIGE", "Corrigé"),
                ], default="VALIDE", max_length=20)),
                ("date_paiement", models.DateField()),
                ("mois_concerne", models.PositiveSmallIntegerField()),
                ("annee_concerne", models.PositiveSmallIntegerField()),
                ("mois_concerne_debut", models.CharField(blank=True, default="", max_length=7)),
                ("mois_concerne_fin", models.CharField(blank=True, default="", max_length=7)),
                ("reference", models.CharField(blank=True, default="", max_length=100)),
                ("notes", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("echeance", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="paiements", to="django_paie.echeancesalariale")),
            ],
            options={
                "verbose_name": "Paiement salarial",
                "verbose_name_plural": "Paiements salariaux",
                "ordering": ["-date_paiement"],
            },
        ),
        migrations.AddIndex(
            model_name="echeancesalariale",
            index=models.Index(fields=["employe_content_type", "employe_object_id"], name="django_paie_employe_content_type_employe_object_id_idx"),
        ),
        migrations.AddIndex(
            model_name="echeancesalariale",
            index=models.Index(fields=["entreprise_id", "statut"], name="django_paie_entreprise_id_statut_idx"),
        ),
        migrations.AddIndex(
            model_name="echeancesalariale",
            index=models.Index(fields=["annee", "mois", "entreprise_id"], name="django_paie_annee_mois_entreprise_id_idx"),
        ),
    ]
