# -*- coding: utf-8 -*-
import re
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class Equipment(models.Model):
    _name = "chc_radio_listing.equipment"
    _description = "Équipement médical"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "modalite, site, equip_type"
    _rec_name = "designation"

    # ── Identification réseau / DICOM ─────────────────────────────────────────
    site = fields.Selection(
        [
            ("AYW", "AYW"),
            ("GRA", "GRA"),
            ("HER", "HER"),
            ("HEU", "HEU"),
            ("MLE", "MLE"),
            ("POLY", "POLY"),
            ("PRE", "PRE"),
            ("WAR", "WAR"),
            ("S98", "S98"),
        ],
        string="Site",
        required=True,
        default="MLE",
        tracking=True,
    )
    aet = fields.Char(string="AET")
    assoc_dicom = fields.Char(string="Assoc DICOM")
    ip = fields.Char(string="IP")
    mac = fields.Char(string="MAC")
    equip_type = fields.Char(string="Type", tracking=True)

    designation = fields.Char(
        string="Libellé",
        compute="_compute_designation",
        store=True,
        readonly=False,
    )
    marque = fields.Char(string="Marque", tracking=True)
    modele = fields.Char(string="Modèle")
    numero_serie = fields.Char(string="N° de série")
    numero_inventaire = fields.Char(string="N° CHC")

    # ── Classification ────────────────────────────────────────────────────────
    category_id = fields.Many2one(
        "chc_radio_listing.category",
        string="Équipements",
        required=True,
        tracking=True,
        ondelete="restrict",
    )
    service = fields.Char(string="Service")
    salle = fields.Char(string="Salle / Localisation", tracking=True)
    responsable = fields.Char(string="Référent")
    modalite = fields.Selection(
        [
            ("RX & Med Nuc", "RX & Med Nuc"),
            ("Autres disciplines", "Autres disciplines"),
            ("Imprimantes", "Imprimantes"),
        ],
        string="Équipements",
        default="RX & Med Nuc",
        tracking=True,
    )
    reseau = fields.Selection(
        [
            ("DHCP", "DHCP"),
            ("IP Fixe", "IP Fixe"),
            ("WIFI", "WIFI"),
        ],
        string="Reseau",
    )
    os = fields.Selection(
        [
            ("WIN", "WIN"),
            ("Linux", "Linux"),
        ],
        string="OS",
    )

    # ── Statut (backend Odoo, masqué dans l'UI HTML) ─────────────────────────
    statut = fields.Selection(
        [
            ("en_service", "En service"),
            ("en_panne", "En panne"),
            ("en_maintenance", "En maintenance"),
            ("hors_service", "Hors service"),
            ("en_attente", "En attente"),
        ],
        string="Statut",
        default="en_service",
        tracking=True,
    )
    color = fields.Integer(string="Couleur kanban", compute="_compute_color", store=True)

    active = fields.Boolean(default=True)

    RELAXED_STATUTS = {"en_attente", "hors_service"}

    # ── Helpers ───────────────────────────────────────────────────────────────
    @staticmethod
    def normalize_mac(mac):
        if not mac:
            return ""
        hex_str = re.sub(r"[^0-9A-Fa-f]", "", str(mac)).upper()
        if len(hex_str) != 12:
            return str(mac).strip()
        return ":".join(hex_str[i : i + 2] for i in range(0, 12, 2))

    @api.depends("site", "equip_type")
    def _compute_designation(self):
        for rec in self:
            parts = [p for p in (rec.site, rec.equip_type) if p]
            rec.designation = " / ".join(parts) if parts else "—"

    @api.depends("statut")
    def _compute_color(self):
        color_map = {
            "en_service": 10,
            "en_panne": 1,
            "en_maintenance": 3,
            "hors_service": 4,
            "en_attente": 4,
        }
        for rec in self:
            rec.color = color_map.get(rec.statut, 0)

    @api.model
    def _category_for_modalite(self, modalite):
        materiels = [
            "RX & Med Nuc",
            "Autres disciplines",
            "Imprimantes",
        ]
        if modalite not in materiels:
            modalite = "RX & Med Nuc"
        Category = self.env["chc_radio_listing.category"]
        cat = Category.search([("name", "=", modalite)], limit=1)
        if not cat:
            cat = Category.create({"name": modalite})
        return cat

    def _sync_category_from_modalite(self, vals):
        if vals.get("modalite"):
            vals["category_id"] = self._category_for_modalite(vals["modalite"]).id
        return vals

    @api.constrains("aet", "ip", "mac", "statut")
    def _check_unique_network_ids(self):
        if self.env.context.get("chc_skip_unique_check"):
            return
        Equipment = self.env["chc_radio_listing.equipment"]
        relaxed = list(self.RELAXED_STATUTS)
        for rec in self.filtered("active"):
            if rec.statut in self.RELAXED_STATUTS:
                continue
            active_domain = [
                ("active", "=", True),
                ("id", "!=", rec.id),
                ("statut", "not in", relaxed),
            ]
            if rec.aet:
                dup = Equipment.search(
                    active_domain + [("aet", "=ilike", rec.aet.strip())],
                    limit=1,
                )
                if dup:
                    raise ValidationError(
                        f"Doublon AET : « {rec.aet.strip().upper()} » est déjà utilisé "
                        f"par un autre équipement (site {dup.site or '—'}, AET {dup.aet or '—'})."
                    )
            if rec.ip:
                dup = Equipment.search(
                    active_domain + [("ip", "=", rec.ip.strip())],
                    limit=1,
                )
                if dup:
                    raise ValidationError(
                        f"Doublon IP : « {rec.ip.strip()} » est déjà utilisé "
                        f"par un autre équipement (site {dup.site or '—'}, AET {dup.aet or '—'})."
                    )
            if rec.mac:
                mac = self.normalize_mac(rec.mac)
                for candidate in Equipment.search(
                    active_domain + [("mac", "!=", False)]
                ):
                    if self.normalize_mac(candidate.mac) == mac:
                        raise ValidationError(
                            f"Doublon MAC : « {mac} » est déjà utilisé "
                            f"par un autre équipement (site {candidate.site or '—'}, "
                            f"AET {candidate.aet or '—'})."
                        )

    @staticmethod
    def normalize_os(os_val):
        if os_val == "Windows":
            return "WIN"
        if os_val in ("WIN", "Linux"):
            return os_val
        return os_val or False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("aet"):
                vals["aet"] = str(vals["aet"]).strip().upper()
            if vals.get("ip"):
                vals["ip"] = str(vals["ip"]).strip()
            if vals.get("mac"):
                vals["mac"] = self.normalize_mac(vals["mac"])
            if vals.get("os"):
                vals["os"] = self.normalize_os(vals["os"])
            self._sync_category_from_modalite(vals)
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("aet"):
            vals["aet"] = str(vals["aet"]).strip().upper()
        if vals.get("ip"):
            vals["ip"] = str(vals["ip"]).strip()
        if vals.get("mac"):
            vals["mac"] = self.normalize_mac(vals["mac"])
        if vals.get("os"):
            vals["os"] = self.normalize_os(vals["os"])
        if vals.get("modalite"):
            self._sync_category_from_modalite(vals)
        return super().write(vals)

    def action_marquer_en_service(self):
        self.write({"statut": "en_service"})

    def action_marquer_en_panne(self):
        self.write({"statut": "en_panne"})

    def action_marquer_en_maintenance(self):
        self.write({"statut": "en_maintenance"})

    def action_marquer_hors_service(self):
        self.write({"statut": "hors_service"})
