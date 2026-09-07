# -*- coding: utf-8 -*-
"""Remove the redundant first-level « Listing Radio » menu entry."""


def migrate(cr, version):
    cr.execute(
        """
        SELECT res_id
          FROM ir_model_data
         WHERE module = 'chc_radio_listing'
           AND name = 'menu_radio_listing_app'
        """
    )
    row = cr.fetchone()
    if not row:
        return
    menu_id = row[0]
    cr.execute(
        """
        SELECT 1
          FROM information_schema.tables
         WHERE table_name = 'ir_ui_menu_group_rel'
        """
    )
    if cr.fetchone():
        cr.execute(
            "DELETE FROM ir_ui_menu_group_rel WHERE menu_id = %s",
            (menu_id,),
        )
    cr.execute("DELETE FROM ir_ui_menu WHERE id = %s", (menu_id,))
    cr.execute(
        """
        DELETE FROM ir_model_data
         WHERE module = 'chc_radio_listing'
           AND name = 'menu_radio_listing_app'
        """
    )
