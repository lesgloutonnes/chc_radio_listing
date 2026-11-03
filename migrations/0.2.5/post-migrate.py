# -*- coding: utf-8 -*-
"""Garantit une seule catégorie Odoo « Stations PACS »."""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Category = env["chc_radio_listing.category"]
    Data = env["ir.model.data"].sudo()
    xmlid = Data.search(
        [
            ("module", "=", "chc_radio_listing"),
            ("name", "=", "category_stations_pacs"),
            ("model", "=", "chc_radio_listing.category"),
        ],
        limit=1,
    )
    cats = Category.with_context(active_test=False).search(
        [("name", "=", "Stations PACS")]
    )
    if xmlid and Category.browse(xmlid.res_id).exists():
        primary = Category.browse(xmlid.res_id)
    elif cats:
        primary = cats[0]
        if not xmlid:
            Data.create(
                {
                    "module": "chc_radio_listing",
                    "name": "category_stations_pacs",
                    "model": "chc_radio_listing.category",
                    "res_id": primary.id,
                    "noupdate": True,
                }
            )
    else:
        primary = Category.create(
            {
                "name": "Stations PACS",
                "code": "PACS",
                "sequence": 4,
                "color": 7,
            }
        )
        Data.create(
            {
                "module": "chc_radio_listing",
                "name": "category_stations_pacs",
                "model": "chc_radio_listing.category",
                "res_id": primary.id,
                "noupdate": True,
            }
        )

    if not primary.code:
        primary.code = "PACS"
    if primary.sequence in (False, 0, 10):
        primary.sequence = 4
    if not primary.color:
        primary.color = 7
    extras = cats - primary
    if extras:
        env["chc_radio_listing.equipment"].with_context(
            active_test=False
        ).search([("category_id", "in", extras.ids)]).write(
            {"category_id": primary.id}
        )
        extras.unlink()
