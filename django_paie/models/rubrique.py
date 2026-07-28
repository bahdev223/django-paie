from django.db import models


class RubriquePaie(models.Model):
    TYPE_CHOICES = [
        ("gain", "Gain"),
        ("retenue", "Retenue"),
    ]

    code = models.CharField(max_length=20, unique=True)
    libelle = models.CharField(max_length=100)
    type_rubrique = models.CharField(max_length=10, choices=TYPE_CHOICES)
    imposable = models.BooleanField(default=True)
    cotisable = models.BooleanField(default=False)
    actif = models.BooleanField(default=True)
    ordre = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "Rubrique de paie"
        verbose_name_plural = "Rubriques de paie"
        ordering = ["ordre", "code"]

    def __str__(self):
        return f"{self.code} - {self.libelle}"
