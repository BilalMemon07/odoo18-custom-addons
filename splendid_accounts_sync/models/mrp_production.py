# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    splendid_job_order_id = fields.Char(string="Splendid Job Order ID", index=True, copy=False)
    splendid_job_order_number = fields.Char(string="Splendid Job Order Number", index=True, copy=False)
    splendid_job_order_status = fields.Integer(string="Splendid Job Order Status", copy=False)
    splendid_actual_quantity_produced = fields.Float(string="Splendid Actual Quantity Produced", copy=False)
    splendid_is_imported = fields.Boolean(copy=False, index=True)
    splendid_raw_payload = fields.Json(copy=False)

    splendid_job_expense_ids = fields.One2many(
        "splendid.job.order.expense",
        "production_id",
        string="Splendid Job Order Expenses",
        copy=False,
    )
    splendid_job_expense_currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        readonly=True,
    )
    splendid_job_expense_total = fields.Monetary(
        string="External Job Expense Total",
        currency_field="splendid_job_expense_currency_id",
        compute="_compute_splendid_job_expense_amounts",
        store=True,
    )
    splendid_job_expense_unit_cost = fields.Monetary(
        string="External Job Expense / Unit",
        currency_field="splendid_job_expense_currency_id",
        compute="_compute_splendid_job_expense_amounts",
        store=True,
    )

    @api.depends("splendid_job_expense_ids.amount", "splendid_job_expense_ids.is_current", "product_qty")
    def _compute_splendid_job_expense_amounts(self):
        for production in self:
            total = sum(production.splendid_job_expense_ids.filtered("is_current").mapped("amount"))
            production.splendid_job_expense_total = total
            production.splendid_job_expense_unit_cost = total / production.product_qty if production.product_qty else 0.0


    def action_delete_splendid_manufacturing_orders(self):
        """Delete selected Splendid-imported MOs only when it is accounting/stock safe.

        This server-action helper is intentionally limited to Draft or Cancelled
        manufacturing orders. Confirmed/In Progress/Done MOs may already have
        reservations, stock moves, work-order costs or valuation/accounting
        entries, so deleting them here would be destructive.
        """
        if not self:
            return {"type": "ir.actions.client", "tag": "reload"}

        non_splendid = self.filtered(lambda production: not production.splendid_is_imported)
        if non_splendid:
            raise UserError(_(
                "This action only deletes Manufacturing Orders imported from Splendid. "
                "Remove non-Splendid orders from the selection and try again: %s"
            ) % ", ".join(non_splendid.mapped("display_name")[:10]))

        unsafe = self.filtered(lambda production: production.state not in ("draft", "cancel"))
        if unsafe:
            details = ", ".join(
                "%s [%s]" % (production.display_name, production.state)
                for production in unsafe[:10]
            )
            raise UserError(_(
                "Only Draft or Cancelled Splendid Manufacturing Orders can be deleted by this action. "
                "Confirmed/In Progress/Done orders are blocked to protect stock valuation and accounting. "
                "Blocked: %s"
            ) % details)

        # Job Order expense rows use ondelete='cascade', so they are removed with
        # the MO. Splendid sync-map rows may retain the old res_id, but the sync
        # resolver uses .exists(); on a future Job Order sync the MO is recreated
        # and the same mapping row is updated to the new record automatically.
        self.unlink()
        return {"type": "ir.actions.client", "tag": "reload"}
