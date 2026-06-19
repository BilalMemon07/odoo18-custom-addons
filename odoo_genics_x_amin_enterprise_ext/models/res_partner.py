from odoo import models, fields


class ResPartner(models.Model):
    _inherit = "res.partner"

    geo_town_id = fields.Many2one(
        "ib.geo.town",
        string="Town",
        ondelete="restrict",
    )

    geo_territory_id = fields.Many2one(
        "ib.geo.territory",
        string="Territory",
        related="geo_town_id.territory_id",
        store=True,
        readonly=True,
    )

    geo_zone_id = fields.Many2one(
        "ib.geo.zone",
        string="Zone",
        related="geo_town_id.zone_id",
        store=True,
        readonly=True,
    )

    geo_region_id = fields.Many2one(
        "ib.geo.region",
        string="Region",
        related="geo_town_id.region_id",
        store=True,
        readonly=True,
    )