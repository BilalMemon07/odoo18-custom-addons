# -*- coding: utf-8 -*-
from odoo import api, fields, models


@api.depends_context("company")
def _compute_show_fmcg_fields(self):
    show = bool(self.env.company.is_fmcg_company)
    for rec in self:
        rec.show_fmcg_fields = show


class ResPartner(models.Model):
    _inherit = "res.partner"

    show_fmcg_fields = fields.Boolean(
        string="Show FMCG Fields",
        compute="_compute_show_fmcg_fields",
        help="Technical field used by views to show FMCG fields only when the active company is marked as FMCG.",
    )
    _compute_show_fmcg_fields = _compute_show_fmcg_fields

    # Aliases used by the FMCG reporting module. The actual location masters
    # and editable contact fields are defined in odoo_genics_x_amin_enterprise_ext:
    # ib.geo.region / ib.geo.zone / ib.geo.territory / ib.geo.town.
    fmcg_city_id = fields.Many2one(
        "ib.geo.town",
        string="Town/City",
        related="geo_town_id",
        store=True,
        readonly=True,
    )
    fmcg_territory_id = fields.Many2one(
        "ib.geo.territory",
        string="Territory",
        related="geo_territory_id",
        store=True,
        readonly=True,
    )
    fmcg_zone_id = fields.Many2one(
        "ib.geo.zone",
        string="Zone",
        related="geo_zone_id",
        store=True,
        readonly=True,
    )
    fmcg_region_id = fields.Many2one(
        "ib.geo.region",
        string="Region",
        related="geo_region_id",
        store=True,
        readonly=True,
    )
    fmcg_channel_id = fields.Many2one("fmcg.sales.channel", string="Channel")
