# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


@api.depends_context("company")
def _compute_show_fmcg_fields(self):
    show = bool(self.env.company.is_fmcg_company)
    for rec in self:
        rec.show_fmcg_fields = show


class ProductCategory(models.Model):
    _inherit = "product.category"

    show_fmcg_fields = fields.Boolean(
        string="Show FMCG Fields",
        compute="_compute_show_fmcg_fields",
        help="Technical field used by views to show FMCG fields only when the active company is marked as FMCG.",
    )
    _compute_show_fmcg_fields = _compute_show_fmcg_fields

    is_fmcg_category = fields.Boolean(string="FMCG Category")
    fmcg_brand_id = fields.Many2one("fmcg.brand", string="Brand")


class ProductTemplate(models.Model):
    _inherit = "product.template"

    show_fmcg_fields = fields.Boolean(
        string="Show FMCG Fields",
        compute="_compute_show_fmcg_fields",
        help="Technical field used by views to show FMCG fields only when the active company is marked as FMCG.",
    )
    _compute_show_fmcg_fields = _compute_show_fmcg_fields

    fmcg_brand_id = fields.Many2one(
        "fmcg.brand",
        string="Brand",
        index=True,
        tracking=True,
    )
    fmcg_analytic_account_id = fields.Many2one(
        "account.analytic.account",
        string="Default Brand Analytic Account",
        check_company=True,
        help="Overrides the brand analytic account for this product. If empty, the brand analytic account is used.",
    )

    @api.onchange("fmcg_brand_id")
    def _onchange_fmcg_brand_id(self):
        for product in self:
            if product.fmcg_brand_id and not product.fmcg_analytic_account_id:
                product.fmcg_analytic_account_id = product.fmcg_brand_id.analytic_account_id

    @api.constrains("fmcg_brand_id", "categ_id", "company_id")
    def _check_fmcg_brand_required(self):
        for product in self:
            company = product.company_id or self.env.company
            if company.is_fmcg_company and product.categ_id.is_fmcg_category and not product.fmcg_brand_id:
                raise ValidationError("Brand is required for products in an FMCG category.")

    def _get_fmcg_analytic_account(self):
        self.ensure_one()
        return self.fmcg_analytic_account_id or self.fmcg_brand_id.analytic_account_id

    def _get_product_accounts(self):
        """Prefer brand-level accounts when configured, otherwise keep Odoo standard mapping."""
        accounts = super()._get_product_accounts()
        self.ensure_one()
        brand = self.fmcg_brand_id
        company = self.company_id or self.env.company
        if company.is_fmcg_company and brand:
            if brand.income_account_id:
                accounts["income"] = brand.income_account_id
            if brand.expense_account_id:
                accounts["expense"] = brand.expense_account_id
            if brand.stock_valuation_account_id and "stock_valuation" in accounts:
                accounts["stock_valuation"] = brand.stock_valuation_account_id
        return accounts


class ProductProduct(models.Model):
    _inherit = "product.product"

    show_fmcg_fields = fields.Boolean(
        string="Show FMCG Fields",
        compute="_compute_show_fmcg_fields",
        help="Technical field used by views to show FMCG fields only when the active company is marked as FMCG.",
    )
    _compute_show_fmcg_fields = _compute_show_fmcg_fields

    fmcg_brand_id = fields.Many2one(
        related="product_tmpl_id.fmcg_brand_id",
        store=True,
        readonly=False,
        string="Brand",
        index=True,
    )
    fmcg_analytic_account_id = fields.Many2one(
        related="product_tmpl_id.fmcg_analytic_account_id",
        store=True,
        readonly=False,
        string="Default Brand Analytic Account",
    )

    def _get_fmcg_analytic_account(self):
        self.ensure_one()
        return self.fmcg_analytic_account_id or self.fmcg_brand_id.analytic_account_id
