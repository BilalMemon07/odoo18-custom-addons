# -*- coding: utf-8 -*-
from odoo import fields, models


class FMCGBrand(models.Model):
    _name = "fmcg.brand"
    _description = "FMCG Brand"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name"

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(tracking=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        index=True,
        required=True,
    )
    analytic_account_id = fields.Many2one(
        "account.analytic.account",
        string="Default Brand Analytic Account",
        check_company=True,
        tracking=True,
    )
    income_account_id = fields.Many2one(
        "account.account",
        string="Brand Income Account",
        check_company=True,
        domain="[('deprecated','=',False), ('account_type', 'in', ('income', 'income_other'))]",
    )
    expense_account_id = fields.Many2one(
        "account.account",
        string="Brand COGS/Expense Account",
        check_company=True,
        domain="[('deprecated','=',False), ('account_type', 'in', ('expense_direct_cost', 'expense'))]",
    )
    stock_valuation_account_id = fields.Many2one(
        "account.account",
        string="Brand Stock Valuation Account",
        check_company=True,
        domain="[('deprecated','=',False)]",
    )

    _sql_constraints = [
        ("name_company_uniq", "unique(name, company_id)", "Brand already exists for this company."),
        ("code_company_uniq", "unique(code, company_id)", "Brand code already exists for this company."),
    ]

    def action_create_analytic_account(self):
        """Create one analytic account per brand when missing."""
        AnalyticAccount = self.env["account.analytic.account"]
        plan = self.env["account.analytic.plan"].search([("name", "=", "Brand Analytics")], limit=1)
        if not plan:
            plan = self.env["account.analytic.plan"].create({"name": "Brand Analytics"})
        for brand in self:
            if brand.analytic_account_id:
                continue
            brand.analytic_account_id = AnalyticAccount.create({
                "name": brand.name,
                "plan_id": plan.id,
                "company_id": brand.company_id.id,
            })
        return True


class FMCGSalesChannel(models.Model):
    _name = "fmcg.sales.channel"
    _description = "FMCG Sales Channel"
    _order = "sequence, name"

    name = fields.Char(required=True)
    code = fields.Char()
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True, index=True)

    _sql_constraints = [
        ("name_company_uniq", "unique(name, company_id)", "Sales channel already exists for this company."),
    ]
