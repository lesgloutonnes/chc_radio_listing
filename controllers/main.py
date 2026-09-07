# -*- coding: utf-8 -*-
import json
import logging
import re

from odoo import http
from odoo.exceptions import AccessError, ValidationError
from odoo.http import request, Response
from odoo.tools import file_open

_logger = logging.getLogger(__name__)

MATERIELS = ["RX & Med Nuc", "Autres disciplines", "Imprimantes"]
SITES = ["AYW", "GRA", "HER", "HEU", "MLE", "POLY", "WAR", "S98"]
AET_SITE_PREFIXES = [
    ("ETIHIMA", "HER"),
    ("ETINIMA", "MLE"),
    ("ETIWIMA", "WAR"),
    ("ETIYIMA", "HEU"),
]
GROUP_USER = "chc_radio_listing.group_radio_listing_user"
GROUP_MANAGER = "chc_radio_listing.group_radio_listing_manager"
VALID_STATUTS = {
    "en_service",
    "en_panne",
    "en_maintenance",
    "hors_service",
    "en_attente",
}
RELAXED_STATUTS = {"en_attente", "hors_service"}


def _json_response(data, status=200):
    return Response(
        json.dumps(data, ensure_ascii=False, default=str),
        status=status,
        content_type="application/json; charset=utf-8",
    )


def _read_json_body():
    raw = request.httprequest.get_data(as_text=True)
    if not raw:
        return {}
    return json.loads(raw)


class RadioListingController(http.Controller):

    def _equipment_model(self):
        return request.env["chc_radio_listing.equipment"]

    def _category_model(self):
        return request.env["chc_radio_listing.category"]

    def _deny_unless(self, group_xmlid):
        if not request.env.user.has_group(group_xmlid):
            return _json_response({"error": "Droits insuffisants pour cette action."}, 403)
        return None

    def _listings(self):
        return list(MATERIELS)

    def _category_for_materiel(self, name):
        if name not in MATERIELS:
            name = "RX & Med Nuc"
        Category = self._category_model()
        cat = Category.search([("name", "=", name)], limit=1)
        if not cat:
            cat = Category.create({"name": name})
        return cat

    def _normalize_materiel(self, body):
        materiel = (
            body.get("modalite")
            or body.get("materiel")
            or body.get("equipement")
            or body.get("listing")
            or "RX & Med Nuc"
        )
        if materiel not in MATERIELS:
            materiel = "RX & Med Nuc"
        return materiel

    def _guess_site_from_row(self, body):
        site = (body.get("site") or "").strip().upper()
        if site in SITES:
            return site
        aet = (body.get("aet") or "").upper()
        for prefix, mapped in AET_SITE_PREFIXES:
            if aet.startswith(prefix):
                return mapped
        hay = " ".join(
            str(body.get(k) or "") for k in ("salle", "aet", "service")
        ).upper()
        if "HRM" in hay:
            return "HER"
        if "SEH" in hay:
            return "HEU"
        for s in SITES:
            if s in hay:
                return s
        return ""

    def _normalize_import_row(self, row, materiel=None):
        if materiel and not row.get("modalite"):
            row["modalite"] = materiel
        if not row.get("site"):
            row["site"] = self._guess_site_from_row(row) or "MLE"
        if not row.get("salle"):
            row["salle"] = row.get("aet") or row.get("numeroInventaire") or "—"
        inv = row.get("numeroInventaire")
        if isinstance(inv, (int, float)) and not isinstance(inv, bool):
            row["numeroInventaire"] = str(int(inv)).zfill(6)
        return row

    def _duplicate_msg(self, field_label, value, dup_rec):
        site = dup_rec.site or "—"
        aet = dup_rec.aet or "—"
        return (
            f"Doublon {field_label} : « {value} » est déjà utilisé par un autre équipement "
            f"(site {site}, AET {aet})."
        )

    def _check_unique_fields(self, body, exclude_id=None, batch_rows=None):
        statut = body.get("statut") or "en_service"
        if statut in RELAXED_STATUTS:
            return None

        Equipment = self._equipment_model()
        domain = [("active", "=", True), ("statut", "not in", list(RELAXED_STATUTS))]
        if exclude_id:
            domain.append(("id", "!=", int(exclude_id)))

        aet = (body.get("aet") or "").strip().upper()
        if aet:
            dup = Equipment.search(domain + [("aet", "=ilike", aet)], limit=1)
            if dup:
                return self._duplicate_msg("AET", aet, dup)

        ip = (body.get("ip") or "").strip()
        if ip:
            dup = Equipment.search(domain + [("ip", "=", ip)], limit=1)
            if dup:
                return self._duplicate_msg("IP", ip, dup)

        mac = Equipment.normalize_mac(body.get("mac") or "")
        if mac:
            for candidate in Equipment.search(domain + [("mac", "!=", False)]):
                if Equipment.normalize_mac(candidate.mac) == mac:
                    return self._duplicate_msg("MAC", mac, candidate)

        if batch_rows:
            for field, label in (("aet", "AET"), ("ip", "IP"), ("mac", "MAC")):
                if field == "mac":
                    val = Equipment.normalize_mac(body.get("mac") or "")
                elif field == "aet":
                    val = (body.get("aet") or "").strip().upper()
                else:
                    val = (body.get(field) or "").strip()
                if not val:
                    continue
                count = sum(
                    1 for row in batch_rows
                    if (
                        Equipment.normalize_mac(row.get("mac") or "")
                        if field == "mac"
                        else (row.get("aet") or "").strip().upper()
                        if field == "aet"
                        else (row.get(field) or "").strip()
                    ) == val
                )
                if count > 1:
                    return f"Doublon {label} dans le fichier importé : « {val} »."
        return None

    def _validate_item_body(self, body, exclude_id=None, batch_rows=None):
        statut = body.get("statut") or "en_service"
        pending = statut == "en_attente"

        if not pending:
            if not body.get("site"):
                return "Le site est obligatoire."
            if not (body.get("aet") or "").strip():
                return "L'AET est obligatoire."
            ip = (body.get("ip") or "").strip()
            if not ip:
                return "L'IP est obligatoire."
            mac_raw = body.get("mac") or ""
            if not str(mac_raw).strip():
                return "La MAC est obligatoire."

        site = (body.get("site") or "").strip().upper()
        valid_sites = {
            "AYW", "GRA", "HER", "HEU", "MLE", "POLY", "WAR", "S98",
        }
        if site and site not in valid_sites:
            return "Le site est invalide."

        ip = (body.get("ip") or "").strip()
        if ip:
            parts = ip.split(".")
            if len(parts) != 4 or not all(
                p.isdigit() and 0 <= int(p) <= 255 for p in parts
            ):
                return "Format IP invalide."

        mac_raw = body.get("mac") or ""
        if str(mac_raw).strip():
            hex_str = re.sub(r"[^0-9A-Fa-f]", "", str(mac_raw))
            if len(hex_str) != 12:
                return "Format MAC invalide (12 caractères hexadécimaux)."

        if statut in RELAXED_STATUTS:
            return None
        return self._check_unique_fields(
            body, exclude_id=exclude_id, batch_rows=batch_rows
        )

    def _equipment_to_json(self, rec):
        return {
            "id": str(rec.id),
            "site": rec.site or "",
            "aet": rec.aet or "",
            "assocDicom": rec.assoc_dicom or "",
            "ip": rec.ip or "",
            "mac": rec.mac or "",
            "type": rec.equip_type or "",
            "marque": rec.marque or "",
            "modele": rec.modele or "",
            "numeroSerie": rec.numero_serie or "",
            "numeroInventaire": rec.numero_inventaire or "",
            "service": rec.service or "",
            "salle": rec.salle or "",
            "modalite": rec.modalite or "",
            "responsable": rec.responsable or "",
            "reseau": rec.reseau or "",
            "os": self._equipment_model().normalize_os(rec.os) if rec.os else "",
            "statut": rec.statut or "en_service",
            "createdAt": rec.create_date.isoformat() if rec.create_date else "",
            "updatedAt": rec.write_date.isoformat() if rec.write_date else "",
            "createdBy": rec.create_uid.login if rec.create_uid else "",
        }

    def _vals_from_json(self, body):
        materiel = self._normalize_materiel(body)
        cat = self._category_for_materiel(materiel)
        reseau = body.get("reseau") or False
        os_val = self._equipment_model().normalize_os(body.get("os") or False)
        vals = {
            "category_id": cat.id,
            "site": body.get("site"),
            "aet": (body.get("aet") or "").strip().upper(),
            "assoc_dicom": body.get("assocDicom", ""),
            "ip": (body.get("ip") or "").strip(),
            "mac": self._equipment_model().normalize_mac(body.get("mac") or ""),
            "equip_type": body.get("type", ""),
            "marque": body.get("marque", ""),
            "modele": body.get("modele", ""),
            "numero_serie": body.get("numeroSerie", ""),
            "numero_inventaire": body.get("numeroInventaire", ""),
            "service": body.get("service", ""),
            "salle": body.get("salle", ""),
            "modalite": materiel,
            "responsable": body.get("responsable", ""),
            "reseau": reseau if reseau else False,
            "os": os_val if os_val else False,
        }
        statut = body.get("statut")
        if statut in VALID_STATUTS:
            vals["statut"] = statut
        return vals

    def _safe_write(self, callback):
        try:
            return callback()
        except AccessError:
            return _json_response({"error": "Droits insuffisants pour cette action."}, 403)
        except ValidationError as exc:
            return _json_response({"error": str(exc)}, 400)

    @http.route("/chc_radio_listing/app", type="http", auth="user")
    def listing_app(self, **kw):
        denied = self._deny_unless(GROUP_USER)
        if denied:
            return denied
        with file_open("chc_radio_listing/static/src/html/index.html", "r") as f:
            html = f.read()
        response = Response(html, content_type="text/html; charset=utf-8")
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        return response

    @http.route(
        "/chc_radio_listing/api/data",
        type="http",
        auth="user",
        methods=["GET"],
        csrf=False,
    )
    def api_data(self, **kw):
        denied = self._deny_unless(GROUP_USER)
        if denied:
            return denied
        recs = self._equipment_model().search([("active", "=", True)])
        write_dates = recs.mapped("write_date")
        last = max(write_dates) if write_dates else False
        return _json_response(
            {
                "listings": self._listings(),
                "items": [self._equipment_to_json(r) for r in recs],
                "lastModified": last.isoformat() if last else None,
                "version": 1,
                "canWrite": request.env.user.has_group(GROUP_MANAGER),
            }
        )

    @http.route(
        "/chc_radio_listing/api/items",
        type="http",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def api_create_item(self, **kw):
        denied = self._deny_unless(GROUP_MANAGER)
        if denied:
            return denied
        body = _read_json_body()
        err = self._validate_item_body(body)
        if err:
            return _json_response({"error": err}, 400)

        def _create():
            vals = self._vals_from_json(body)
            rec = self._equipment_model().create(vals)
            return _json_response(self._equipment_to_json(rec), 201)

        return self._safe_write(_create)

    @http.route(
        "/chc_radio_listing/api/items/<int:item_id>",
        type="http",
        auth="user",
        methods=["PUT"],
        csrf=False,
    )
    def api_update_item(self, item_id, **kw):
        denied = self._deny_unless(GROUP_MANAGER)
        if denied:
            return denied
        rec = self._equipment_model().browse(item_id)
        if not rec.exists() or not rec.active:
            return _json_response({"error": "Équipement introuvable"}, 404)
        body = _read_json_body()
        err = self._validate_item_body(body, exclude_id=item_id)
        if err:
            return _json_response({"error": err}, 400)

        def _update():
            vals = self._vals_from_json(body)
            rec.write(vals)
            return _json_response(self._equipment_to_json(rec))

        return self._safe_write(_update)

    @http.route(
        "/chc_radio_listing/api/items/<int:item_id>",
        type="http",
        auth="user",
        methods=["DELETE"],
        csrf=False,
    )
    def api_delete_item(self, item_id, **kw):
        denied = self._deny_unless(GROUP_MANAGER)
        if denied:
            return denied
        rec = self._equipment_model().browse(item_id)
        if not rec.exists() or not rec.active:
            return _json_response({"error": "Équipement introuvable"}, 404)

        def _archive():
            rec.write({"active": False})
            return _json_response({"deleted": 1})

        return self._safe_write(_archive)

    @http.route(
        "/chc_radio_listing/api/import",
        type="http",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def api_import(self, **kw):
        denied = self._deny_unless(GROUP_MANAGER)
        if denied:
            return denied
        body = _read_json_body()
        items = body.get("items", [])
        materiel = (
            body.get("materiel")
            or body.get("equipement")
            or body.get("listing")
            or body.get("modalite")
        )
        replace = body.get("replace", False)
        Equipment = self._equipment_model()

        normalized = []
        for row in items:
            self._normalize_import_row(row, materiel)
            normalized.append(row)

        def _import():
            if replace and materiel:
                if materiel not in MATERIELS:
                    materiel_norm = "RX & Med Nuc"
                else:
                    materiel_norm = materiel
                Equipment.search(
                    [("modalite", "=", materiel_norm), ("active", "=", True)]
                ).write({"active": False})
            elif replace:
                Equipment.search([("active", "=", True)]).write({"active": False})

            for row in normalized:
                vals = self._vals_from_json(row)
                Equipment.with_context(chc_skip_unique_check=True).create(vals)

            total = Equipment.search_count([("active", "=", True)])
            return _json_response(
                {"imported": len(normalized), "total": total}
            )

        return self._safe_write(_import)

    @http.route(
        "/chc_radio_listing/api/purge",
        type="http",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def api_purge(self, **kw):
        denied = self._deny_unless(GROUP_MANAGER)
        if denied:
            return denied
        Equipment = self._equipment_model()

        def _purge():
            recs = Equipment.search([("active", "=", True)])
            count = len(recs)
            recs.unlink()
            return _json_response({"purged": count, "total": 0})

        return self._safe_write(_purge)
