# -*- coding: utf-8 -*-
from odoo import api, fields, models


@api.depends_context("company")
def _compute_show_fmcg_fields(self):
    show = bool(self.env.company.is_fmcg_company)
    for rec in self:
        rec.show_fmcg_fields = show


class StockPicking(models.Model):
    _inherit = "stock.picking"

    show_fmcg_fields = fields.Boolean(
        string="Show FMCG Fields",
        compute="_compute_show_fmcg_fields",
        help="Technical field used by views to show FMCG fields only when the active company is marked as FMCG.",
    )
    _compute_show_fmcg_fields = _compute_show_fmcg_fields

    fmcg_region_id = fields.Many2one("ib.geo.region", string="Region")
    fmcg_zone_id = fields.Many2one("ib.geo.zone", string="Zone")
    fmcg_city_id = fields.Many2one("ib.geo.town", string="Town/City")
    fmcg_channel_id = fields.Many2one("fmcg.sales.channel", string="Channel", check_company=True)
    fmcg_territory_id = fields.Many2one("ib.geo.territory", string="Territory")

    def _fmcg_dimension_vals_from_partner(self, partner):
        return {
            "fmcg_region_id": partner.fmcg_region_id.id or False,
            "fmcg_zone_id": partner.fmcg_zone_id.id or False,
            "fmcg_city_id": partner.fmcg_city_id.id or False,
            "fmcg_territory_id": partner.fmcg_territory_id.id or False,
            "fmcg_channel_id": partner.fmcg_channel_id.id or False,
        }

    @api.onchange("partner_id")
    def _onchange_partner_id_fmcg_dimensions(self):
        for picking in self:
            if picking.company_id.is_fmcg_company and picking.partner_id:
                picking.update(picking._fmcg_dimension_vals_from_partner(picking.partner_id))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            partner_id = vals.get("partner_id")
            company_id = vals.get("company_id") or self.env.company.id
            company = self.env["res.company"].browse(company_id)
            if company.is_fmcg_company and partner_id:
                partner = self.env["res.partner"].browse(partner_id)
                for key, value in self._fmcg_dimension_vals_from_partner(partner).items():
                    vals.setdefault(key, value)
        return super().create(vals_list)


class StockMove(models.Model):
    _inherit = "stock.move"

    show_fmcg_fields = fields.Boolean(
        string="Show FMCG Fields",
        compute="_compute_show_fmcg_fields",
        help="Technical field used by views to show FMCG fields only when the active company is marked as FMCG.",
    )
    _compute_show_fmcg_fields = _compute_show_fmcg_fields

    fmcg_brand_id = fields.Many2one(
        "fmcg.brand",
        string="Brand",
        related="product_id.fmcg_brand_id",
        store=True,
        readonly=True,
        index=True,
    )
