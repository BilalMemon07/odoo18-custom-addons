# -*- coding: utf-8 -*-
from odoo import api, fields, models


@api.depends_context("company")
def _compute_show_fmcg_fields(self):
    show = bool(self.env.company.is_fmcg_company)
    for rec in self:
        rec.show_fmcg_fields = show


def _analytic_distribution_from_account(account):
    return {str(account.id): 100.0} if account else False


def _product_fmcg_values(product):
    if not product:
        return False, False
    brand = product.fmcg_brand_id
    analytic = product._get_fmcg_analytic_account() if hasattr(product, "_get_fmcg_analytic_account") else False
    return brand, _analytic_distribution_from_account(analytic)


class SaleOrder(models.Model):
    _inherit = "sale.order"

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
        for order in self:
            if order.company_id.is_fmcg_company and order.partner_id:
                order.update(order._fmcg_dimension_vals_from_partner(order.partner_id))

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

    def write(self, vals):
        res = super().write(vals)
        if "partner_id" in vals and not self.env.context.get("skip_fmcg_partner_sync"):
            for order in self.filtered(lambda o: o.company_id.is_fmcg_company and o.partner_id):
                dimension_vals = order._fmcg_dimension_vals_from_partner(order.partner_id)
                explicit_keys = set(vals.keys()) & set(dimension_vals.keys())
                if not explicit_keys:
                    order.with_context(skip_fmcg_partner_sync=True).write(dimension_vals)
        return res

    def _prepare_invoice(self):
        res = super()._prepare_invoice()
        if self.company_id.is_fmcg_company:
            res.update({
                "fmcg_region_id": self.fmcg_region_id.id or False,
                "fmcg_zone_id": self.fmcg_zone_id.id or False,
                "fmcg_city_id": self.fmcg_city_id.id or False,
                "fmcg_territory_id": self.fmcg_territory_id.id or False,
                "fmcg_channel_id": self.fmcg_channel_id.id or False,
            })
        return res


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    show_fmcg_fields = fields.Boolean(
        string="Show FMCG Fields",
        compute="_compute_show_fmcg_fields",
        help="Technical field used by views to show FMCG fields only when the active company is marked as FMCG.",
    )
    _compute_show_fmcg_fields = _compute_show_fmcg_fields

    fmcg_brand_id = fields.Many2one("fmcg.brand", string="Brand", check_company=True, index=True)

    @api.onchange("fmcg_brand_id")
    def _onchange_fmcg_brand_id(self):
        for rec in self:
            account = rec.fmcg_brand_id.analytic_account_id
            if account and "analytic_distribution" in rec._fields and not rec.analytic_distribution:
                rec.analytic_distribution = _analytic_distribution_from_account(account)

    @api.onchange("product_id")
    def _onchange_product_id_fmcg_brand(self):
        for line in self:
            if not line.product_id:
                continue
            brand, distribution = _product_fmcg_values(line.product_id)
            line.fmcg_brand_id = brand
            if distribution and not line.analytic_distribution:
                line.analytic_distribution = distribution

    @api.model_create_multi
    def create(self, vals_list):
        Product = self.env["product.product"]
        for vals in vals_list:
            product = Product.browse(vals.get("product_id")) if vals.get("product_id") else False
            brand, distribution = _product_fmcg_values(product)
            if brand:
                vals.setdefault("fmcg_brand_id", brand.id)
            if distribution and "analytic_distribution" in self._fields:
                vals.setdefault("analytic_distribution", distribution)
        return super().create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        if "product_id" in vals:
            for line in self.filtered("product_id"):
                brand, distribution = _product_fmcg_values(line.product_id)
                update_vals = {}
                if brand and not line.fmcg_brand_id:
                    update_vals["fmcg_brand_id"] = brand.id
                if distribution and "analytic_distribution" in line._fields and not line.analytic_distribution:
                    update_vals["analytic_distribution"] = distribution
                if update_vals:
                    super(SaleOrderLine, line).write(update_vals)
        return res

    def _prepare_invoice_line(self, **optional_values):
        res = super()._prepare_invoice_line(**optional_values)
        if self.order_id.company_id.is_fmcg_company:
            brand, distribution = _product_fmcg_values(self.product_id)
            res["fmcg_brand_id"] = self.fmcg_brand_id.id or (brand.id if brand else False)
            if distribution:
                res["analytic_distribution"] = res.get("analytic_distribution") or self.analytic_distribution or distribution
        return res
