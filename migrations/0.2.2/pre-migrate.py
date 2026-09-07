# -*- coding: utf-8 -*-
"""Replace the old full-page URL action with a backend client action."""


def migrate(cr, version):
    cr.execute(
        """
        SELECT res_id, model
          FROM ir_model_data
         WHERE module = 'chc_radio_listing'
           AND name = 'action_listing_app'
        """
    )
    row = cr.fetchone()
    if not row:
        return
    res_id, model = row
    if model != "ir.actions.act_url":
        return

    action_ref = "ir.actions.act_url,%s" % res_id
    cr.execute(
        "UPDATE ir_ui_menu SET action = NULL WHERE action = %s",
        (action_ref,),
    )
    cr.execute("DELETE FROM ir_act_url WHERE id = %s", (res_id,))
    cr.execute(
        """
        DELETE FROM ir_model_data
         WHERE module = 'chc_radio_listing'
           AND name = 'action_listing_app'
        """
    )
