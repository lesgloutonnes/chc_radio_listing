# -*- coding: utf-8 -*-
"""Stop implying listing access from Internal User (base.group_user)."""


def migrate(cr, version):
    cr.execute(
        """
        SELECT 1
          FROM information_schema.tables
         WHERE table_name = 'res_groups_implied_rel'
        """
    )
    if not cr.fetchone():
        return
    cr.execute(
        """
        DELETE FROM res_groups_implied_rel
         WHERE gid IN (
                SELECT res_id FROM ir_model_data
                 WHERE module = 'base' AND name = 'group_user'
         )
           AND hid IN (
                SELECT res_id FROM ir_model_data
                 WHERE module = 'chc_radio_listing'
                   AND name = 'group_radio_listing_user'
         )
        """
    )
