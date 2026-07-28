from datetime import date
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth.models import User
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
        echeance = self.service.creer_echeance(self.employe, "07/2026", 50000)
        self.service.enregistrer_paiement(echeance.id, 20000)
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
