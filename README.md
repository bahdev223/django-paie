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
    "CONTRAT_MODEL": "mon_app.Contrat",
    "ABSENCE_MODEL": "mon_app.Absence",
    "RH_ADAPTER": "mon_projet.paie.MonRHAdapter",
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
- Variables mensuelles : primes, indemnités, heures supplémentaires, avantages,
  absences, prêts/avances, retenues, rappels, congés et régularisations
- Règles légales versionnées par pays, organisme, entreprise et dates d'effet
- Calcul automatique CNSS, AMO, ITS (barèmes Mali)
- Bulletins détaillés
- Cotisations salariales et patronales
- Exports PDF et Excel

En mode multi-entreprise, l'utilisateur et l'employé doivent tous les deux porter
le champ configuré par `EMPLOYE_ENTREPRISE_FIELD` (par défaut `entreprise_id`).
Un rattachement absent ou différent entraîne un refus d'accès.
