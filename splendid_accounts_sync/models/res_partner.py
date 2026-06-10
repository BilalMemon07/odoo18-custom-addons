# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    splendid_customer_id = fields.Char(index=True, copy=False)
    splendid_vendor_id = fields.Char(index=True, copy=False)
    splendid_is_imported = fields.Boolean(copy=False)
