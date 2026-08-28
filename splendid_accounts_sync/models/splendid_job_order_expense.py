# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import UserError


class SplendidJobOrderExpense(models.Model):
    _name = "splendid.job.order.expense"
    _description = "Splendid Job Order Expense"
    _order = "production_id, id"

    connection_id = fields.Many2one(
        "splendid.account.connection",
        required=True,
        ondelete="cascade",
        index=True,
    )
    production_id = fields.Many2one(
        "mrp.production",
        string="Manufacturing Order",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        related="production_id.company_id",
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    splendid_job_order_id = fields.Char(index=True, copy=False)
    splendid_job_order_number = fields.Char(index=True, copy=False)
    splendid_expense_id = fields.Char(string="Splendid Expense ID", index=True, copy=False)
    splendid_account_id = fields.Char(string="Splendid Account ID", index=True, copy=False)
    splendid_contact_id = fields.Char(string="Splendid Contact ID", index=True, copy=False)

    account_id = fields.Many2one(
        "account.account",
        string="Splendid Expense Account",
        check_company=True,
    )
    vendor_id = fields.Many2one(
        "res.partner",
        string="Vendor",
        domain="[('supplier_rank', '>', 0)]",
    )
    description = fields.Char()
    amount = fields.Monetary(required=True)
    vendor_bill_id = fields.Many2one(
        "account.move",
        string="Vendor Bill / Refund",
        readonly=True,
        copy=False,
        domain="[('move_type', 'in', ('in_invoice', 'in_refund'))]",
    )
    journal_entry_id = fields.Many2one(
        "account.move",
        string="Journal Entry",
        readonly=True,
        copy=False,
        domain="[('move_type', '=', 'entry')]",
    )
    accounting_state = fields.Selection(
        [
            ("not_required", "Work Order Cost / No Separate JE"),
            ("ready", "Ready for Journal Entry"),
            ("draft", "Draft Journal Entry"),
            ("posted", "Journal Entry Posted"),
            ("review", "Accounting Review Required"),
        ],
        default="not_required",
        copy=False,
        index=True,
    )
    billing_state = fields.Selection(
        [
            ("not_required", "Cost Only"),
            ("ready", "Ready for Vendor Bill"),
            ("review", "Vendor Review Required"),
            ("billed", "Vendor Bill Created"),
        ],
        default="not_required",
        copy=False,
        index=True,
    )
    review_note = fields.Char(copy=False)
    is_current = fields.Boolean(string="Present in Latest Splendid Payload", default=True, copy=False, index=True)
    splendid_raw_payload = fields.Json(copy=False)
    operation_id = fields.Many2one(
        "mrp.routing.workcenter",
        string="Splendid Cost Operation",
        readonly=True,
        copy=False,
        ondelete="set null",
    )
    workorder_id = fields.Many2one(
        "mrp.workorder",
        string="Splendid Cost Work Order",
        readonly=True,
        copy=False,
        ondelete="set null",
    )

    _sql_constraints = [
        (
            "splendid_job_order_expense_unique",
            "unique(connection_id, splendid_job_order_id, splendid_expense_id)",
            "The same Splendid Job Order expense cannot be imported twice for one connection.",
        )
    ]

    def action_create_journal_entry(self):
        raise UserError(_(
            "Separate Job Order expense Journal Entries have been removed. "
            "Splendid jobOrderExpenses are now applied through Manufacturing Work Orders and Odoo's standard Work Center costing."
        ))

    # Backward-compatible RPC/button name from older versions. No bill or
    # separate journal entry is created in v29.
    def action_create_vendor_bill(self):
        return self.action_create_journal_entry()
