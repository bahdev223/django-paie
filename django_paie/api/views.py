import json
from datetime import date
from decimal import Decimal
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from ..models import EcheanceSalariale, PaiementSalarial, PeriodePaie, RubriquePaie
from ..models.bulletin import BulletinPaie, LigneBulletin, CotisationBulletin, ValidationPaie
from ..services import ModeSimpleService, ModeCompletService, StatistiquesPaieService
from ..conf import paie_settings
from ..utils import extraire_mois_annee


def _get_entreprise_id(request):
    if paie_settings.MODE_PAR_ENTREPRISE:
        return getattr(request.user, "entreprise_id", "")
    return ""


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


@method_decorator(csrf_exempt, name="dispatch")
class EcheanceListAPI(View):
    def get(self, request):
        entreprise_id = _get_entreprise_id(request)
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

        service = ModeSimpleService(entreprise_id=_get_entreprise_id(request))
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


@method_decorator(csrf_exempt, name="dispatch")
class EcheanceDetailAPI(View):
    def get(self, request, pk):
        try:
            e = EcheanceSalariale.objects.prefetch_related("paiements").get(pk=pk)
        except EcheanceSalariale.DoesNotExist:
            return _json_error("Échéance introuvable.", 404)
        return JsonResponse({"data": _serialize_echeance(e, include_paiements=True)})

    def post(self, request, pk):
        data = _parse_json(request)
        if not data:
            return _json_error("Corps JSON requis.")
        action = data.get("action")
        if action == "cloturer":
            try:
                e = EcheanceSalariale.objects.get(pk=pk)
            except EcheanceSalariale.DoesNotExist:
                return _json_error("Échéance introuvable.", 404)
            e.date_cloture = date.today()
            e.statut = "PAYE"
            e.save(update_fields=["date_cloture", "statut"])
            return JsonResponse({"data": _serialize_echeance(e)})
        return _json_error("Action non supportée.")


@method_decorator(csrf_exempt, name="dispatch")
class PaiementListAPI(View):
    def get(self, request):
        entreprise_id = _get_entreprise_id(request)
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
        data = _parse_json(request)
        if not data:
            return _json_error("Corps JSON requis.")

        service = ModeSimpleService(entreprise_id=_get_entreprise_id(request))
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


@method_decorator(csrf_exempt, name="dispatch")
class PaiementAnnulerAPI(View):
    def post(self, request, pk):
        try:
            paiement = PaiementSalarial.objects.get(pk=pk)
        except PaiementSalarial.DoesNotExist:
            return _json_error("Paiement introuvable.", 404)
        try:
            paiement.annuler()
        except Exception as e:
            return _json_error(str(e))
        paiement.refresh_from_db()
        return JsonResponse({"data": _serialize_paiement(paiement)})


@method_decorator(csrf_exempt, name="dispatch")
class AvanceAPI(View):
    def post(self, request):
        data = _parse_json(request)
        if not data:
            return _json_error("Corps JSON requis.")

        employe_id = data.get("employe_id")
        periode_source = data.get("periode_source")
        montant = _decimal(data.get("montant", 0))
        if not all([employe_id, periode_source, montant]):
            return _json_error("employe_id, periode_source, montant requis.")

        from django.apps import apps
        model = apps.get_model(paie_settings.EMPLOYE_MODEL)
        try:
            employe = model.objects.get(pk=employe_id)
        except model.DoesNotExist:
            return _json_error(f"Employé {employe_id} introuvable.", 404)

        service = ModeSimpleService(entreprise_id=_get_entreprise_id(request))
        try:
            paiement = service.enregistrer_paiement(
                employe=employe,
                periode=periode_source,
                montant=montant,
                date_paiement=_parse_date(data.get("date_paiement")),
                type_paiement="AVANCE",
                notes=data.get("notes", ""),
            )
        except ValueError as e:
            return _json_error(str(e))
        return JsonResponse({"data": _serialize_paiement(paiement)}, status=201)


@method_decorator(csrf_exempt, name="dispatch")
class BulletinCalculAPI(View):
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

        service = ModeCompletService(entreprise_id=_get_entreprise_id(request))
        try:
            bulletin_dataclass, echeance = service.calculer_bulletin(employe, periode)
        except Exception as e:
            return _json_error(str(e))
        bulletin_model = BulletinPaie.objects.get(echeance=echeance)
        return JsonResponse({"data": _serialize_bulletin(bulletin_model)}, status=201)


@method_decorator(csrf_exempt, name="dispatch")
class BulletinListAPI(View):
    def get(self, request):
        entreprise_id = _get_entreprise_id(request)
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


@method_decorator(csrf_exempt, name="dispatch")
class MasseSalarialeAPI(View):
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

        service = ModeCompletService(entreprise_id=_get_entreprise_id(request))
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


@method_decorator(csrf_exempt, name="dispatch")
class StatsResumeAPI(View):
    def get(self, request):
        entreprise_id = _get_entreprise_id(request)
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


@method_decorator(csrf_exempt, name="dispatch")
class StatsArrieresAPI(View):
    def get(self, request):
        entreprise_id = _get_entreprise_id(request)
        stats = StatistiquesPaieService(entreprise_id=entreprise_id)
        return JsonResponse({"data": stats.arrieres()})


@method_decorator(csrf_exempt, name="dispatch")
class StatsAvancesAPI(View):
    def get(self, request):
        entreprise_id = _get_entreprise_id(request)
        stats = StatistiquesPaieService(entreprise_id=entreprise_id)
        return JsonResponse({"data": stats.avances()})


@method_decorator(csrf_exempt, name="dispatch")
class DashboardAPI(View):
    def get(self, request):
        entreprise_id = _get_entreprise_id(request)
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
