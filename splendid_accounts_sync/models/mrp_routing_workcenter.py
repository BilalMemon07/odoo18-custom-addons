# -*- coding: utf-8 -*-
from odoo import fields, models


class MrpRoutingWorkcenter(models.Model):
    _inherit = "mrp.routing.workcenter"

    splendid_is_external_cost = fields.Boolean(
        string="Splendid External Cost Operation",
        copy=False,
        index=True,
        help="Technical flag for the Job Order expense operation created from Splendid.",
    )
    splendid_job_expense_id = fields.Char(
        string="Splendid Job Expense ID",
        copy=False,
        index=True,
    )
    splendid_external_cost_currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        readonly=True,
    )
    splendid_external_cost = fields.Monetary(
        string="Fixed Work Order Cost",
        currency_field="splendid_external_cost_currency_id",
        copy=False,
        help="Exact fixed amount contributed by this operation to the Manufacturing Order cost. It comes from Splendid jobOrderExpenses and is never multiplied by tracked duration or Work Center hourly cost.",
    )
    splendid_expense_account_id = fields.Many2one(
        "account.account",
        string="Splendid Expense Account",
        check_company=True,
        copy=False,
    )

    def _compute_operation_cost(self):
        """Keep Odoo's operation-cost helper consistent with the fixed cost.

        Odoo 18 normally derives operation cost from duration * Work Center hourly
        cost. Splendid external expenses are fixed monetary amounts, so their
        operation cost is the payload amount while ordinary operations keep the
        native Odoo calculation.
        """
        self.ensure_one()
        if self.splendid_is_external_cost:
            return self.splendid_external_cost or 0.0
        return super()._compute_operation_cost()
