# Règles et Pièges — django-paie

Ce document recense tous les problèmes rencontrés pendant le développement de `django-paie`,
les solutions appliquées, et les règles à suivre pour éviter que les futurs agents ou
développeurs ne tombent dans les mêmes pièges.

---

## 1. Architecture générale

### 1.1. Django App vs Package Python

| À ne pas faire | À faire |
|---|---|
| Nommer le module Python `django-paie` (avec un tiret) | Le module Python doit être `django_paie` (underscore). Le nom du package PyPI peut être `django-paie` |

**Règle :** `pyproject.toml` utilise `django-paie` comme `name`, mais le dossier du module
est `django_paie/`. L'installation se fait via `pip install -e .` (mode développement).

### 1.2. Build system

**Problème :** Le `pyproject.toml` doit explicitement inclure les fichiers non-Python
(templates, migrations) dans le wheel, sinon ils sont absents à l'installation.

**Solution :**
```toml
[tool.setuptools.package-data]
django_paie = ["templates/**/*.html", "migrations/*.py"]
```

**Règle :** Toujours vérifier que `package-data` contient les templates et migrations.

---

## 2. Modèles Django

### 2.1. GenericForeignKey pour l'employé

**Problème :** On ne veut pas hardcoder un modèle Employé spécifique. Chaque projet peut
avoir son propre modèle `rh.Employe`, `auth.User`, etc.

**Solution :** `EcheanceSalariale` utilise `GenericForeignKey` :

```python
employe_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
employe_object_id = models.CharField(max_length=255)
employe = GenericForeignKey("employe_content_type", "employe_object_id")
```

**Règle :** Ne JAMAIS mettre de `ForeignKey` direct vers un modèle employé. Toujours
utiliser `GenericForeignKey` + un setting `EMPLOYE_MODEL`.

### 2.2. Montants monétaires (XOF)

**Règle :** Tous les champs monétaires utilisent :
```python
models.DecimalField(max_digits=14, decimal_places=0)
```

Le XOF (Franc CFA) n'a pas de sous-unités. Pas de `float` — jamais.

### 2.3. Mois et année en champs séparés

**Problème :** On pourrait stocker la période comme `CharField("MM/AAAA")`.

**Solution :** On utilise `PositiveSmallIntegerField` pour `mois` et `annee`
séparément. Cela permet les tris, les index, et les contraintes d'unicité.

```python
mois = models.PositiveSmallIntegerField()
annee = models.PositiveSmallIntegerField()
```

**Règle :** Toujours `PositiveSmallIntegerField`, jamais `CharField` pour les périodes.

### 2.4. Gestion des index

**Problème :** Les noms d'index auto-générés changent entre versions de Django.
Django 5.2 génère des noms plus courts que Django 4.2. Cela produit des opérations
`RenameIndex` non désirées dans les migrations automatiques.

**Solution :** Spécifier des noms d'index explicites dans les modèles OU supprimer
les `RenameIndex` des migrations générées automatiquement.

**Règle :** Après `makemigrations`, vérifier et supprimer les `RenameIndex` si les
noms sont déjà définis dans la migration précédente.

### 2.5. Contrainte d'unicité

```python
unique_together = ["employe_content_type", "employe_object_id", "mois", "annee", "entreprise_id"]
```

**Raison :** Un employé ne peut avoir qu'une seule échéance par mois/année/entreprise.

---

## 3. La méthode `mettre_a_jour_statut` — PIÈGE FATAL

### 3.1. Le bug du `montant_paye` perdu

**Problème :** Dans `echeance.py`, la méthode `mettre_a_jour_statut()` faisait :
```python
self.save(update_fields=["statut"])
```

Mais `montant_paye` était modifié AVANT l'appel (dans `_recalculer_echeance()`).
Comme `update_fields` ne listait que `statut`, la modification de `montant_paye`
était perdue. `refresh_from_db()` renvoyait toujours 0.

**Solution :**
```python
self.save(update_fields=["statut", "montant_paye"])
```

**Règle :** Quand une méthode modifie plusieurs champs puis appelle `save(update_fields=...)`,
TOUS les champs modifiés doivent être listés dans `update_fields`.

### 3.2. Le piège des dates

**Problème :** `mettre_a_jour_statut()` utilise `date.today()` pour déterminer le statut.
Si l'échéance est dans le passé et que le paiement est partiel, le statut devient
`EN_RETARD` au lieu de `PARTIELLEMENT_PAYE`.

```python
elif self.montant_paye < self.montant_net:
    if self._a_paiements_futurs():
        self.statut = "PAYE_EN_AVANCE"
    elif today > self.date_echeance:
        self.statut = "EN_RETARD"
    else:
        self.statut = "PARTIELLEMENT_PAYE"
```

**Règle :** Les tests utilisant des périodes passées par rapport à `date.today()`
vont planter. Toujours utiliser des périodes futures (ex: `"09/2026"` au lieu de `"07/2026"`)
dans les tests, ou mocker `date.today()`.

---

## 4. Service Layer — Paiements

### 4.1. Toujours passer par le service, pas par le modèle direct

**Problème :** `PaiementCreateView` utilisait `ModelForm.save()` directement, ce qui
créait un `PaiementSalarial` mais ne passait pas par `ModeSimpleService.enregistrer_paiement()`.
La logique métier (détection avance/arriéré, multi-mois, `select_for_update`) était
contournée.

**Solution :** `PaiementCreateView` utilise `FormView` + `ModeSimpleService.enregistrer_paiement()`.

**Règle :** Les vues ne doivent JAMAIS créer/modifier des modèles de paie directement.
Toujours passer par les services (`ModeSimpleService`, `ModeCompletService`).

### 4.2. `select_for_update` + `transaction.atomic()`

**Problème :** `PaiementSalarial.save()` utilise `select_for_update` sur l'échéance
pour éviter les paiements concurrents qui dépasseraient le montant dû. Mais cette
méthode est appelée DEPUIS `enregistrer_paiement()` qui a déjà sa propre
`with transaction.atomic()`. Cela crée des `atomic()` imbriqués.

```python
# dans enregistrer_paiement()
with transaction.atomic():
    echeance = EcheanceSalariale.objects.select_for_update().get(pk=echeance_id)
    ...
    paiement = PaiementSalarial.objects.create(...)  # appelle save() avec son propre atomic()

# dans PaiementSalarial.save()
def save(self, *args, **kwargs):
    with transaction.atomic():  # savepoint imbriqué
        echeance = EcheanceSalariale.objects.select_for_update().get(pk=self.echeance_id)
        super().save(*args, **kwargs)
        self._recalculer_echeance()
```

**Risque :** Avec SQLite et les `atomic()` imbriqués, `select_for_update` peut
échouer silencieusement. Le `savepoint` créé par l'`atomic()` imbriqué peut ne
pas supporter `FOR UPDATE`.

**Solution adoptée :** Conserver la structure mais être conscient que le
`select_for_update` du `save()` est redondant avec celui du service. Une
refactorisation future pourrait :
1. Supprimer le `select_for_update` du `save()` (le service a déjà le lock)
2. OU extraire la logique de `_recalculer_echeance` dans un signal `post_save`

### 4.3. Détection avance/arriéré

**Règle :** Le type de paiement est détecté automatiquement si non spécifié :

```python
def _detecter_type_paiement(self, echeance, date_paiement, mois_concerne, annee_concerne):
    if (annee_concerne, mois_concerne) > (date_paiement.year, date_paiement.month):
        return "AVANCE"
    if date_paiement > echeance.date_fin:
        return "ARRIERE"
    return "PAIEMENT"
```

### 4.4. Paiement d'avance — Rattachement à la bonne période

**Problème :** Un paiement d'avance pour août était attaché à l'échéance de juillet
(la période courante) au lieu de celle d'août. Résultat : l'échéance de juillet
était marquée "trop-perçu" et celle d'août restait impayée.

**Solution :** Quand le type est `AVANCE`, le service crée/trouve l'échéance de la
période cible et y attache le paiement.

```python
if type_paiement == "AVANCE":
    target_mois, target_annee = self._periode_suivante(echeance.mois, echeance.annee)
    target_echeance, _ = EcheanceSalariale.objects.get_or_create(...)
    echeance = EcheanceSalariale.objects.select_for_update().get(pk=target_echeance.pk)
    mois_concerne, annee_concerne = target_mois, target_annee
```

**Règle :** Un paiement d'avance doit toujours être attaché à l'échéance de la
période qu'il concerne, pas à la période courante.

### 4.5. `date_echeance` — Utiliser la période demandée

**Problème :** La `date_echeance` de l'échéance créée par un paiement d'avance
utilisait le mois en cours au lieu du mois de la période cible.

**Solution :** Utiliser `target_mois` et `target_annee` pour calculer la `date_echeance`.

```python
"date_echeance": date(target_annee, target_mois, paie_settings.JOUR_PAIEMENT),
```

---

## 5. Mode COMPLET — Modèles et persistance

### 5.1. Dataclasses vs Django Models

**Règle :** Le `MoteurPaie` utilise des dataclasses pures (`BulletinPaie`, `LignePaie`,
`RubriquePaie` dans `complet/modeles.py`). La persistance est assurée par les modèles
Django (`django_paie/models/bulletin.py`, `rubrique.py`). La couche service
(`ModeCompletService`) fait la conversion.

```
MoteurPaie (dataclasses) → ModeCompletService._sauvegarder_bulletin() → Django Models
```

### 5.2. Cycle de vie d'un bulletin COMPLET

```python
# 1. Calcul
bulletin_dataclass = MoteurPaie.calculer_bulletin(employe_id, periode)

# 2. Persistance (dans _sauvegarder_bulletin)
#    a. Crée/met à jour EcheanceSalariale (montant_brut, montant_net)
#    b. Crée/met à jour BulletinPaie (1:1 avec EcheanceSalariale)
#    c. Supprime les LigneBulletin existantes
#    d. Recrée les LigneBulletin à partir du dataclass
echeance = self._sauvegarder_bulletin(employe, periode, bulletin_dataclass)
```

**Règle :** Les lignes sont supprimées puis recréées à chaque calcul (pas de mise à jour
individuelle). Le statut initial est `BROUILLON` (ou `VALIDE` si verrouillé).

### 5.3. Rubriques — Code durci vs Base de données

**Problème :** Les rubriques (BASE, CNSS, AMO, ITS) sont définies en dur dans
`MoteurPaie._enregistrer_rubriques_defaut()`. Mais les `LigneBulletin` en DB ont
besoin d'une référence à une `RubriquePaie` (ForeignKey).

**Solution :** La migration `0002` seed les rubriques par défaut. Le service utilise
`get_or_create` pour être robuste :

```python
rubrique, _ = RubriquePaie.objects.get_or_create(
    code=ligne.rubrique_code,
    defaults={"libelle": ligne.rubrique_code, "type_rubrique": ...},
)
```

**Règle :** Toujours utiliser `get_or_create` (pas `get`) pour les rubriques dans le
service, car la base peut ne pas encore avoir la rubrique si la data migration n'a
pas été exécutée.

---

## 6. Vues et Templates

### 6.1. EnterpriseFilterMixin

**Problème :** Le filtrage par entreprise est différent pour `PaiementSalarial`
(qui utilise `echeance__entreprise_id`) et les autres modèles (qui ont
`entreprise_id` directement).

**Solution :**
```python
class EnterpriseFilterMixin:
    def get_queryset(self):
        qs = super().get_queryset()
        if model and model is PaiementSalarial:
            qs = qs.filter(echeance__entreprise_id=entreprise_id)
        elif entreprise_id:
            qs = qs.filter(entreprise_id=entreprise_id)
        return qs
```

### 6.2. Permissions

Toutes les vues utilisent `PermissionRequiredMixin`. Les permissions sont créées
par la commande `paie_init`.

**Règle :** `PermissionRequiredMixin` sur TOUTES les vues. Utiliser
`creer_permissions_paie()` pour les initialiser.

---

## 7. Commandes de gestion

### 7.1. `paie_init` — Crée les permissions

```python
class Command(BaseCommand):
    help = "Initialise les permissions de paie"

    def handle(self, *args, **options):
        creer_permissions_paie()
```

### 7.2. `paie_generer_echeances` — Création en masse

### 7.3. `paie_actualiser_statuts` — Met à jour les statuts EN_RETARD

---

## 8. Signaux

**Problème :** Les signaux (`signals.py`) doivent être importés au moment du
démarrage de Django, mais sans créer d'imports circulaires.

**Solution :** L'import se fait dans `apps.py.ready()` :

```python
class DjangoPaieConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "django_paie"

    def ready(self):
        import django_paie.signals  # noqa
```

**Règle :** L'import du module signals doit être dans `ready()` et précédé de
`# noqa` pour éviter les warnings d'import inutilisé.

---

## 9. Tests

### 9.1. Dépendance à `date.today()`

**Problème :** Les tests qui créent des échéances avec des périodes passées par
rapport à `date.today()` échouent parce que `mettre_a_jour_statut()` les marque
comme `EN_RETARD`.

**Règle :** Utiliser des périodes futures dans les tests (`"09/2026"` quand on est
en juillet 2026). Ne JAMAIS utiliser `"01/2000"` ou d'autres dates passées.

### 9.2. `select_for_update` avec SQLite

**Règle :** Les tests avec SQLite et `select_for_update` peuvent avoir des
comportements différents de PostgreSQL. Toujours tester en production avec
la base cible.

### 9.3. Vérifier `montant_paye` après `refresh_from_db()`

**Règle :** Après un paiement, toujours faire `echeance.refresh_from_db()` avant
de vérifier `montant_paye` — ne pas se fier à l'objet en mémoire.

---

## 10. Exports

### 10.1. PDF (ReportLab)

L'export PDF utilise `reportlab`. Si `reportlab` n'est pas installé, il y a un
fallback HTML.

**Règle :** `reportlab` et `openpyxl` sont optionnels dans les dépendances.
Le code doit gérer leur absence (`ImportError`).

### 10.2. Excel (openpyxl)

Même règle que pour PDF.

---

## 11. Statistiques

### 11.1. `cout_employeur` — Attention au type Decimal

**Problème :** Le coût employeur utilisait `float * Decimal` qui lève `TypeError`.

```python
# Bogue :
cout = montant_brut * float(0.072)  # TypeError

# Correction :
cout = montant_brut * Decimal("0.072")
```

**Règle :** Ne JAMAIS multiplier un `Decimal` par un `float`. Utiliser
`Decimal("0.072")` ou `Decimal(72) / Decimal(1000)`.

### 11.2. Alerte clôture

**Problème :** L'alerte vérifiait un seuil arbitraire (`non_cloture > 150`) au lieu
d'utiliser directement `PeriodePaie.objects.filter(est_cloturee=False)`.

**Règle :** Les alertes doivent être basées sur des requêtes directes aux modèles,
pas sur des seuils magiques.

---

## 12. Migration 0002 — Écueils

### 12.1. Dépendance à `AUTH_USER_MODEL`

`ValidationPaie.valide_par` est une FK vers `settings.AUTH_USER_MODEL`. Dans la
migration, cela nécessite :

```python
dependencies = [
    ("django_paie", "0001_initial"),
    migrations.swappable_dependency(settings.AUTH_USER_MODEL),
]
```

### 12.2. Data migration pour les rubriques

Les rubriques par défaut (BASE, CNSS, AMO, ITS, etc.) sont insérées via `RunPython`
dans la même migration que la création des tables. Cela permet d'avoir les rubriques
disponibles immédiatement après `migrate`.

### 12.3. Supprimer les `RenameIndex`

Django 5.2 peut générer des `RenameIndex` pour les index de `0001_initial`. Ces
opérations doivent être supprimées de la migration générée car les noms d'index
sont déjà explicitement définis dans `0001_initial`.

---

## 13. Checklist avant chaque commit

- [ ] `python -m build` produit un `.whl` et `.tar.gz` valides
- [ ] Le `.whl` contient les templates (`templates/**/*.html`)
- [ ] Le `.whl` contient les migrations (`migrations/*.py`)
- [ ] `mettre_a_jour_statut()` liste TOUS les champs modifiés dans `update_fields`
- [ ] Aucun `float * Decimal` dans le code
- [ ] `date.today()` n'est pas utilisé dans les tests avec des périodes fixes
- [ ] Les vues utilisent le service layer, pas `Model.save()` direct
- [ ] Les paiements d'avance sont attachés à la période cible
- [ ] `GenericForeignKey` est utilisé pour l'employé
- [ ] Les montants sont en `Decimal(max_digits=14, decimal_places=0)`
