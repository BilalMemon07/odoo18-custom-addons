# -*- coding: utf-8 -*-
from odoo import fields, models


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    splendid_warehouse_id = fields.Char(index=True, copy=False)
    splendid_is_imported = fields.Boolean(copy=False)
