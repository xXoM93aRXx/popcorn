"""
Recompute points_consumed on all event registrations.

Previously the field fell back to hardcoded values (3/2/6) for
non-points-mode memberships and registrations with no membership.
The fix makes those always return 0, so we force a full recompute here.
"""


def migrate(cr, version):
    from odoo import api, registry

    with registry(cr.dbname).cursor() as new_cr:
        env = api.Environment(new_cr, 1, {})
        registrations = env['event.registration'].search([])
        registrations._compute_points_consumed()
        new_cr.commit()
