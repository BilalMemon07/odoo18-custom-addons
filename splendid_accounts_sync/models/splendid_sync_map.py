# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SplendidSyncMap(models.Model):
    _name = "splendid.sync.map"
    _description = "Splendid External ID Mapping"
    _rec_name = "display_name"
    _order = "external_model, external_id"

    connection_id = fields.Many2one("splendid.account.connection", required=True, ondelete="cascade")
    company_id = fields.Many2one("res.company", related="connection_id.company_id", store=True, readonly=True)
    external_model = fields.Char(required=True, index=True)
    external_id = fields.Char(required=True, index=True)
    external_name = fields.Char()
    odoo_model = fields.Char(required=True, index=True)
    res_id = fields.Integer(required=True, index=True)
    display_name = fields.Char(compute="_compute_display_name", store=True)
    last_payload_hash = fields.Char()
    last_sync_date = fields.Datetime(default=fields.Datetime.now)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "splendid_external_unique",
            "unique(connection_id, external_model, external_id, odoo_model)",
            "The same Splendid record is already mapped to this Odoo model.",
        )
    ]

    @api.depends("external_model", "external_id", "external_name", "odoo_model", "res_id")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "%s/%s → %s,%s" % (
                rec.external_model or "",
                rec.external_id or "",
                rec.odoo_model or "",
                rec.res_id or "",
            )
