# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    splendid_product_id = fields.Char(index=True, copy=False)
    splendid_is_imported = fields.Boolean(copy=False)
