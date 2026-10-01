from datetime import date
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from django_paie.complet.integration import AdaptateurRHBase
from django_paie.models import (
    EcheanceSalariale,
    PaiementSalarial,
    PeriodePaie,
    RubriquePaie,
)
from django_paie.services import ModeSimpleService, StatistiquesPaieService
from django_paie.tenancy import ContexteEntreprise, resoudre_entreprise

User = get_user_model()


class ModernisationV04Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("payroll-user", password="x")

    def test_same_company_reference_can_exist_in_two_sources(self):
        a = PeriodePaie.from_libelle(
            "10/2026",
            entreprise_source="solarplus",
            entreprise_reference="ENT-001",
        )
        b = PeriodePaie.from_libelle(
            "10/2026",
            entreprise_source="fournea",
            entreprise_reference="ENT-001",
        )
        self.assertNotEqual(a.pk, b.pk)
        self.assertNotEqual(a.entreprise_id, b.entreprise_id)

    def test_company_rubric_overrides_global_rubric(self):
        RubriquePaie.objects.create(
            code="PRIME",
            libelle="Prime globale",
            type_rubrique="gain",
            ordre=10,
        )
        RubriquePaie.objects.create(
            entreprise_source="solarplus",
            entreprise_reference="ENT-001",
            code="PRIME",
            libelle="Prime Solarplus",
            type_rubrique="gain",
            ordre=10,
        )
        rubriques = RubriquePaie.actives_pour("solarplus", "ENT-001")
        prime = next(r for r in rubriques if r.code == "PRIME")
        self.assertEqual(prime.libelle, "Prime Solarplus")
        self.assertEqual(sum(1 for r in rubriques if r.code == "PRIME"), 1)

    @override_settings(
        DJANGO_PAIE={
            "MODE": "SIMPLE",
            "MODE_PAR_ENTREPRISE": True,
        }
    )
    def test_service_is_fail_closed_without_company(self):
        with self.assertRaises(ValueError):
            ModeSimpleService()

    @override_settings(
        DJANGO_PAIE={
            "MODE": "SIMPLE",
            "MODE_PAR_ENTREPRISE": True,
        }
    )
    def test_legacy_request_company_is_still_supported(self):
        request = SimpleNamespace(
            user=SimpleNamespace(
                entreprise_id="ENT-LEGACY",
                entreprise_nom="Ancienne entreprise",
            )
        )
        contexte = resoudre_entreprise(request)
        self.assertEqual(contexte.source, "legacy")
        self.assertEqual(contexte.reference, "ENT-LEGACY")
        self.assertEqual(contexte.legacy_id, "ENT-LEGACY")

    @override_settings(
        DJANGO_PAIE={
            "MODE": "SIMPLE",
            "MODE_PAR_ENTREPRISE": False,
            "JOUR_PAIEMENT": 5,
        }
    )
    def test_payment_idempotency(self):
        service = ModeSimpleService()
        echeance = service.creer_echeance(
            self.user,
            "10/2026",
            100000,
            100000,
        )
        first = service.enregistrer_paiement(
            echeance_id=echeance.pk,
            montant=25000,
            date_paiement=date(2026, 10, 5),
            cle_idempotence="PAY-UNIQUE-001",
        )
        second = service.enregistrer_paiement(
            echeance_id=echeance.pk,
            montant=25000,
            date_paiement=date(2026, 10, 5),
            cle_idempotence="PAY-UNIQUE-001",
        )
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(PaiementSalarial.objects.count(), 1)

    def test_rh_snapshot_accepts_legacy_contract_salary_name(self):
        adapter = AdaptateurRHBase()
        employe = SimpleNamespace(
            pk=1,
            matricule="EMP001",
            nom="DIOP",
            prenom="Awa",
            poste_code="COMPTA",
            departement_code="FIN",
        )
        contrat = SimpleNamespace(salaire_brut_mensuel=350000)
        snapshot = adapter.get_snapshot_employe(employe, contrat)
        self.assertEqual(snapshot["matricule"], "EMP001")
        self.assertEqual(snapshot["nom_complet"], "DIOP Awa")
        self.assertEqual(snapshot["salaire_contractuel"], 350000)

    @override_settings(
        DJANGO_PAIE={
            "MODE": "COMPLET",
            "MODE_PAR_ENTREPRISE": False,
        }
    )
    def test_employer_cost_is_not_invented_without_contributions(self):
        EcheanceSalariale.objects.create(
            employe_content_type_id=self._user_content_type_id(),
            employe_object_id=str(self.user.pk),
            mois=10,
            annee=2026,
            date_debut=date(2026, 10, 1),
            date_fin=date(2026, 10, 31),
            date_echeance=date(2026, 10, 5),
            montant_brut=500000,
            montant_net=400000,
            mode="COMPLET",
        )
        stats = StatistiquesPaieService()
        result = stats.cout_employeur("10/2026")
        self.assertFalse(result["cout_employeur_disponible"])
        self.assertIsNone(result["cout_total"])
        self.assertIsNone(result["total_charges_patronales"])

    def _user_content_type_id(self):
        from django.contrib.contenttypes.models import ContentType

        return ContentType.objects.get_for_model(User).pk
