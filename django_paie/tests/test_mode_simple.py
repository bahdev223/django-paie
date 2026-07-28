import json
from datetime import date
from decimal import Decimal
from django.test import TestCase
from django.test import override_settings
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.contrib.contenttypes.models import ContentType
from ..models import EcheanceSalariale, PaiementSalarial, PeriodePaie
from ..services import ModeSimpleService
from ..utils import generer_periodes_annee, periode_en_cours, est_periode_valide, extraire_mois_annee


class ModeSimpleServiceTest(TestCase):
    def setUp(self):
        self.employe = User.objects.create_user(
            username="moussa", password="test123"
        )
        self.service = ModeSimpleService()

    def test_creer_echeance(self):
        echeance = self.service.creer_echeance(
            employe=self.employe,
            periode="07/2026",
            montant_brut=50000,
            montant_net=50000,
        )
        self.assertEqual(echeance.montant_brut, 50000)
        self.assertEqual(echeance.montant_net, 50000)
        self.assertEqual(echeance.mois, 7)
        self.assertEqual(echeance.annee, 2026)
        self.assertEqual(echeance.periode, "07/2026")
        self.assertEqual(echeance.statut, "A_PAYER")
        self.assertEqual(echeance.mode, "SIMPLE")

    def test_echeance_unique_par_periode(self):
        self.service.creer_echeance(self.employe, "07/2026", 50000)
        echeance2 = self.service.creer_echeance(self.employe, "07/2026", 60000)
        self.assertEqual(echeance2.montant_brut, 60000)
        count = EcheanceSalariale.objects.filter(mois=7, annee=2026).count()
        self.assertEqual(count, 1)

    def test_enregistrer_paiement_total(self):
        echeance = self.service.creer_echeance(self.employe, "07/2026", 50000)
        paiement = self.service.enregistrer_paiement(
            echeance_id=echeance.id, montant=50000
        )
        echeance.refresh_from_db()
        self.assertEqual(echeance.montant_paye, 50000)
        self.assertEqual(echeance.statut, "PAYE")
        self.assertEqual(paiement.type_paiement, "PAIEMENT")

    def test_enregistrer_paiement_partiel(self):
        echeance = self.service.creer_echeance(
            self.employe, "09/2026", 50000, date_echeance=date(2026, 9, 30),
        )
        self.service.enregistrer_paiement(
            echeance.id, 20000, date_paiement=date(2026, 9, 15),
        )
        echeance.refresh_from_db()
        self.assertEqual(echeance.montant_paye, 20000)
        self.assertEqual(echeance.statut, "PARTIELLEMENT_PAYE")

    def test_mois_impayes(self):
        self.service.creer_echeance(self.employe, "06/2026", 50000)
        self.service.creer_echeance(self.employe, "07/2026", 50000)
        echeance_aout = self.service.creer_echeance(self.employe, "08/2026", 50000)
        self.service.enregistrer_paiement(echeance_aout.id, 50000)

        impayes = self.service.mois_impayes(self.employe, annee=2026)
        self.assertEqual(len(impayes), 2)

    def test_reste_a_payer(self):
        echeance = self.service.creer_echeance(self.employe, "07/2026", 50000)
        self.assertEqual(echeance.reste_a_payer, 50000)
        self.service.enregistrer_paiement(echeance.id, 30000)
        echeance.refresh_from_db()
        self.assertEqual(echeance.reste_a_payer, 20000)

    def test_dashboard(self):
        e = self.service.creer_echeance(self.employe, "07/2026", 50000)
        self.service.enregistrer_paiement(e.id, 50000)
        dash = self.service.dashboard(annee=2026)
        self.assertEqual(dash["total_echeances"], 1)
        self.assertEqual(dash["paye"], 1)

    def test_payer_plusieurs_mois(self):
        self.service.creer_echeance(self.employe, "07/2026", 50000)
        self.service.creer_echeance(self.employe, "08/2026", 50000)
        paiements = self.service.payer_plusieurs_mois(
            self.employe, 80000, "07/2026", "08/2026"
        )
        self.assertEqual(len(paiements), 2)
        self.assertEqual(paiements[0].montant, 50000)
        self.assertEqual(paiements[1].montant, 30000)

    def test_montant_zero_rejete(self):
        echeance = self.service.creer_echeance(self.employe, "07/2026", 50000)
        with self.assertRaises(ValueError):
            self.service.enregistrer_paiement(echeance.id, 0)

    def test_trop_percu(self):
        echeance = self.service.creer_echeance(self.employe, "07/2026", 50000)
        self.service.enregistrer_paiement(echeance.id, 60000)
        echeance.refresh_from_db()
        self.assertEqual(echeance.statut, "TROPPERCU")
        self.assertEqual(echeance.trop_percu, 10000)

    def test_avance_conserve_salaire_complet(self):
        source = self.service.creer_echeance(self.employe, "07/2026", montant_brut=50000, montant_net=48000)
        paiement = self.service.enregistrer_paiement(
            echeance_id=source.id, montant=20000, type_paiement="AVANCE",
        )
        echeance_cible = paiement.echeance
        self.assertEqual(echeance_cible.mois, 8)
        self.assertEqual(echeance_cible.annee, 2026)
        self.assertEqual(echeance_cible.montant_brut, 50000)
        self.assertEqual(echeance_cible.montant_net, 48000)
        self.assertEqual(echeance_cible.montant_paye, 20000)
        self.assertEqual(echeance_cible.statut, "PAYE_EN_AVANCE")

    def test_annulation_paiement(self):
        echeance = self.service.creer_echeance(self.employe, "07/2026", 50000)
        paiement = self.service.enregistrer_paiement(echeance.id, 50000)
        echeance.refresh_from_db()
        self.assertEqual(echeance.statut, "PAYE")
        paiement.annuler()
        paiement.refresh_from_db()
        self.assertEqual(paiement.statut, "ANNULE")
        echeance.refresh_from_db()
        self.assertEqual(echeance.montant_paye, 0)
        self.assertIn(echeance.statut, ["A_PAYER", "EN_RETARD"])

    def test_arriere_detecte_automatiquement(self):
        echeance = self.service.creer_echeance(self.employe, "06/2026", 50000)
        echeance.date_fin = date(2026, 6, 30)
        echeance.save()
        paiement = self.service.enregistrer_paiement(
            echeance.id, 50000, date_paiement=date(2026, 7, 15),
        )
        self.assertEqual(paiement.type_paiement, "ARRIERE")

    def test_creer_echeance_periode_close_refuse(self):
        periode = PeriodePaie.from_libelle("06/2026")
        periode.est_cloturee = True
        periode.save()
        with self.assertRaises(ValueError):
            self.service.creer_echeance(self.employe, "06/2026", 50000)

    def test_creer_echeance_deja_payee_refuse(self):
        echeance = self.service.creer_echeance(self.employe, "07/2026", 50000)
        self.service.enregistrer_paiement(echeance.id, 50000)
        with self.assertRaises(ValueError):
            self.service.creer_echeance(self.employe, "07/2026", 60000)

    def test_paiement_periode_close_refuse(self):
        echeance = self.service.creer_echeance(self.employe, "07/2026", 50000)
        periode = PeriodePaie.from_libelle("07/2026")
        periode.est_cloturee = True
        periode.save(update_fields=["est_cloturee"])
        with self.assertRaises(ValueError):
            self.service.enregistrer_paiement(echeance.id, 10000)

    def test_avance_sans_salaire_reference_refusee(self):
        with self.assertRaisesRegex(ValueError, "salaire de référence"):
            self.service.enregistrer_paiement(
                employe=self.employe,
                periode="07/2026",
                montant=20000,
                type_paiement="AVANCE",
            )

    def test_avance_accepte_montant_mensuel_explicite(self):
        paiement = self.service.enregistrer_paiement(
            employe=self.employe,
            periode="07/2026",
            montant=20000,
            montant_mensuel=50000,
            type_paiement="AVANCE",
        )
        self.assertEqual(paiement.echeance.montant_net, 50000)
        self.assertEqual(paiement.echeance.reste_a_payer, 30000)

    def test_isolation_multi_entreprise(self):
        service_b = ModeSimpleService(entreprise_id="ENT-B")
        e_a = self.service.creer_echeance(self.employe, "07/2026", 50000)
        e_b = service_b.creer_echeance(self.employe, "07/2026", 70000)
        self.assertNotEqual(e_a.pk, e_b.pk)
        self.assertEqual(e_a.montant_brut, 50000)
        self.assertEqual(e_b.montant_brut, 70000)
        dash_a = self.service.dashboard(annee=2026)
        dash_b = service_b.dashboard(annee=2026)
        self.assertEqual(dash_a["total_echeances"], 1)
        self.assertEqual(dash_b["total_echeances"], 1)


class UtilsTest(TestCase):
    def test_generer_periodes(self):
        periodes = generer_periodes_annee(2026)
        self.assertEqual(len(periodes), 12)
        self.assertEqual(periodes[0], "01/2026")
        self.assertEqual(periodes[11], "12/2026")

    def test_periode_en_cours(self):
        p = periode_en_cours()
        self.assertTrue(est_periode_valide(p))

    def test_est_periode_valide(self):
        self.assertTrue(est_periode_valide("07/2026"))
        self.assertFalse(est_periode_valide("13/2026"))
        self.assertFalse(est_periode_valide("07/99"))
        self.assertFalse(est_periode_valide(""))

    def test_extraire_mois_annee(self):
        m, a = extraire_mois_annee("07/2026")
        self.assertEqual(m, 7)
        self.assertEqual(a, 2026)
        with self.assertRaises(ValueError):
            extraire_mois_annee("")


class PeriodePaieModelTest(TestCase):
    def test_from_libelle(self):
        p = PeriodePaie.from_libelle("07/2026")
        self.assertEqual(p.mois, 7)
        self.assertEqual(p.annee, 2026)
        self.assertEqual(p.date_debut.month, 7)
        self.assertEqual(p.date_debut.day, 1)

    def test_date_fin_correcte(self):
        p = PeriodePaie.from_libelle("01/2026")
        self.assertEqual(p.date_fin.day, 31)
        p = PeriodePaie.from_libelle("02/2026")
        self.assertEqual(p.date_fin.day, 28)
        p = PeriodePaie.from_libelle("07/2026")
        self.assertEqual(p.date_fin.day, 31)

    def test_from_libelle_reutilise(self):
        p1 = PeriodePaie.from_libelle("07/2026")
        p2 = PeriodePaie.from_libelle("07/2026")
        self.assertEqual(p1.pk, p2.pk)


class APITest(TestCase):
    def setUp(self):
        self.employe = User.objects.create_user(
            username="api_test", password="test123", is_staff=True,
        )

    def _api_request(self, method, path, data=None):
        from django.test import RequestFactory
        factory = RequestFactory()
        if method == "GET":
            request = factory.get(path)
        else:
            request = factory.post(path, json.dumps(data), content_type="application/json")
        self.employe.is_superuser = True
        self.employe.save(update_fields=["is_superuser"])
        request.user = self.employe
        return request

    def test_api_echeance_list(self):
        from ..api.views import EcheanceListAPI
        request = self._api_request("GET", "/api/echeances/")
        response = EcheanceListAPI.as_view()(request)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn("data", data)
        self.assertIn("count", data)

    def test_api_paiement_create(self):
        from ..api.views import PaiementListAPI
        service = ModeSimpleService()
        echeance = service.creer_echeance(self.employe, "07/2026", 50000)
        request = self._api_request("POST", "/api/paiements/",
                                    {"echeance_id": echeance.id, "montant": 50000})
        response = PaiementListAPI.as_view()(request)
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.content)
        self.assertEqual(data["data"]["montant"], 50000)

    def test_api_refuse_utilisateur_sans_permission(self):
        from ..api.views import EcheanceListAPI
        request = self._api_request("GET", "/api/echeances/")
        self.employe.is_superuser = False
        self.employe.save(update_fields=["is_superuser"])
        with self.assertRaises(PermissionDenied):
            EcheanceListAPI.as_view()(request)

    @override_settings(
        DJANGO_PAIE={"MODE": "SIMPLE", "MODE_PAR_ENTREPRISE": True}
    )
    def test_api_refuse_utilisateur_sans_entreprise(self):
        from ..api.views import EcheanceListAPI
        request = self._api_request("GET", "/api/echeances/")
        with self.assertRaises(PermissionDenied):
            EcheanceListAPI.as_view()(request)


class StatistiquesPaieServiceTest(TestCase):
    def setUp(self):
        self.employe = User.objects.create_user(username="fatou", password="test123")
        self.service = ModeSimpleService()

    def test_arrieres_ignore_partiel_avant_date(self):
        echeance = self.service.creer_echeance(self.employe, "09/2026", 50000)
        echeance.date_echeance = date(2026, 9, 30)
        echeance.save()
        self.service.enregistrer_paiement(echeance.id, 20000)
        from ..services import StatistiquesPaieService
        stats = StatistiquesPaieService()
        arrieres = stats.arrieres()
        self.assertEqual(arrieres["nombre_echeances"], 0)

    def test_resume_annuel_reste_global_non_negatif(self):
        echeance = self.service.creer_echeance(self.employe, "07/2026", 50000)
        self.service.enregistrer_paiement(echeance.id, 60000)
        from ..services import StatistiquesPaieService
        stats = StatistiquesPaieService()
        resume = stats.resume_annuel(annee=2026)
        self.assertEqual(resume["reste_global"], 0)
        self.assertEqual(resume["total_montant_du"], 50000)
        self.assertEqual(resume["total_montant_paye"], 60000)
