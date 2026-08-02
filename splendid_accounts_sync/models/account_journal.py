# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    splendid_bank_account_id = fields.Char(index=True, copy=False)
    splendid_bank_account_account_id = fields.Char(string="Splendid Linked Account ID", index=True, copy=False)
    splendid_is_imported = fields.Boolean(copy=False)
