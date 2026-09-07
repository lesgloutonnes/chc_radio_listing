# -*- coding: utf-8 -*-
{
    "name": "CHC - Listing Radio",
    "summary": "Listing et gestion équipement d'imagerie médicale.",
    "description": """
Listing et gestion équipement d'imagerie médicale.
    """,
    "author": "CHC",
    "website": "https://www.chc.be",
    "license": "LGPL-3",
    "category": "Medical / Equipment",
    "version": "0.2.4",
    "depends": ["base", "web", "mail"],
    "data": [
        "security/init_groups.xml",
        "security/ir.model.access.csv",
        "data/default_data.xml",
        "views/equipment_category_views.xml",
        "views/equipment_views.xml",
        "views/dashboard_views.xml",
        "views/listing_app_views.xml",
        "views/menu_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "chc_radio_listing/static/src/css/radio_listing.css",
            "chc_radio_listing/static/src/js/listing_app_action.js",
            "chc_radio_listing/static/src/xml/listing_app_action.xml",
        ],
    },
    "application": True,
    "installable": True,
}
