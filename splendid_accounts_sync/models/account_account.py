# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountAccount(models.Model):
    _inherit = "account.account"

    splendid_account_id = fields.Char(index=True, copy=False)
    splendid_is_imported = fields.Boolean(copy=False)
