from odoo import models, fields


class GeoRegion(models.Model):
    _name = "ib.geo.region"
    _description = "Region"
    _order = "name"

    name = fields.Char(string="Region", required=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("region_name_unique", "unique(name)", "Region must be unique."),
    ]


class GeoZone(models.Model):
    _name = "ib.geo.zone"
    _description = "Zone"
    _order = "name"

    name = fields.Char(string="Zone", required=True)
    region_id = fields.Many2one(
        "ib.geo.region",
        string="Region",
        required=True,
        ondelete="restrict",
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("zone_name_region_unique", "unique(name, region_id)", "Zone must be unique per Region."),
    ]


class GeoTerritory(models.Model):
    _name = "ib.geo.territory"
    _description = "Territory"
    _order = "name"

    name = fields.Char(string="Territory", required=True)
    zone_id = fields.Many2one(
        "ib.geo.zone",
        string="Zone",
        required=True,
        ondelete="restrict",
    )
    region_id = fields.Many2one(
        "ib.geo.region",
        string="Region",
        related="zone_id.region_id",
        store=True,
        readonly=True,
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("territory_name_zone_unique", "unique(name, zone_id)", "Territory must be unique per Zone."),
    ]


class GeoTown(models.Model):
    _name = "ib.geo.town"
    _description = "Town"
    _order = "name"

    name = fields.Char(string="Town", required=True)
    territory_id = fields.Many2one(
        "ib.geo.territory",
        string="Territory",
        required=True,
        ondelete="restrict",
    )
    zone_id = fields.Many2one(
        "ib.geo.zone",
        string="Zone",
        related="territory_id.zone_id",
        store=True,
        readonly=True,
    )
    region_id = fields.Many2one(
        "ib.geo.region",
        string="Region",
        related="territory_id.region_id",
        store=True,
        readonly=True,
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("town_name_territory_unique", "unique(name, territory_id)", "Town must be unique per Territory."),
    ]