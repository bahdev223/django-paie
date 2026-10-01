# django-paie

Moteur de paie modulaire pour Django, conçu pour rester indépendant du moteur RH.

- **Mode SIMPLE** : PME, commerces, restaurants — échéances salariales et paiements
- **Mode COMPLET** : bulletins, rubriques, variables, cotisations, règles et exports
- **Multi-entreprise** : isolation stricte avec resolver serveur et compatibilité legacy
- **RH Adapter** : contrat stable avec `django-rh` ou tout autre système RH

```python
INSTALLED_APPS = [
    "django_paie",
]

DJANGO_PAIE = {
    "MODE": "SIMPLE",
    "MODE_PAR_ENTREPRISE": True,
    "ENTREPRISE_RESOLVER": "core.tenancy.resolve_entreprise",

    "EMPLOYE_MODEL": "rh.Employe",
    "CONTRAT_MODEL": "rh.Contrat",
    "ABSENCE_MODEL": "rh.Absence",
    "POINTAGE_MODEL": "rh.Pointage",
    "RH_ADAPTER": "rh.integrations.DjangoPaieAdapter",

    "DEVISE": "XOF",
    "JOUR_PAIEMENT": 5,
}
```

## Responsabilités

`django-paie` ne possède pas les employés ni les contrats. Le moteur RH reste
la source de vérité pour :

- employés ;
- contrats et avenants ;
- absences et congés ;
- pointages et temps de travail ;
- calendrier/jours ouvrés.

`django-paie` possède :

- périodes de paie ;
- échéances salariales ;
- variables mensuelles ;
- rubriques et règles ;
- bulletins ;
- cotisations ;
- paiements, avances et arriérés ;
- clôtures, statistiques et audit.

## Mode SIMPLE

- échéance par employé/période/entreprise ;
- paiements totaux, partiels et multiples ;
- avances rattachées à la période cible ;
- arriérés ;
- idempotence des paiements ;
- référence de compte de trésorerie ;
- détection des impayés.

## Mode COMPLET

- rubriques globales + surcharges par entreprise ;
- variables mensuelles ;
- règles légales versionnées ;
- CNSS / AMO / ITS ;
- bulletins détaillés ;
- cotisations salariales et patronales ;
- snapshot RH historique sur l'échéance ;
- exports PDF / Excel ;
- masse salariale et coût employeur.

Le coût employeur n'est jamais estimé avec des taux codés en dur : il repose sur
les cotisations réellement calculées.

## Multi-entreprise

Le contexte entreprise canonique est :

```text
entreprise_source
entreprise_reference
entreprise_libelle
```

Le resolver est exécuté côté serveur :

```python
def resolve_entreprise(request):
    organisation = request.organisation_active
    return {
        "source": "saheltech",
        "reference": str(organisation.pk),
        "libelle": organisation.nom,
    }
```

Le client HTTP ne choisit jamais directement son entreprise.

Quand `MODE_PAR_ENTREPRISE=True`, API, services, vues HTML et Django Admin
refusent l'accès si aucun contexte fiable n'est disponible.

### Compatibilité v0.3

L'ancien champ `entreprise_id` est conservé pendant la transition. Les anciennes
valeurs sont migrées automatiquement vers :

```text
source = legacy
reference = <ancienne entreprise_id>
```

Les nouvelles intégrations utilisent une clé legacy composée
`source:reference` afin d'éviter toute collision entre plateformes.

## Rubriques

Une rubrique globale est utilisable par toutes les entreprises. Une entreprise
peut définir une rubrique portant le même code ; sa version prend alors priorité.

```text
PRIME [global]
        ↓ surcharge
PRIME [Entreprise A]
```

## RH Adapter

Un adaptateur peut fournir :

```python
get_employe(employe_id)
get_contrat_actif(employe_id)
get_absences_mois(employe_id, annee, mois)
get_heures_mois(employe_id, annee, mois)
get_jours_ouvres(employe_id, annee, mois)
get_variables_mois(employe_id, annee, mois)
get_snapshot_employe(employe, contrat)
```

Les heures supplémentaires utilisent la durée mensuelle du contrat, et les
retenues d'absence utilisent les jours ouvrés fournis par RH/calendrier.

## Sécurité financière

- verrouillage transactionnel ;
- périodes clôturées non modifiables ;
- bulletin validé/clôturé non recalculable ;
- bulletin déjà payé non recalculable ;
- paiement validé non déplaçable ;
- paiements idempotents ;
- journal `EvenementPaie` ;
- commandes batch explicites en multi-entreprise.

## Migration v0.4

```bash
python manage.py migrate
pytest
```

Avant déploiement, exécuter la suite sur la base cible (PostgreSQL recommandé
pour valider réellement les verrous `select_for_update`).
