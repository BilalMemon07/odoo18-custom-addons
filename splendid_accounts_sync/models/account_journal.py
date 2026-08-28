# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    splendid_bank_account_id = fields.Char(index=True, copy=False)
    splendid_bank_account_account_id = fields.Char(string="Splendid Linked Account ID", index=True, copy=False)
    # Exact Splendid GL account used by payment payloads. This is separate from
    # splendid_bank_account_id because cash / suspense payment accounts are not
    # necessarily records from Splendid's BankAccounts master.
    splendid_payment_account_id = fields.Char(string="Splendid Payment Account ID", index=True, copy=False)
    splendid_is_imported = fields.Boolean(copy=False)
    splendid_is_cheque_journal = fields.Boolean(
        string="Splendid Cheque Journal",
        copy=False,
        index=True,
        help="Dedicated liquidity journal automatically used for Splendid paymentMode 20 (cheque) when no exact payment account is supplied.",
    )
