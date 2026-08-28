# -*- coding: utf-8 -*-
from odoo import fields, models


class MrpWorkorder(models.Model):
    _inherit = "mrp.workorder"

    splendid_is_external_cost = fields.Boolean(
        related="operation_id.splendid_is_external_cost",
        string="Splendid Fixed Cost",
        store=True,
        readonly=True,
    )
    splendid_job_expense_id = fields.Char(
        related="operation_id.splendid_job_expense_id",
        string="Splendid Job Expense ID",
        store=True,
        readonly=True,
    )
    splendid_external_cost_currency_id = fields.Many2one(
        "res.currency",
        related="operation_id.splendid_external_cost_currency_id",
        readonly=True,
    )
    splendid_external_cost = fields.Monetary(
        related="operation_id.splendid_external_cost",
        string="Fixed Work Order Cost",
        currency_field="splendid_external_cost_currency_id",
        store=True,
        readonly=True,
        help=(
            "Exact fixed cost received from Splendid for this external-cost Work Order. "
            "For this Work Order Odoo must not calculate cost as duration x hourly rate."
        ),
    )
    splendid_expense_account_id = fields.Many2one(
        "account.account",
        related="operation_id.splendid_expense_account_id",
        string="Splendid Expense Account",
        store=True,
        readonly=True,
    )

    def _cal_cost(self, date=False):
        """Use the exact Splendid amount instead of duration * hourly rate.

        Odoo 18 normally values a Work Order from its tracked time multiplied by
        ``workcenter_id.costs_hour``.  Splendid ``jobOrderExpenses`` are already a
        total monetary amount for the Job Order, so multiplying them by duration
        would be wrong.  External-cost Work Orders therefore contribute the fixed
        payload amount exactly once.  Ordinary Work Orders stay 100% standard.

        ``mrp_account.mrp.production._cal_price`` sums this method for every Work
        Order, so this fixed amount becomes part of the finished-product
        manufacturing cost for FIFO/AVCO valuation without using ``extra_cost``.
        """
        total = 0.0
        for workorder in self:
            if workorder.splendid_is_external_cost:
                if workorder.state != "cancel":
                    total += workorder.splendid_external_cost or 0.0
                continue
            total += super(MrpWorkorder, workorder)._cal_cost(date=date)
        return total

    def _compute_expected_operation_cost(self, without_employee_cost=False):
        self.ensure_one()
        if self.splendid_is_external_cost:
            return self.splendid_external_cost or 0.0
        return super()._compute_expected_operation_cost(
            without_employee_cost=without_employee_cost
        )

    def _compute_current_operation_cost(self):
        self.ensure_one()
        if self.splendid_is_external_cost:
            return self.splendid_external_cost or 0.0
        return super()._compute_current_operation_cost()

    def _get_current_theorical_operation_cost(self, without_employee_cost=False):
        self.ensure_one()
        if self.splendid_is_external_cost:
            return self.splendid_external_cost or 0.0
        return super()._get_current_theorical_operation_cost(
            without_employee_cost=without_employee_cost
        )

    def _create_or_update_analytic_entry(self):
        """Keep analytic costing fixed as well when mrp_account is installed.

        Standard Odoo creates Work Center analytic cost using hours * hourly rate.
        Our technical Splendid Work Centers deliberately have hourly cost = 0, so
        leaving the standard method unchanged would show zero analytic cost even
        though the Work Order correctly contributes a fixed manufacturing cost.

        For Splendid external-cost Work Orders we feed the exact fixed amount into
        Odoo's standard analytic-distribution helper.  Unit amount is zero because
        the source is a fixed charge, not billable/consumed hours.
        """
        splendid_workorders = self.filtered("splendid_is_external_cost")
        normal_workorders = self - splendid_workorders

        if normal_workorders:
            super(MrpWorkorder, normal_workorders)._create_or_update_analytic_entry()

        for workorder in splendid_workorders:
            if not workorder.id:
                continue
            value = -(workorder.splendid_external_cost or 0.0)
            workorder._create_or_update_analytic_entry_for_record(value, 0.0)
