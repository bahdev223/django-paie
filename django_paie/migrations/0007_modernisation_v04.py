from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def migrer_entreprises_legacy(apps, schema_editor):
    noms = [
        "EcheanceSalariale",
        "PeriodePaie",
        "ParametrePaie",
        "ReglePaie",
        "VariablePaieMensuelle",
    ]
    for nom in noms:
        Modele = apps.get_model("django_paie", nom)
        for obj in Modele.objects.filter(
            entreprise_source="",
            entreprise_reference="",
        ).exclude(entreprise_id="").iterator():
            obj.entreprise_source = "legacy"
            obj.entreprise_reference = str(obj.entreprise_id)
            obj.save(
                update_fields=["entreprise_source", "entreprise_reference"]
            )


def retour_entreprises_legacy(apps, schema_editor):
    noms = [
        "EcheanceSalariale",
        "PeriodePaie",
        "ParametrePaie",
        "ReglePaie",
        "VariablePaieMensuelle",
    ]
    for nom in noms:
        Modele = apps.get_model("django_paie", nom)
        Modele.objects.filter(entreprise_source="legacy").update(
            entreprise_source="",
            entreprise_reference="",
        )


class Migration(migrations.Migration):
    dependencies = [
        ("django_paie", "0006_alter_bulletinpaie_echeance_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="echeancesalariale",
            name="entreprise_source",
            field=models.CharField(blank=True, db_index=True, max_length=80),
        ),
        migrations.AddField(
            model_name="echeancesalariale",
            name="entreprise_reference",
            field=models.CharField(blank=True, db_index=True, max_length=255),
        ),
        migrations.AddField(
            model_name="echeancesalariale",
            name="entreprise_libelle",
            field=models.CharField(blank=True, max_length=240),
        ),
        migrations.AddField(
            model_name="echeancesalariale",
            name="employe_matricule_snapshot",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="echeancesalariale",
            name="employe_nom_snapshot",
            field=models.CharField(blank=True, default="", max_length=240),
        ),
        migrations.AddField(
            model_name="echeancesalariale",
            name="poste_snapshot",
            field=models.CharField(blank=True, default="", max_length=240),
        ),
        migrations.AddField(
            model_name="echeancesalariale",
            name="departement_snapshot",
            field=models.CharField(blank=True, default="", max_length=240),
        ),
        migrations.AddField(
            model_name="echeancesalariale",
            name="salaire_contractuel_snapshot",
            field=models.DecimalField(
                blank=True, decimal_places=0, max_digits=14, null=True
            ),
        ),
        migrations.AddField(
            model_name="periodepaie",
            name="entreprise_source",
            field=models.CharField(blank=True, db_index=True, max_length=80),
        ),
        migrations.AddField(
            model_name="periodepaie",
            name="entreprise_reference",
            field=models.CharField(blank=True, db_index=True, max_length=255),
        ),
        migrations.AddField(
            model_name="periodepaie",
            name="entreprise_libelle",
            field=models.CharField(blank=True, max_length=240),
        ),
        migrations.AddField(
            model_name="parametrepaie",
            name="entreprise_source",
            field=models.CharField(blank=True, db_index=True, max_length=80),
        ),
        migrations.AddField(
            model_name="parametrepaie",
            name="entreprise_reference",
            field=models.CharField(blank=True, db_index=True, max_length=255),
        ),
        migrations.AddField(
            model_name="parametrepaie",
            name="entreprise_libelle",
            field=models.CharField(blank=True, max_length=240),
        ),
        migrations.AddField(
            model_name="reglepaie",
            name="entreprise_source",
            field=models.CharField(blank=True, db_index=True, max_length=80),
        ),
        migrations.AddField(
            model_name="reglepaie",
            name="entreprise_reference",
            field=models.CharField(blank=True, db_index=True, max_length=255),
        ),
        migrations.AddField(
            model_name="reglepaie",
            name="entreprise_libelle",
            field=models.CharField(blank=True, max_length=240),
        ),
        migrations.AddField(
            model_name="variablepaiemensuelle",
            name="entreprise_source",
            field=models.CharField(blank=True, db_index=True, max_length=80),
        ),
        migrations.AddField(
            model_name="variablepaiemensuelle",
            name="entreprise_reference",
            field=models.CharField(blank=True, db_index=True, max_length=255),
        ),
        migrations.AddField(
            model_name="variablepaiemensuelle",
            name="entreprise_libelle",
            field=models.CharField(blank=True, max_length=240),
        ),
        migrations.AddField(
            model_name="rubriquepaie",
            name="entreprise_source",
            field=models.CharField(blank=True, db_index=True, max_length=80),
        ),
        migrations.AddField(
            model_name="rubriquepaie",
            name="entreprise_reference",
            field=models.CharField(blank=True, db_index=True, max_length=255),
        ),
        migrations.AddField(
            model_name="rubriquepaie",
            name="entreprise_libelle",
            field=models.CharField(blank=True, max_length=240),
        ),
        migrations.AddField(
            model_name="paiementsalarial",
            name="cle_idempotence",
            field=models.CharField(
                blank=True, max_length=120, null=True, unique=True
            ),
        ),
        migrations.AddField(
            model_name="paiementsalarial",
            name="compte_reference",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AlterField(
            model_name="parametrepaie",
            name="entreprise_id",
            field=models.CharField(
                blank=True, db_index=True, default="", max_length=255
            ),
        ),
        migrations.AlterField(
            model_name="rubriquepaie",
            name="code",
            field=models.CharField(db_index=True, max_length=20),
        ),
        migrations.RunPython(
            migrer_entreprises_legacy,
            retour_entreprises_legacy,
        ),
        migrations.AlterUniqueTogether(
            name="echeancesalariale",
            unique_together=set(),
        ),
        migrations.AlterUniqueTogether(
            name="periodepaie",
            unique_together=set(),
        ),
        migrations.RemoveConstraint(
            model_name="reglepaie",
            name="paie_regle_version_unique",
        ),
        migrations.RemoveConstraint(
            model_name="variablepaiemensuelle",
            name="paie_variable_unique",
        ),
        migrations.RemoveIndex(
            model_name="echeancesalariale",
            name="django_paie_employe_content_type_employe_object_id_idx",
        ),
        migrations.RemoveIndex(
            model_name="echeancesalariale",
            name="django_paie_entreprise_id_statut_idx",
        ),
        migrations.RemoveIndex(
            model_name="echeancesalariale",
            name="django_paie_annee_mois_entreprise_id_idx",
        ),
        migrations.AddIndex(
            model_name="echeancesalariale",
            index=models.Index(
                fields=["employe_content_type", "employe_object_id"],
                name="paie_ech_emp_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="echeancesalariale",
            index=models.Index(
                fields=[
                    "entreprise_source",
                    "entreprise_reference",
                    "statut",
                ],
                name="paie_ech_ent_stat_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="echeancesalariale",
            index=models.Index(
                fields=[
                    "annee",
                    "mois",
                    "entreprise_source",
                    "entreprise_reference",
                ],
                name="paie_ech_per_ent_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="echeancesalariale",
            constraint=models.UniqueConstraint(
                fields=(
                    "employe_content_type",
                    "employe_object_id",
                    "mois",
                    "annee",
                    "entreprise_source",
                    "entreprise_reference",
                ),
                name="paie_echeance_unique_entreprise",
            ),
        ),
        migrations.AddConstraint(
            model_name="periodepaie",
            constraint=models.UniqueConstraint(
                fields=(
                    "mois",
                    "annee",
                    "entreprise_source",
                    "entreprise_reference",
                ),
                name="paie_periode_unique_entreprise",
            ),
        ),
        migrations.AddConstraint(
            model_name="periodepaie",
            constraint=models.CheckConstraint(
                condition=models.Q(mois__gte=1, mois__lte=12),
                name="paie_periode_mois_valide",
            ),
        ),
        migrations.AddConstraint(
            model_name="periodepaie",
            constraint=models.CheckConstraint(
                condition=models.Q(annee__gte=2000, annee__lte=2100),
                name="paie_periode_annee_valide",
            ),
        ),
        migrations.AddConstraint(
            model_name="parametrepaie",
            constraint=models.UniqueConstraint(
                fields=("entreprise_source", "entreprise_reference"),
                name="paie_parametre_unique_entreprise",
            ),
        ),
        migrations.AddConstraint(
            model_name="reglepaie",
            constraint=models.UniqueConstraint(
                fields=(
                    "pays",
                    "organisme",
                    "version",
                    "entreprise_source",
                    "entreprise_reference",
                ),
                name="paie_regle_version_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="variablepaiemensuelle",
            constraint=models.UniqueConstraint(
                fields=(
                    "employe_content_type",
                    "employe_object_id",
                    "mois",
                    "annee",
                    "entreprise_source",
                    "entreprise_reference",
                ),
                name="paie_variable_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="rubriquepaie",
            constraint=models.UniqueConstraint(
                fields=(
                    "entreprise_source",
                    "entreprise_reference",
                    "code",
                ),
                name="paie_rubrique_code_unique_entreprise",
            ),
        ),
        migrations.CreateModel(
            name="EvenementPaie",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "entreprise_source",
                    models.CharField(blank=True, db_index=True, max_length=80),
                ),
                (
                    "entreprise_reference",
                    models.CharField(blank=True, db_index=True, max_length=255),
                ),
                (
                    "entreprise_libelle",
                    models.CharField(blank=True, max_length=240),
                ),
                (
                    "entreprise_id",
                    models.CharField(
                        blank=True, db_index=True, default="", max_length=255
                    ),
                ),
                (
                    "action",
                    models.CharField(db_index=True, max_length=80),
                ),
                (
                    "type_objet",
                    models.CharField(db_index=True, max_length=80),
                ),
                (
                    "objet_id",
                    models.CharField(
                        blank=True, db_index=True, default="", max_length=120
                    ),
                ),
                (
                    "reference",
                    models.CharField(
                        blank=True, db_index=True, default="", max_length=160
                    ),
                ),
                (
                    "donnees",
                    models.JSONField(blank=True, default=dict),
                ),
                (
                    "cree_le",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "acteur",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="evenements_paie",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Événement de paie",
                "verbose_name_plural": "Événements de paie",
                "ordering": ["-cree_le", "-id"],
            },
        ),

        migrations.AddConstraint(
            model_name="echeancesalariale",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(entreprise_source="", entreprise_reference="")
                    | (~models.Q(entreprise_source="") & ~models.Q(entreprise_reference=""))
                ),
                name="django_paie_echeancesalariale_ent_coherent",
            ),
        ),
        migrations.AddConstraint(
            model_name="periodepaie",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(entreprise_source="", entreprise_reference="")
                    | (~models.Q(entreprise_source="") & ~models.Q(entreprise_reference=""))
                ),
                name="django_paie_periodepaie_ent_coherent",
            ),
        ),
        migrations.AddConstraint(
            model_name="parametrepaie",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(entreprise_source="", entreprise_reference="")
                    | (~models.Q(entreprise_source="") & ~models.Q(entreprise_reference=""))
                ),
                name="django_paie_parametrepaie_ent_coherent",
            ),
        ),
        migrations.AddConstraint(
            model_name="reglepaie",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(entreprise_source="", entreprise_reference="")
                    | (~models.Q(entreprise_source="") & ~models.Q(entreprise_reference=""))
                ),
                name="django_paie_reglepaie_ent_coherent",
            ),
        ),
        migrations.AddConstraint(
            model_name="variablepaiemensuelle",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(entreprise_source="", entreprise_reference="")
                    | (~models.Q(entreprise_source="") & ~models.Q(entreprise_reference=""))
                ),
                name="django_paie_variablepaiemensuelle_ent_coherent",
            ),
        ),
        migrations.AddConstraint(
            model_name="rubriquepaie",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(entreprise_source="", entreprise_reference="")
                    | (~models.Q(entreprise_source="") & ~models.Q(entreprise_reference=""))
                ),
                name="django_paie_rubriquepaie_ent_coherent",
            ),
        ),
        migrations.AddConstraint(
            model_name="evenementpaie",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(entreprise_source="", entreprise_reference="")
                    | (~models.Q(entreprise_source="") & ~models.Q(entreprise_reference=""))
                ),
                name="django_paie_evenementpaie_ent_coherent",
            ),
        ),
    ]
