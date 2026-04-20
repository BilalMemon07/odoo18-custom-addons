from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    use_custom_invoice = fields.Boolean("Use Custom Invoice")