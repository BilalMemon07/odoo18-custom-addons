# -*- coding: utf-8 -*-
from odoo import fields, models, tools


COMMON_LINE_FILTER = """
    am.state = 'posted'
    AND aml.company_id IN (SELECT id FROM res_company WHERE is_fmcg_company = TRUE)
    AND (aml.display_type IS NULL OR aml.display_type NOT IN ('line_section', 'line_note'))
"""


class FMCGCostRevenueReport(models.Model):
    _name = "fmcg.cost.revenue.report"
    _description = "FMCG Cost vs Revenue Report"
    _auto = False
    _rec_name = "date"

    date = fields.Date(readonly=True)
    company_id = fields.Many2one("res.company", readonly=True)
    currency_id = fields.Many2one("res.currency", readonly=True)
    fmcg_brand_id = fields.Many2one("fmcg.brand", string="Brand", readonly=True)
    team_id = fields.Many2one("crm.team", string="Sales Team", readonly=True)
    salesperson_id = fields.Many2one("res.users", string="Salesperson", readonly=True)
    fmcg_region_id = fields.Many2one("ib.geo.region", string="Region", readonly=True)
    fmcg_city_id = fields.Many2one("ib.geo.town", string="Town/City", readonly=True)
    fmcg_territory_id = fields.Many2one("ib.geo.territory", string="Territory", readonly=True)
    fmcg_zone_id = fields.Many2one("ib.geo.zone", string="Zone", readonly=True)
    fmcg_channel_id = fields.Many2one("fmcg.sales.channel", string="Channel", readonly=True)
    revenue = fields.Monetary(readonly=True, currency_field="currency_id")
    cogs = fields.Monetary(string="COGS", readonly=True, currency_field="currency_id")
    gross_margin = fields.Monetary(readonly=True, currency_field="currency_id")
    allocated_expenses = fields.Monetary(readonly=True, currency_field="currency_id")
    net_margin = fields.Monetary(readonly=True, currency_field="currency_id")

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    MIN(aml.id) AS id,
                    COALESCE(am.invoice_date, am.date)::date AS date,
                    aml.company_id AS company_id,
                    company.currency_id AS currency_id,
                    COALESCE(aml.fmcg_brand_id, pt.fmcg_brand_id) AS fmcg_brand_id,
                    am.team_id AS team_id,
                    am.invoice_user_id AS salesperson_id,
                    am.fmcg_region_id AS fmcg_region_id,
                    am.fmcg_city_id AS fmcg_city_id,
                    am.fmcg_territory_id AS fmcg_territory_id,
                    am.fmcg_zone_id AS fmcg_zone_id,
                    am.fmcg_channel_id AS fmcg_channel_id,
                    SUM(CASE WHEN aa.account_type IN ('income', 'income_other') THEN -aml.balance ELSE 0 END) AS revenue,
                    SUM(CASE WHEN aa.account_type = 'expense_direct_cost' THEN aml.balance ELSE 0 END) AS cogs,
                    SUM(CASE WHEN aa.account_type IN ('income', 'income_other') THEN -aml.balance ELSE 0 END)
                      - SUM(CASE WHEN aa.account_type = 'expense_direct_cost' THEN aml.balance ELSE 0 END) AS gross_margin,
                    SUM(CASE WHEN aa.account_type IN ('expense', 'expense_depreciation') THEN aml.balance ELSE 0 END) AS allocated_expenses,
                    SUM(CASE WHEN aa.account_type IN ('income', 'income_other') THEN -aml.balance ELSE 0 END)
                      - SUM(CASE WHEN aa.account_type = 'expense_direct_cost' THEN aml.balance ELSE 0 END)
                      - SUM(CASE WHEN aa.account_type IN ('expense', 'expense_depreciation') THEN aml.balance ELSE 0 END) AS net_margin
                FROM account_move_line aml
                JOIN account_move am ON am.id = aml.move_id
                JOIN account_account aa ON aa.id = aml.account_id
                JOIN res_company company ON company.id = aml.company_id
                LEFT JOIN product_product pp ON pp.id = aml.product_id
                LEFT JOIN product_template pt ON pt.id = pp.product_tmpl_id
                WHERE {COMMON_LINE_FILTER}
                GROUP BY
                    COALESCE(am.invoice_date, am.date)::date,
                    aml.company_id,
                    company.currency_id,
                    COALESCE(aml.fmcg_brand_id, pt.fmcg_brand_id),
                    am.team_id,
                    am.invoice_user_id,
                    am.fmcg_region_id,
                    am.fmcg_city_id,
                    am.fmcg_territory_id,
                    am.fmcg_zone_id,
                    am.fmcg_channel_id
            )
        """)


class FMCGBrandSalesReport(models.Model):
    _name = "fmcg.brand.sales.report"
    _description = "FMCG Brand-wise Sales and Revenue Report"
    _auto = False
    _rec_name = "date"

    date = fields.Date(readonly=True)
    company_id = fields.Many2one("res.company", readonly=True)
    currency_id = fields.Many2one("res.currency", readonly=True)
    fmcg_brand_id = fields.Many2one("fmcg.brand", string="Brand", readonly=True)
    fmcg_channel_id = fields.Many2one("fmcg.sales.channel", string="Channel", readonly=True)
    team_id = fields.Many2one("crm.team", string="Sales Team", readonly=True)
    salesperson_id = fields.Many2one("res.users", string="Salesperson", readonly=True)
    quantity = fields.Float(readonly=True)
    net_revenue = fields.Monetary(readonly=True, currency_field="currency_id")
    discounts = fields.Monetary(readonly=True, currency_field="currency_id")
    returns = fields.Monetary(readonly=True, currency_field="currency_id")

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    MIN(aml.id) AS id,
                    COALESCE(am.invoice_date, am.date)::date AS date,
                    aml.company_id AS company_id,
                    company.currency_id AS currency_id,
                    COALESCE(aml.fmcg_brand_id, pt.fmcg_brand_id) AS fmcg_brand_id,
                    am.fmcg_channel_id AS fmcg_channel_id,
                    am.team_id AS team_id,
                    am.invoice_user_id AS salesperson_id,
                    SUM(CASE WHEN am.move_type = 'out_invoice' THEN aml.quantity WHEN am.move_type = 'out_refund' THEN -aml.quantity ELSE 0 END) AS quantity,
                    SUM(CASE WHEN aa.account_type IN ('income', 'income_other') THEN -aml.balance ELSE 0 END) AS net_revenue,
                    SUM(ABS(COALESCE(aml.quantity, 0) * COALESCE(aml.price_unit, 0) * COALESCE(aml.discount, 0) / 100.0)) AS discounts,
                    SUM(CASE WHEN am.move_type = 'out_refund' AND aa.account_type IN ('income', 'income_other') THEN ABS(aml.balance) ELSE 0 END) AS returns
                FROM account_move_line aml
                JOIN account_move am ON am.id = aml.move_id
                JOIN account_account aa ON aa.id = aml.account_id
                JOIN res_company company ON company.id = aml.company_id
                LEFT JOIN product_product pp ON pp.id = aml.product_id
                LEFT JOIN product_template pt ON pt.id = pp.product_tmpl_id
                WHERE {COMMON_LINE_FILTER}
                  AND am.move_type IN ('out_invoice', 'out_refund')
                  AND aa.account_type IN ('income', 'income_other')
                GROUP BY
                    COALESCE(am.invoice_date, am.date)::date,
                    aml.company_id,
                    company.currency_id,
                    COALESCE(aml.fmcg_brand_id, pt.fmcg_brand_id),
                    am.fmcg_channel_id,
                    am.team_id,
                    am.invoice_user_id
            )
        """)


class FMCGRegionReport(models.Model):
    _name = "fmcg.region.report"
    _description = "FMCG Region-wise Revenue, Collections and Outstanding Report"
    _auto = False
    _rec_name = "date"

    date = fields.Date(readonly=True)
    company_id = fields.Many2one("res.company", readonly=True)
    currency_id = fields.Many2one("res.currency", readonly=True)
    fmcg_region_id = fields.Many2one("ib.geo.region", string="Region", readonly=True)
    fmcg_city_id = fields.Many2one("ib.geo.town", string="Town/City", readonly=True)
    fmcg_territory_id = fields.Many2one("ib.geo.territory", string="Territory", readonly=True)
    fmcg_zone_id = fields.Many2one("ib.geo.zone", string="Zone", readonly=True)
    fmcg_channel_id = fields.Many2one("fmcg.sales.channel", string="Channel", readonly=True)
    revenue = fields.Monetary(readonly=True, currency_field="currency_id")
    collections = fields.Monetary(readonly=True, currency_field="currency_id")
    outstanding = fields.Monetary(readonly=True, currency_field="currency_id")

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    MIN(am.id) AS id,
                    COALESCE(am.invoice_date, am.date)::date AS date,
                    am.company_id AS company_id,
                    company.currency_id AS currency_id,
                    am.fmcg_region_id AS fmcg_region_id,
                    am.fmcg_city_id AS fmcg_city_id,
                    am.fmcg_territory_id AS fmcg_territory_id,
                    am.fmcg_zone_id AS fmcg_zone_id,
                    am.fmcg_channel_id AS fmcg_channel_id,
                    SUM(am.amount_untaxed_signed) AS revenue,
                    SUM(am.amount_total_signed - am.amount_residual_signed) AS collections,
                    SUM(am.amount_residual_signed) AS outstanding
                FROM account_move am
                JOIN res_company company ON company.id = am.company_id
                WHERE am.state = 'posted'
                  AND am.move_type IN ('out_invoice', 'out_refund')
                  AND am.company_id IN (SELECT id FROM res_company WHERE is_fmcg_company = TRUE)
                GROUP BY
                    COALESCE(am.invoice_date, am.date)::date,
                    am.company_id,
                    company.currency_id,
                    am.fmcg_region_id,
                    am.fmcg_city_id,
                    am.fmcg_territory_id,
                    am.fmcg_zone_id,
                    am.fmcg_channel_id
            )
        """)


class FMCGSalespersonReport(models.Model):
    _name = "fmcg.salesperson.report"
    _description = "FMCG Salesperson Performance Report"
    _auto = False
    _rec_name = "date"

    date = fields.Date(readonly=True)
    company_id = fields.Many2one("res.company", readonly=True)
    currency_id = fields.Many2one("res.currency", readonly=True)
    salesperson_id = fields.Many2one("res.users", string="Salesperson", readonly=True)
    team_id = fields.Many2one("crm.team", string="Sales Team", readonly=True)
    fmcg_brand_id = fields.Many2one("fmcg.brand", string="Brand", readonly=True)
    fmcg_region_id = fields.Many2one("ib.geo.region", string="Region", readonly=True)
    fmcg_city_id = fields.Many2one("ib.geo.town", string="Town/City", readonly=True)
    fmcg_territory_id = fields.Many2one("ib.geo.territory", string="Territory", readonly=True)
    fmcg_zone_id = fields.Many2one("ib.geo.zone", string="Zone", readonly=True)
    fmcg_channel_id = fields.Many2one("fmcg.sales.channel", string="Channel", readonly=True)
    orders_count = fields.Integer(string="Orders", readonly=True)
    revenue = fields.Monetary(readonly=True, currency_field="currency_id")
    returns = fields.Monetary(readonly=True, currency_field="currency_id")
    collections = fields.Monetary(readonly=True, currency_field="currency_id")
    outstanding = fields.Monetary(readonly=True, currency_field="currency_id")

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    MIN(aml.id) AS id,
                    COALESCE(am.invoice_date, am.date)::date AS date,
                    aml.company_id AS company_id,
                    company.currency_id AS currency_id,
                    am.invoice_user_id AS salesperson_id,
                    am.team_id AS team_id,
                    COALESCE(aml.fmcg_brand_id, pt.fmcg_brand_id) AS fmcg_brand_id,
                    am.fmcg_region_id AS fmcg_region_id,
                    am.fmcg_city_id AS fmcg_city_id,
                    am.fmcg_territory_id AS fmcg_territory_id,
                    am.fmcg_zone_id AS fmcg_zone_id,
                    am.fmcg_channel_id AS fmcg_channel_id,
                    COUNT(DISTINCT am.id) AS orders_count,
                    SUM(CASE WHEN aa.account_type IN ('income', 'income_other') THEN -aml.balance ELSE 0 END) AS revenue,
                    SUM(CASE WHEN am.move_type = 'out_refund' AND aa.account_type IN ('income', 'income_other') THEN ABS(aml.balance) ELSE 0 END) AS returns,
                    SUM(
                        CASE WHEN aa.account_type IN ('income', 'income_other') AND am.amount_total_signed != 0
                             THEN (-aml.balance) * ((am.amount_total_signed - am.amount_residual_signed) / am.amount_total_signed)
                             ELSE 0 END
                    ) AS collections,
                    SUM(
                        CASE WHEN aa.account_type IN ('income', 'income_other') AND am.amount_total_signed != 0
                             THEN (-aml.balance) * (am.amount_residual_signed / am.amount_total_signed)
                             ELSE 0 END
                    ) AS outstanding
                FROM account_move_line aml
                JOIN account_move am ON am.id = aml.move_id
                JOIN account_account aa ON aa.id = aml.account_id
                JOIN res_company company ON company.id = aml.company_id
                LEFT JOIN product_product pp ON pp.id = aml.product_id
                LEFT JOIN product_template pt ON pt.id = pp.product_tmpl_id
                WHERE {COMMON_LINE_FILTER}
                  AND am.move_type IN ('out_invoice', 'out_refund')
                  AND aa.account_type IN ('income', 'income_other')
                GROUP BY
                    COALESCE(am.invoice_date, am.date)::date,
                    aml.company_id,
                    company.currency_id,
                    am.invoice_user_id,
                    am.team_id,
                    COALESCE(aml.fmcg_brand_id, pt.fmcg_brand_id),
                    am.fmcg_region_id,
                    am.fmcg_city_id,
                    am.fmcg_territory_id,
                    am.fmcg_zone_id,
                    am.fmcg_channel_id
            )
        """)


class FMCGBrandPLReport(models.Model):
    _name = "fmcg.brand.pl.report"
    _description = "FMCG Brand P&L Report"
    _auto = False
    _rec_name = "date"

    date = fields.Date(readonly=True)
    company_id = fields.Many2one("res.company", readonly=True)
    currency_id = fields.Many2one("res.currency", readonly=True)
    fmcg_brand_id = fields.Many2one("fmcg.brand", string="Brand", readonly=True)
    revenue = fields.Monetary(readonly=True, currency_field="currency_id")
    cogs = fields.Monetary(string="COGS", readonly=True, currency_field="currency_id")
    expenses = fields.Monetary(readonly=True, currency_field="currency_id")
    profit = fields.Monetary(readonly=True, currency_field="currency_id")

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    MIN(aml.id) AS id,
                    COALESCE(am.invoice_date, am.date)::date AS date,
                    aml.company_id AS company_id,
                    company.currency_id AS currency_id,
                    COALESCE(aml.fmcg_brand_id, pt.fmcg_brand_id) AS fmcg_brand_id,
                    SUM(CASE WHEN aa.account_type IN ('income', 'income_other') THEN -aml.balance ELSE 0 END) AS revenue,
                    SUM(CASE WHEN aa.account_type = 'expense_direct_cost' THEN aml.balance ELSE 0 END) AS cogs,
                    SUM(CASE WHEN aa.account_type IN ('expense', 'expense_depreciation') THEN aml.balance ELSE 0 END) AS expenses,
                    SUM(CASE WHEN aa.account_type IN ('income', 'income_other') THEN -aml.balance ELSE 0 END)
                      - SUM(CASE WHEN aa.account_type = 'expense_direct_cost' THEN aml.balance ELSE 0 END)
                      - SUM(CASE WHEN aa.account_type IN ('expense', 'expense_depreciation') THEN aml.balance ELSE 0 END) AS profit
                FROM account_move_line aml
                JOIN account_move am ON am.id = aml.move_id
                JOIN account_account aa ON aa.id = aml.account_id
                JOIN res_company company ON company.id = aml.company_id
                LEFT JOIN product_product pp ON pp.id = aml.product_id
                LEFT JOIN product_template pt ON pt.id = pp.product_tmpl_id
                WHERE {COMMON_LINE_FILTER}
                GROUP BY
                    COALESCE(am.invoice_date, am.date)::date,
                    aml.company_id,
                    company.currency_id,
                    COALESCE(aml.fmcg_brand_id, pt.fmcg_brand_id)
            )
        """)
