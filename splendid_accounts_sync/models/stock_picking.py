# -*- coding: utf-8 -*-
from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    splendid_sale_invoice_id = fields.Char(index=True, copy=False)
    splendid_sale_return_id = fields.Char(index=True, copy=False)
    splendid_purchase_invoice_id = fields.Char(index=True, copy=False)
    splendid_purchase_return_id = fields.Char(index=True, copy=False)
    splendid_source_model = fields.Char(index=True, copy=False)
    splendid_is_imported = fields.Boolean(copy=False)
    splendid_raw_payload = fields.Json(copy=False)
