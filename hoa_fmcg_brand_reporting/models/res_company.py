# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    is_fmcg_company = fields.Boolean(
        string="FMCG Company",
        help="Enable House of Amin FMCG fields, masters, analytics and reports for this company.",
    )
