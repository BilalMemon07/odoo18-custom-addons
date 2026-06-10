# -*- coding: utf-8 -*-
from odoo import fields, models


class SplendidSyncLog(models.Model):
    _name = "splendid.sync.log"
    _description = "Splendid Sync Log"
    _order = "create_date desc, id desc"

    connection_id = fields.Many2one("splendid.account.connection", required=True, ondelete="cascade")
    company_id = fields.Many2one("res.company", related="connection_id.company_id", store=True, readonly=True)
    sync_type = fields.Char(required=True)
    external_id = fields.Char(index=True)
    odoo_model = fields.Char()
    res_id = fields.Integer()
    state = fields.Selection(
        [("success", "Success"), ("skipped", "Skipped"), ("error", "Error")],
        default="success",
        required=True,
        index=True,
    )
    message = fields.Text()
    payload = fields.Json()
