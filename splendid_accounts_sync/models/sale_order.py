# -*- coding: utf-8 -*-
from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    splendid_external_id = fields.Char(index=True, copy=False)
    splendid_source_model = fields.Char(index=True, copy=False)
    splendid_is_imported = fields.Boolean(copy=False)
    splendid_raw_payload = fields.Json(copy=False)
