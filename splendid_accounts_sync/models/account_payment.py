# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    splendid_customer_payment_id = fields.Char(index=True, copy=False)
    splendid_customer_refund_id = fields.Char(index=True, copy=False)
    splendid_vendor_payment_id = fields.Char(index=True, copy=False)
    splendid_is_imported = fields.Boolean(copy=False)
    splendid_raw_payload = fields.Json(copy=False)
