API_DOCS = """\
# API REST django-paie

Toutes les reponses sont en JSON avec le format `{"data": ...}` ou `{"error": "..."}`.

## Authentification

Requiert un utilisateur Django connecte avec les permissions appropriees.

Permissions requises :

| Permission | Endpoints |
|---|---|
| `django_paie.view_echeancesalariale` | GET echeances, stats, dashboard |
| `django_paie.add_echeancesalariale` | POST echeances |
| `django_paie.view_paiementsalarial` | GET paiements |
| `django_paie.add_paiementsalarial` | POST paiements, avance |
| `django_paie.change_paiementsalarial` | POST annuler paiement |
| `django_paie.add_bulletinpaie` | POST bulletins/calculer, masse/calculer |

---

## Echeances

### `GET /api/echeances/`

Liste des echeances.

**Parametres (query string) :**

| Nom | Type | Description |
|---|---|---|
| `statut` | string | Filtrer par statut (`A_PAYER`, `PAYE`, `EN_RETARD`, ...) |
| `periode` | string | Filtrer par periode (`MM/AAAA`) |
| `employe_id` | string | Filtrer par ID employe |

**Reponse :**

```json
{"data": [{"id": 1, "employe_id": "42", "periode": "07/2026", "mois": 7, "annee": 2026, "statut": "A_PAYER", ...}], "count": 1}
```

### `POST /api/echeances/`

Creer une echeance.

```json
{"employe_id": "42", "periode": "07/2026", "montant_brut": 50000, "montant_net": 48000, "date_echeance": "2026-07-05"}
```

`montant_net` et `date_echeance` sont optionnels.

### `GET /api/echeances/<id>/`

Detail d'une echeance avec ses paiements.

### `POST /api/echeances/<id>/`

Actions sur une echeance.

**Action `cloturer` :** `{"action": "cloturer"}` refuse si `reste_a_payer > 0`.

---

## Paiements

### `GET /api/paiements/`

Liste des paiements. Parametre : `?echeance_id=1`.

### `POST /api/paiements/`

```json
{"echeance_id": 1, "montant": 50000, "date_paiement": "2026-07-15", "type_paiement": "PAIEMENT"}
```

`type_paiement` : `PAIEMENT`, `AVANCE`, `ARRIERE`, `REGULARISATION` (defaut: `PAIEMENT`).

### `POST /api/paiements/<id>/annuler/`

Annuler un paiement.

---

## Avance

### `POST /api/avance/`

```json
{"employe_id": "42", "periode_source": "07/2026", "montant": 20000, "periode_cible": "10/2026"}
```

`periode_cible` optionnelle (defaut: mois suivant).

---

## Bulletins (mode COMPLET)

### `GET /api/bulletins/`

Parametres : `?employe_id=`, `?periode=`.

### `POST /api/bulletins/calculer/`

```json
{"employe_id": "42", "periode": "07/2026"}
```

### `POST /api/masse/calculer/`

```json
{"periode": "07/2026", "employes_ids": ["42", "43", "44"]}
```

---

## Statistiques

### `GET /api/stats/resume/?annee=2026`

### `GET /api/stats/arrieres/`

### `GET /api/stats/avances/`

---

## Dashboard

### `GET /api/dashboard/`

---

## Codes d'erreur

| Statut | Signification |
|---|---|
| 200 | Succes |
| 201 | Cree |
| 400 | Requete invalide |
| 403 | Permission refusee |
| 404 | Ressource introuvable |

Toutes les erreurs retournent `{"error": "message"}`.

---

## Filtrage multi-entreprise

Quand `MODE_PAR_ENTREPRISE = True`, filtre automatique par `entreprise_id`.
"""
