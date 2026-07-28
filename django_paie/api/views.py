import json
from datetime import date
from decimal import Decimal
from django.http import JsonResponse
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from ..models import EcheanceSalariale, PaiementSalarial, PeriodePaie, RubriquePaie
from ..models.bulletin import BulletinPaie, LigneBulletin, CotisationBulletin, ValidationPaie
from ..services import ModeSimpleService, ModeCompletService, StatistiquesPaieService
from ..conf import paie_settings
from .docs_content import API_DOCS


class APIView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "django_paie.view_echeancesalariale"
    raise_exception = True

    def dispatch(self, request, *args, **kwargs):
        if paie_settings.MODE_PAR_ENTREPRISE:
            entreprise_id = getattr(request.user, "entreprise_id", "")
            if not entreprise_id:
                raise PermissionDenied("Aucune entreprise associée à cet utilisateur.")
        return super().dispatch(request, *args, **kwargs)

    def get_entreprise_id(self):
        if not paie_settings.MODE_PAR_ENTREPRISE:
            return ""
        entreprise_id = getattr(self.request.user, "entreprise_id", "")
        if not entreprise_id:
            raise PermissionDenied("Aucune entreprise associée à cet utilisateur.")
        return str(entreprise_id)


def _json_error(msg, status=400):
    return JsonResponse({"error": msg}, status=status)


def _parse_json(request):
    try:
        return json.loads(request.body)
    except (ValueError, AttributeError):
        return None


def _decimal(val):
    try:
        return int(Decimal(str(val)))
    except (Exception, ArithmeticError):
        return 0


def _parse_date(val):
    if not val:
        return None
    if isinstance(val, date):
        return val
    try:
        return date.fromisoformat(str(val))
    except (ValueError, TypeError):
        return None


def _verifier_employe_entreprise(request, employe):
    if not paie_settings.MODE_PAR_ENTREPRISE:
        return
    entreprise_id = getattr(request.user, "entreprise_id", "")
    champ = paie_settings.EMPLOYE_ENTREPRISE_FIELD
    valeur = getattr(employe, champ, None)
    if valeur is None or str(valeur) != str(entreprise_id):
        raise PermissionDenied(
            "Employé introuvable ou rattaché à une autre entreprise."
        )


def _serialize_echeance(e, include_paiements=False):
    d = {
        "id": e.pk,
        "employe_id": e.employe_object_id,
        "periode": e.periode,
        "mois": e.mois,
        "annee": e.annee,
        "date_debut": e.date_debut.isoformat(),
        "date_fin": e.date_fin.isoformat(),
        "date_echeance": e.date_echeance.isoformat(),
        "montant_brut": int(e.montant_brut),
        "montant_net": int(e.montant_net),
        "montant_paye": int(e.montant_paye),
        "reste_a_payer": int(e.reste_a_payer),
        "trop_percu": int(e.trop_percu),
        "statut": e.statut,
        "statut_display": e.get_statut_display(),
        "mode": e.mode,
        "entreprise_id": e.entreprise_id,
    }
    if include_paiements:
        d["paiements"] = [_serialize_paiement(p) for p in e.paiements.all()]
    return d


def _serialize_paiement(p):
    return {
        "id": p.pk,
        "echeance_id": p.echeance_id,
        "montant": int(p.montant),
        "type_paiement": p.type_paiement,
        "type_display": p.get_type_paiement_display(),
        "statut": p.statut,
        "date_paiement": p.date_paiement.isoformat(),
        "mois_concerne": p.mois_concerne,
        "annee_concerne": p.annee_concerne,
        "reference": p.reference,
        "notes": p.notes,
    }


def _serialize_bulletin(b):
    return {
        "id": b.pk,
        "echeance_id": b.echeance_id,
        "periode": b.echeance.periode,
        "employe_id": b.echeance.employe_object_id,
        "total_gains": int(b.total_gains),
        "total_retenues": int(b.total_retenues),
        "net_a_payer": int(b.net_a_payer),
        "statut": b.statut,
        "date_edition": b.date_edition.isoformat(),
        "lignes": [
            {
                "rubrique": l.rubrique.code,
                "libelle": l.rubrique.libelle,
                "base": int(l.base),
                "taux": float(l.taux),
                "montant": int(l.montant),
                "ordre": l.ordre,
            }
            for l in b.lignes.select_related("rubrique").all()
        ],
        "cotisations": [
            {
                "rubrique": c.rubrique.code,
                "type": c.type_cotisation,
                "base": int(c.base),
                "taux": float(c.taux),
                "montant": int(c.montant),
            }
            for c in b.cotisations.select_related("rubrique").all()
        ],
    }


class EcheanceListAPI(APIView):
    permission_required = "django_paie.view_echeancesalariale"

    def get(self, request):
        entreprise_id = self.get_entreprise_id()
        qs = EcheanceSalariale.objects.all()
        if entreprise_id:
            qs = qs.filter(entreprise_id=entreprise_id)

        statut = request.GET.get("statut")
        if statut:
            qs = qs.filter(statut=statut)
        periode = request.GET.get("periode")
        if periode:
            try:
                m, a = periode.split("/")
                qs = qs.filter(mois=int(m), annee=int(a))
            except (ValueError, AttributeError):
                pass
        employe = request.GET.get("employe_id")
        if employe:
            qs = qs.filter(employe_object_id=employe)

        qs = qs.order_by("-annee", "-mois")
        return JsonResponse(
            {"data": [_serialize_echeance(e) for e in qs], "count": qs.count()}
        )

    def post(self, request):
        if not request.user.has_perm("django_paie.add_echeancesalariale"):
            return _json_error("Permission refusée.", 403)
        data = _parse_json(request)
        if not data:
            return _json_error("Corps JSON requis.")
        employe_id = data.get("employe_id")
        periode = data.get("periode")
        montant_brut = data.get("montant_brut")
        if not all([employe_id, periode, montant_brut]):
            return _json_error("employe_id, periode, montant_brut requis.")

        from django.apps import apps
        model = apps.get_model(paie_settings.EMPLOYE_MODEL)
        try:
            employe = model.objects.get(pk=employe_id)
        except model.DoesNotExist:
            return _json_error(f"Employé {employe_id} introuvable.", 404)
        _verifier_employe_entreprise(request, employe)

        entreprise_id = self.get_entreprise_id()
        service = ModeSimpleService(entreprise_id=entreprise_id)
        try:
            echeance = service.creer_echeance(
                employe=employe,
                periode=periode,
                montant_brut=_decimal(montant_brut),
                montant_net=_decimal(data.get("montant_net", montant_brut)),
                date_echeance=_parse_date(data.get("date_echeance")),
            )
        except ValueError as e:
            return _json_error(str(e))
        return JsonResponse({"data": _serialize_echeance(echeance)}, status=201)


class EcheanceDetailAPI(APIView):
    permission_required = "django_paie.view_echeancesalariale"

    def _verifier_acces(self, echeance):
        if not paie_settings.MODE_PAR_ENTREPRISE:
            return True
        return echeance.entreprise_id == self.get_entreprise_id()

    def get(self, request, pk):
        try:
            e = EcheanceSalariale.objects.prefetch_related("paiements").get(pk=pk)
        except EcheanceSalariale.DoesNotExist:
            return _json_error("Échéance introuvable.", 404)
        if not self._verifier_acces(e):
            return _json_error("Accès refusé.", 403)
        return JsonResponse({"data": _serialize_echeance(e, include_paiements=True)})

    def post(self, request, pk):
        data = _parse_json(request)
        if not data:
            return _json_error("Corps JSON requis.")
        try:
            e = EcheanceSalariale.objects.get(pk=pk)
        except EcheanceSalariale.DoesNotExist:
            return _json_error("Échéance introuvable.", 404)
        if not self._verifier_acces(e):
            return _json_error("Accès refusé.", 403)
        action = data.get("action")
        if action == "cloturer":
            if not request.user.has_perm("django_paie.cloturer_periode"):
                return _json_error("Permission refusée.", 403)
            with transaction.atomic():
                e = EcheanceSalariale.objects.select_for_update().get(pk=e.pk)
                periode_qs = EcheanceSalariale.objects.select_for_update().filter(
                    mois=e.mois, annee=e.annee, entreprise_id=e.entreprise_id
                )
                non_reglees = periode_qs.exclude(
                    statut__in=["PAYE", "PAYE_EN_AVANCE", "ANNULE"]
                )
                if non_reglees.exists():
                    return _json_error(
                        "Impossible de clôturer : toutes les échéances de la période doivent être réglées.",
                        400,
                    )
                periode = PeriodePaie.from_libelle(e.periode, entreprise_id=e.entreprise_id)
                periode.est_cloturee = True
                periode.save(update_fields=["est_cloturee"])
                periode_qs.update(date_cloture=date.today())
                BulletinPaie.objects.filter(
                    echeance__mois=e.mois,
                    echeance__annee=e.annee,
                    echeance__entreprise_id=e.entreprise_id,
                ).update(est_verrouille=True, statut="CLOTURE")
                e.refresh_from_db()
            return JsonResponse({"data": _serialize_echeance(e)})
        return _json_error("Action non supportée.")


class PaiementListAPI(APIView):
    permission_required = "django_paie.view_paiementsalarial"

    def get(self, request):
        entreprise_id = self.get_entreprise_id()
        qs = PaiementSalarial.objects.select_related("echeance").all()
        if entreprise_id:
            qs = qs.filter(echeance__entreprise_id=entreprise_id)
        echeance_id = request.GET.get("echeance_id")
        if echeance_id:
            qs = qs.filter(echeance_id=echeance_id)
        qs = qs.order_by("-date_paiement")
        return JsonResponse(
            {"data": [_serialize_paiement(p) for p in qs], "count": qs.count()}
        )

    def post(self, request):
        if not request.user.has_perm("django_paie.add_paiementsalarial"):
            return _json_error("Permission refusée.", 403)
        data = _parse_json(request)
        if not data:
            return _json_error("Corps JSON requis.")

        entreprise_id = self.get_entreprise_id()
        service = ModeSimpleService(entreprise_id=entreprise_id)
        try:
            paiement = service.enregistrer_paiement(
                echeance_id=data.get("echeance_id"),
                montant=_decimal(data.get("montant", 0)),
                date_paiement=_parse_date(data.get("date_paiement")),
                type_paiement=data.get("type_paiement", "PAIEMENT"),
                notes=data.get("notes", ""),
            )
        except (ValueError, EcheanceSalariale.DoesNotExist) as e:
            return _json_error(str(e))
        return JsonResponse({"data": _serialize_paiement(paiement)}, status=201)


class PaiementAnnulerAPI(APIView):
    permission_required = "django_paie.annuler_paiement"

    def post(self, request, pk):
        try:
            paiement = PaiementSalarial.objects.get(pk=pk)
        except PaiementSalarial.DoesNotExist:
            return _json_error("Paiement introuvable.", 404)
        if paie_settings.MODE_PAR_ENTREPRISE:
            if paiement.echeance.entreprise_id != self.get_entreprise_id():
                return _json_error("Accès refusé.", 403)
        try:
            paiement.annuler()
        except Exception as e:
            return _json_error(str(e))
        paiement.refresh_from_db()
        return JsonResponse({"data": _serialize_paiement(paiement)})


class AvanceAPI(APIView):
    permission_required = "django_paie.add_paiementsalarial"

    def post(self, request):
        data = _parse_json(request)
        if not data:
            return _json_error("Corps JSON requis.")

        employe_id = data.get("employe_id")
        montant = _decimal(data.get("montant", 0))
        periode_source = data.get("periode_source")
        if not all([employe_id, montant, periode_source]):
            return _json_error("employe_id, periode_source, montant requis.")

        from django.apps import apps
        model = apps.get_model(paie_settings.EMPLOYE_MODEL)
        try:
            employe = model.objects.get(pk=employe_id)
        except model.DoesNotExist:
            return _json_error(f"Employé {employe_id} introuvable.", 404)
        _verifier_employe_entreprise(request, employe)

        entreprise_id = self.get_entreprise_id()
        service = ModeSimpleService(entreprise_id=entreprise_id)
        try:
            paiement = service.enregistrer_paiement(
                employe=employe,
                periode=periode_source,
                montant=montant,
                date_paiement=_parse_date(data.get("date_paiement")),
                type_paiement="AVANCE",
                periode_cible=data.get("periode_cible"),
                montant_mensuel=data.get("montant_mensuel"),
                notes=data.get("notes", ""),
            )
        except ValueError as e:
            return _json_error(str(e))
        return JsonResponse({"data": _serialize_paiement(paiement)}, status=201)


class BulletinCalculAPI(APIView):
    permission_required = "django_paie.add_bulletinpaie"

    def post(self, request):
        data = _parse_json(request)
        if not data:
            return _json_error("Corps JSON requis.")

        employe_id = data.get("employe_id")
        periode = data.get("periode")
        if not all([employe_id, periode]):
            return _json_error("employe_id, periode requis.")

        from django.apps import apps
        model = apps.get_model(paie_settings.EMPLOYE_MODEL)
        try:
            employe = model.objects.get(pk=employe_id)
        except model.DoesNotExist:
            return _json_error(f"Employé {employe_id} introuvable.", 404)
        _verifier_employe_entreprise(request, employe)

        entreprise_id = self.get_entreprise_id()
        service = ModeCompletService(entreprise_id=entreprise_id)
        try:
            bulletin_dataclass, echeance = service.calculer_bulletin(employe, periode)
        except Exception as e:
            return _json_error(str(e))
        bulletin_model = BulletinPaie.objects.get(echeance=echeance)
        return JsonResponse({"data": _serialize_bulletin(bulletin_model)}, status=201)


class BulletinListAPI(APIView):
    permission_required = "django_paie.view_bulletinpaie"

    def get(self, request):
        entreprise_id = self.get_entreprise_id()
        qs = BulletinPaie.objects.select_related("echeance").all()
        if entreprise_id:
            qs = qs.filter(echeance__entreprise_id=entreprise_id)
        employe_id = request.GET.get("employe_id")
        if employe_id:
            qs = qs.filter(echeance__employe_object_id=employe_id)
        periode = request.GET.get("periode")
        if periode:
            try:
                m, a = periode.split("/")
                qs = qs.filter(echeance__mois=int(m), echeance__annee=int(a))
            except (ValueError, AttributeError):
                pass
        qs = qs.order_by("-echeance__annee", "-echeance__mois")
        return JsonResponse(
            {"data": [_serialize_bulletin(b) for b in qs], "count": qs.count()}
        )


class MasseSalarialeAPI(APIView):
    permission_required = "django_paie.add_bulletinpaie"

    def post(self, request):
        data = _parse_json(request)
        if not data:
            return _json_error("Corps JSON requis.")
        periode = data.get("periode")
        employes_ids = data.get("employes_ids", [])
        if not periode:
            return _json_error("periode requis.")
        if not employes_ids:
            return _json_error("employes_ids requis (liste).")

        entreprise_id = self.get_entreprise_id()
        service = ModeCompletService(entreprise_id=entreprise_id)
        resultats = service.calculer_masse(employes_ids, periode)
        succes = sum(1 for r in resultats if r["succes"])
        echec = sum(1 for r in resultats if not r["succes"])
        return JsonResponse({
            "periode": periode,
            "total_employes": len(resultats),
            "succes": succes,
            "echec": echec,
            "resultats": resultats,
        })


class StatsResumeAPI(APIView):
    permission_required = "django_paie.view_echeancesalariale"

    def get(self, request):
        entreprise_id = self.get_entreprise_id()
        stats = StatistiquesPaieService(entreprise_id=entreprise_id)
        annee = request.GET.get("annee")
        if annee:
            try:
                annee = int(annee)
            except ValueError:
                annee = None
        periode = request.GET.get("periode")
        if periode:
            return JsonResponse({"data": stats.resume_periode(periode)})
        return JsonResponse({"data": stats.resume_annuel(annee=annee)})


class StatsArrieresAPI(APIView):
    permission_required = "django_paie.view_echeancesalariale"

    def get(self, request):
        entreprise_id = self.get_entreprise_id()
        stats = StatistiquesPaieService(entreprise_id=entreprise_id)
        return JsonResponse({"data": stats.arrieres()})


class StatsAvancesAPI(APIView):
    permission_required = "django_paie.view_echeancesalariale"

    def get(self, request):
        entreprise_id = self.get_entreprise_id()
        stats = StatistiquesPaieService(entreprise_id=entreprise_id)
        return JsonResponse({"data": stats.avances()})


class DashboardAPI(APIView):
    permission_required = "django_paie.view_echeancesalariale"

    def get(self, request):
        entreprise_id = self.get_entreprise_id()
        stats = StatistiquesPaieService(entreprise_id=entreprise_id)
        annee = request.GET.get("annee")
        if annee:
            try:
                annee = int(annee)
            except ValueError:
                annee = None

        mode = paie_settings.get_mode(entreprise_id)
        res = {
            "resume": stats.resume_annuel(annee=annee),
            "evolution": stats.evolution_mensuelle(annee=annee),
            "arrieres": stats.arrieres(),
            "avances": stats.avances(),
            "alertes": stats.alertes(),
            "mode": mode,
        }
        if mode == "COMPLET":
            periode_courante = f"{date.today().month:02d}/{date.today().year}"
            res["masse_salariale"] = stats.masse_salariale(periode_courante)
            res["cout_employeur"] = stats.cout_employeur(periode_courante)
        return JsonResponse({"data": res})


class DocsAPI(APIView):
    permission_required = "django_paie.view_echeancesalariale"

    def get(self, request):
        return JsonResponse({"data": API_DOCS})
