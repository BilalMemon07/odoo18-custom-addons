# -*- coding: utf-8 -*-
from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    splendid_sale_invoice_id = fields.Char(index=True, copy=False)
    splendid_sale_invoice_number = fields.Char(copy=False)
    splendid_is_imported = fields.Boolean(copy=False)
