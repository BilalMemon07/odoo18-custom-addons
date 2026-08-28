# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    splendid_product_id = fields.Char(index=True, copy=False)
    splendid_uom_symbol = fields.Char(string="Splendid UoM Symbol", copy=False)
    splendid_track_inventory = fields.Boolean(string="Splendid Track Inventory", copy=False)
    splendid_is_imported = fields.Boolean(copy=False)
