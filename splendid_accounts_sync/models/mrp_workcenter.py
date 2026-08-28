# -*- coding: utf-8 -*-
from odoo import fields, models


class MrpWorkcenter(models.Model):
    _inherit = "mrp.workcenter"

    splendid_is_external_cost_center = fields.Boolean(
        string="Splendid External Cost Work Center",
        copy=False,
        index=True,
        help="Technical Work Center used by Splendid Job Order expense Work Orders.",
    )
