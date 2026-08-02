# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountTax(models.Model):
    _inherit = "account.tax"

    splendid_tax_id = fields.Char(index=True, copy=False)
    splendid_tax_direction = fields.Selection([
        ("sale", "Sale/Out"),
        ("purchase", "Purchase/In"),
    ], index=True, copy=False)
    splendid_tax_use = fields.Selection([
        ("sale", "Sale"),
        ("purchase", "Purchase"),
        ("none", "None"),
    ], index=True, copy=False)
    splendid_is_imported = fields.Boolean(copy=False)
