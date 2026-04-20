from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    invoice_type = fields.Selection([
        ('official', 'Official'),
        ('unofficial', 'Unofficial'),
    ], string="Invoice Type", default='official')