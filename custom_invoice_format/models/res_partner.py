from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    invoice_type = fields.Selection(
        selection=[
            ('official', 'Official'),
            ('unofficial', 'Unofficial'),
        ],
        string='Invoice Type',
        default='official',
    )

    show_custom_invoice_fields = fields.Boolean(
        string='Show Custom Invoice Fields',
        compute='_compute_show_custom_invoice_fields',
    )

    @api.depends_context('company')
    def _compute_show_custom_invoice_fields(self):
        enabled = bool(self.env.company.use_custom_invoice)
        for partner in self:
            partner.show_custom_invoice_fields = enabled
