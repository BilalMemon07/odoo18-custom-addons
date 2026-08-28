# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountAccount(models.Model):
    _inherit = "account.account"

    splendid_account_id = fields.Char(index=True, copy=False)
    splendid_is_imported = fields.Boolean(copy=False)
    splendid_is_cheque_clearing = fields.Boolean(
        string="Splendid Cheque Clearing Account",
        copy=False,
        index=True,
        help="Dedicated liquidity account used by the automatically created Splendid Cheque journal.",
    )
    splendid_job_expense_vendor_id = fields.Many2one(
        "res.partner",
        string="Default Vendor for Job Order Expenses",
        domain="[('supplier_rank', '>', 0)]",
        help="Fallback vendor used for Splendid Job Order expenses when Splendid does not provide contactId.",
    )
