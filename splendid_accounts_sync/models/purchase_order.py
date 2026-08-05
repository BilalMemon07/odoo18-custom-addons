# -*- coding: utf-8 -*-
from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    splendid_purchase_invoice_id = fields.Char(index=True, copy=False)
    splendid_purchase_invoice_number = fields.Char(copy=False)
    splendid_is_imported = fields.Boolean(copy=False)
    splendid_raw_payload = fields.Json(copy=False)
