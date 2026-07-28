# API REST django-paie

Toutes les réponses sont en JSON avec le format `{"data": ...}` ou `{"error": "..."}`.

## Authentification

Requiert un utilisateur Django connecté avec les permissions appropriées.

Permissions requises :
| Permission | Endpoints |
|---|---|
| `django_paie.view_echeancesalariale` | GET echeances, stats, dashboard |
| `django_paie.add_echeancesalariale` | POST echeances |
| `django_paie.view_paiementsalarial` | GET paiements |
| `django_paie.add_paiementsalarial` | POST paiements, avance |
| `django_paie.annuler_paiement` | POST annuler paiement |
| `django_paie.cloturer_periode` | POST clôturer une période |
| `django_paie.add_bulletinpaie` | POST bulletins/calculer, masse/calculer |

---

## Échéances

### `GET /api/echeances/`

Liste des échéances.

**Paramètres (query string) :**
| Nom | Type | Description |
|---|---|---|
| `statut` | string | Filtrer par statut (`A_PAYER`, `PAYE`, `EN_RETARD`, ...) |
| `periode` | string | Filtrer par période (`MM/AAAA`) |
| `employe_id` | string | Filtrer par ID employé |

**Réponse :**
```json
{
  "data": [
    {
      "id": 1,
      "employe_id": "42",
      "periode": "07/2026",
      "mois": 7,
      "annee": 2026,
      "date_debut": "2026-07-01",
      "date_fin": "2026-07-31",
      "date_echeance": "2026-07-05",
      "montant_brut": 50000,
      "montant_net": 48000,
      "montant_paye": 0,
      "reste_a_payer": 48000,
      "trop_percu": 0,
      "statut": "A_PAYER",
      "statut_display": "À payer",
      "mode": "SIMPLE",
      "entreprise_id": ""
    }
  ],
  "count": 1
}
```

### `POST /api/echeances/`

Créer une échéance.

**Corps (JSON) :**
```json
{
  "employe_id": "42",
  "periode": "07/2026",
  "montant_brut": 50000,
  "montant_net": 48000,
  "date_echeance": "2026-07-05"
}
```

`montant_net` et `date_echeance` sont optionnels.

### `GET /api/echeances/<id>/`

Détail d'une échéance avec ses paiements.

### `POST /api/echeances/<id>/`

Actions sur une échéance.

**Action `cloturer` :**
```json
{"action": "cloturer"}
```
Refuse si `reste_a_payer > 0`.

---

## Paiements

### `GET /api/paiements/`

Liste des paiements.

**Paramètres :**
| Nom | Type | Description |
|---|---|---|
| `echeance_id` | int | Filtrer par échéance |

### `POST /api/paiements/`

Créer un paiement.

```json
{
  "echeance_id": 1,
  "montant": 50000,
  "date_paiement": "2026-07-15",
  "type_paiement": "PAIEMENT",
  "notes": ""
}
```

`type_paiement` peut être `PAIEMENT`, `AVANCE`, `ARRIERE`, `REGULARISATION` (défaut : `PAIEMENT`).  
`date_paiement` et `notes` sont optionnels.

### `POST /api/paiements/<id>/annuler/`

Annuler un paiement.

---

## Avance

### `POST /api/avance/`

Enregistrer une avance sur salaire.

```json
{
  "employe_id": "42",
  "periode_source": "07/2026",
  "montant": 20000,
  "date_paiement": "2026-07-10",
  "periode_cible": "10/2026",
  "montant_mensuel": 50000,
  "notes": ""
}
```

- `periode_source` : période où le paiement est effectué.
- `periode_cible` : période concernée par l'avance (optionnelle, défaut : mois suivant).
- Le salaire de la période cible vient de l'échéance source ou d'une échéance
  antérieure. À défaut, `montant_mensuel` est obligatoire.

---

## Bulletins (mode COMPLET)

### `GET /api/bulletins/`

Liste des bulletins.

**Paramètres :**
| Nom | Type | Description |
|---|---|---|
| `employe_id` | string | Filtrer par employé |
| `periode` | string | Filtrer par période (`MM/AAAA`) |

### `POST /api/bulletins/calculer/`

Calculer et enregistrer un bulletin.

```json
{
  "employe_id": "42",
  "periode": "07/2026"
}
```

Retourne le bulletin complet avec lignes et cotisations.

Le calcul utilise la ligne `VariablePaieMensuelle` de l'employé et de la période :
primes, indemnités, heures supplémentaires et majoration, avantages en nature,
absences, prêts/avances récupérables, retenues personnalisées, rappels, congés,
régularisations et rubriques supplémentaires. Les règles `ReglePaie` applicables
à la date du bulletin sont utilisées pour CNSS, AMO et ITS.

### `POST /api/masse/calculer/`

Calculer la masse salariale pour plusieurs employés.

```json
{
  "periode": "07/2026",
  "employes_ids": ["42", "43", "44"]
}
```

---

## Statistiques

### `GET /api/stats/resume/`

Résumé annuel ou par période.

**Paramètres :**
| Nom | Type | Description |
|---|---|---|
| `annee` | int | Année (défaut : année courante) |
| `periode` | string | Si présent, résumé d'une seule période (`MM/AAAA`) |

### `GET /api/stats/arrieres/`

Liste des arriérés.

### `GET /api/stats/avances/`

Récapitulatif des avances.

---

## Dashboard

### `GET /api/dashboard/`

Tableau de bord complet.

**Paramètres :**
| Nom | Type | Description |
|---|---|---|
| `annee` | int | Année (défaut : année courante) |

Retourne : résumé, évolution mensuelle, arriérés, avances, alertes.  
En mode COMPLET : masse salariale + coût employeur.

---

## Codes d'erreur

| Statut | Signification |
|---|---|
| 200 | Succès |
| 201 | Créé |
| 400 | Requête invalide (paramètres manquants, validation) |
| 403 | Permission refusée |
| 404 | Ressource introuvable |

Toutes les erreurs retournent `{"error": "message"}`.

---

## Filtrage multi-entreprise

Quand `DJANGO_PAIE.MODE_PAR_ENTREPRISE = True`, l'API filtre automatiquement
les données par `entreprise_id` de l'utilisateur connecté. Un utilisateur sans
`entreprise_id` se voit refuser l'accès à toutes les données.
