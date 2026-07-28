from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("django_paie", "0002_bulletinpaie_cotisationbulletin_lignebulletin_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="paiementsalarial",
            name="type_paiement",
            field=models.CharField(
                choices=[
                    ("PAIEMENT", "Paiement"),
                    ("AVANCE", "Avance"),
                    ("ARRIERE", "Arriéré"),
                    ("REGULARISATION", "Régularisation"),
                ],
                default="PAIEMENT",
                max_length=20,
            ),
        ),
    ]
