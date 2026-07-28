# django-paie

Application de paie modulaire pour Django.

- **Mode SIMPLE** : pour PME, boutiques, restaurants — montant mensuel convenu, pas de calculs complexes
- **Mode COMPLET** : pour grandes entreprises — bulletins détaillés, cotisations, impôts, exports

```python
INSTALLED_APPS = [
    "django_paie",
]

DJANGO_PAIE = {
    "MODE": "SIMPLE",
    "EMPLOYE_MODEL": "mon_app.Employe",
    "DEVISE": "XOF",
}
```

## Fonctionnalités

### Mode SIMPLE

- Échéances salariales par employé/période
- Paiements (total, partiel, multiple)
- Avances et arriérés
- Détection des mois impayés
- Vue dashboard

### Mode COMPLET

- Rubriques de paie paramétrables
- Calcul automatique CNSS, AMO, ITS (barèmes Mali)
- Bulletins détaillés
- Cotisations salariales et patronales
- Exports PDF et Excel
