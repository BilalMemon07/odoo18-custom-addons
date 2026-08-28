# -*- coding: utf-8 -*-
from odoo import fields, models


class MrpBom(models.Model):
    _inherit = "mrp.bom"

    splendid_job_order_id = fields.Char(string="Splendid Job Order ID", index=True, copy=False)
    splendid_job_order_number = fields.Char(string="Splendid Job Order Number", index=True, copy=False)
    splendid_is_imported = fields.Boolean(copy=False, index=True)


class MrpBomLine(models.Model):
    _inherit = "mrp.bom.line"

    splendid_job_order_detail_id = fields.Char(string="Splendid Job Order Detail ID", index=True, copy=False)
    splendid_warehouse_id = fields.Char(string="Splendid Warehouse ID", copy=False)
