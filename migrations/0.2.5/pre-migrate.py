# -*- coding: utf-8 -*-
"""Keep historical OS values on the new selection.

« Windows » et « WIN » deviennent la valeur technique WIN, affichée
« WIN (à préciser) ». WIN 10 et WIN 11 ne sont pas réécrits.
"""


def migrate(cr, version):
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = 'chc_radio_listing_equipment'
           AND column_name = 'os'
        """
    )
    if not cr.fetchone():
        return
    cr.execute(
        """
        UPDATE chc_radio_listing_equipment
           SET os = 'WIN 10'
         WHERE os IS NOT NULL
           AND lower(replace(btrim(os), ' ', '')) IN ('windows10', 'win10')
           AND os <> 'WIN 10'
        """
    )
    cr.execute(
        """
        UPDATE chc_radio_listing_equipment
           SET os = 'WIN 11'
         WHERE os IS NOT NULL
           AND lower(replace(btrim(os), ' ', '')) IN ('windows11', 'win11')
           AND os <> 'WIN 11'
        """
    )
    cr.execute(
        """
        UPDATE chc_radio_listing_equipment
           SET os = 'Linux'
         WHERE os IS NOT NULL
           AND lower(btrim(os)) = 'linux'
           AND os <> 'Linux'
        """
    )
    cr.execute(
        """
        UPDATE chc_radio_listing_equipment
           SET os = 'WIN'
         WHERE os IS NOT NULL
           AND lower(btrim(os)) IN ('windows', 'win')
           AND os <> 'WIN'
        """
    )
