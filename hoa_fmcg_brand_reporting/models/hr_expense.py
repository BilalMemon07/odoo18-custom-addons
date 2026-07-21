# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


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


class HrExpense(models.Model):
    _inherit = "hr.expense"

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
        for expense in self:
            if not expense.product_id:
                continue
            brand, distribution = _product_fmcg_values(expense.product_id)
            expense.fmcg_brand_id = brand
            if distribution and "analytic_distribution" in expense._fields and not expense.analytic_distribution:
                expense.analytic_distribution = distribution

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
            for expense in self.filtered("product_id"):
                brand, distribution = _product_fmcg_values(expense.product_id)
                update_vals = {}
                if brand and not expense.fmcg_brand_id:
                    update_vals["fmcg_brand_id"] = brand.id
                if distribution and "analytic_distribution" in expense._fields and not expense.analytic_distribution:
                    update_vals["analytic_distribution"] = distribution
                if update_vals:
                    super(HrExpense, expense).write(update_vals)
        return res

    def _check_fmcg_expense_analytic_required(self):
        missing = self.filtered(
            lambda e: e.company_id.is_fmcg_company
            and not e.analytic_distribution
            and not e.fmcg_brand_id.analytic_account_id
        )
        if missing:
            names = ", ".join(missing.mapped("name")[:5])
            raise UserError("Set Brand / Analytic Distribution before submitting FMCG expenses: %s" % names)

    def action_submit_expenses(self):
        self._check_fmcg_expense_analytic_required()
        return super().action_submit_expenses()
