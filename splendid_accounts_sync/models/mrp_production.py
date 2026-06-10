# -*- coding: utf-8 -*-
from odoo import fields, models


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    splendid_external_id = fields.Char(index=True, copy=False)
    splendid_source_model = fields.Char(index=True, copy=False)
    splendid_is_imported = fields.Boolean(copy=False)
    splendid_raw_payload = fields.Json(copy=False)
