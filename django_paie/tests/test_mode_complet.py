import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.test import Client, TestCase, override_settings

from ..complet.export import ExportExcel, ExportPDF
from ..complet.modeles import BulletinPaie, LignePaie
from ..models import EcheanceSalariale, PaiementSalarial, ReglePaie, VariablePaieMensuelle
from ..services import ModeCompletService


class FauxContrat:
    salaire_base = Decimal("450000")


class FauxRH:
    def get_employe(self, matricule):
        return matricule

    def get_contrat_actif(self, matricule):
        return FauxContrat()

    def get_absences_mois(self, matricule, annee, mois):
        return 0

    def get_heures_mois(self, matricule, annee, mois):
        return Decimal("150")

    def get_variables_mois(self, matricule, annee, mois):
        return {
            "primes": 30000,
            "indemnites": 10000,
            "heures_supplementaires": 10,
            "taux_majoration_heures": "1.25",
            "avantages_nature": 5000,
            "prets_avances": 15000,
            "retenues_personnalisees": 5000,
            "rappels": 2000,
            "conges_payes": 3000,
            "regularisations": -1000,
            "jours_absence": 1,
            "autres": [],
        }


class PetitContrat:
    salaire_base = Decimal("100000")


class FauxRHSansVariables:
    def get_employe(self, matricule):
        return matricule

    def get_contrat_actif(self, matricule):
        return PetitContrat()

    def get_absences_mois(self, matricule, annee, mois):
        return 0

    def get_heures_mois(self, matricule, annee, mois):
        return Decimal("151.67")

    def get_variables_mois(self, matricule, annee, mois):
        return {}


@override_settings(DJANGO_PAIE={"MODE": "COMPLET"})
class ModeCompletTest(TestCase):
    def setUp(self):
        self.employe = User.objects.create_user(username="complet")

    def test_variables_mensuelles_sont_calculees(self):
        bulletin, echeance = ModeCompletService().calculer_bulletin(
            self.employe, "07/2026", rh_stockage=FauxRH()
        )
        codes = {ligne.rubrique_code for ligne in bulletin.lignes}
        self.assertTrue(
            {
                "BASE", "PRIME", "INDEMNITE", "HSUP", "AVANTAGE", "ABSENCE",
                "PRET_AVANCE", "RETENUE", "RAPPEL", "CONGE",
                "REGULARISATION", "CNSS", "AMO", "ITS",
            }.issubset(codes)
        )
        self.assertGreater(bulletin.total_gains(), Decimal("450000"))
        self.assertEqual(echeance.mode, "COMPLET")

    def test_base_cnss_amo_inclut_salaire_base(self):
        bulletin, _ = ModeCompletService().calculer_bulletin(
            self.employe, "07/2026", rh_stockage=FauxRHSansVariables()
        )
        lignes = {ligne.rubrique_code: ligne for ligne in bulletin.lignes}
        self.assertEqual(lignes["CNSS"].base, Decimal("100000"))
        self.assertEqual(lignes["CNSS"].montant, Decimal("-3600"))
        self.assertEqual(lignes["AMO"].base, Decimal("100000"))
        self.assertEqual(lignes["AMO"].montant, Decimal("-5000"))

    def test_regles_obligatoires_manquantes_refusent_calcul(self):
        ReglePaie.objects.filter(organisme="ITS").delete()
        with self.assertRaisesRegex(Exception, "Règles manquantes"):
            ModeCompletService().calculer_bulletin(
                self.employe, "07/2026", rh_stockage=FauxRHSansVariables()
            )

    def test_bulletin_paye_ne_peut_pas_etre_recalcule(self):
        _, echeance = ModeCompletService().calculer_bulletin(
            self.employe, "07/2026", rh_stockage=FauxRHSansVariables()
        )
        PaiementSalarial.objects.create(
            echeance=echeance,
            montant=echeance.montant_net,
            date_paiement=date(2026, 7, 31),
            mois_concerne=7,
            annee_concerne=2026,
        )
        with self.assertRaisesRegex(ValueError, "paiement"):
            ModeCompletService().calculer_bulletin(
                self.employe, "07/2026", rh_stockage=FauxRHSansVariables()
            )

    def test_variable_django_est_lue_par_adaptateur_defaut(self):
        ct = ContentType.objects.get_for_model(self.employe)
        variable = VariablePaieMensuelle.objects.create(
            employe_content_type=ct,
            employe_object_id=str(self.employe.pk),
            mois=7,
            annee=2026,
            primes=25000,
        )
        self.assertEqual(variable.to_moteur_dict()["primes"], 25000)

    def test_regle_entreprise_prioritaire_et_datee(self):
        ReglePaie.objects.create(
            organisme="CNSS",
            version=10,
            date_debut=date(2026, 1, 1),
            entreprise_id="ENT-A",
            taux_salarial=Decimal("0.01"),
            taux_patronal=Decimal("0.02"),
            plafond=Decimal("100000"),
        )
        regle = ReglePaie.pour_date("CNSS", date(2026, 7, 1), "ENT-A")
        self.assertEqual(regle.version, 10)
        nationale = ReglePaie.pour_date("CNSS", date(2026, 7, 1), "ENT-B")
        self.assertEqual(nationale.entreprise_id, "")


class ExportsTest(TestCase):
    def setUp(self):
        self.bulletin = BulletinPaie(
            employe_id="E-1",
            periode="07/2026",
            date_edition=date(2026, 7, 31),
            lignes=[
                LignePaie("BASE", Decimal("100000"), Decimal("1"), Decimal("100000")),
                LignePaie("CNSS", Decimal("100000"), Decimal("0.036"), Decimal("-3600")),
            ],
        )

    def test_exports_pdf_et_excel(self):
        with tempfile.TemporaryDirectory() as dossier:
            pdf = Path(dossier) / "bulletin.pdf"
            xlsx = Path(dossier) / "bulletins.xlsx"
            ExportPDF(self.bulletin).generer(str(pdf))
            ExportExcel([self.bulletin]).generer(str(xlsx))
            self.assertTrue(pdf.read_bytes().startswith(b"%PDF"))
            self.assertTrue(xlsx.read_bytes().startswith(b"PK"))


class CSRFSecurityTest(TestCase):
    def test_post_session_sans_csrf_est_refuse(self):
        user = User.objects.create_superuser("admin", "a@example.test", "secret")
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)
        response = client.post(
            "/api/echeances/",
            data="{}",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
