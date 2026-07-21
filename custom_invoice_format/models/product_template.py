from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    ctn_size = fields.Float(string='Carton Size')
    grams = fields.Float(string='Grams')
    trade_price = fields.Float(string='Trade Price')
    msrp = fields.Float(string='MSRP')

    show_custom_invoice_fields = fields.Boolean(
        string='Show Custom Invoice Fields',
        compute='_compute_show_custom_invoice_fields',
    )

    @api.depends_context('company')
    def _compute_show_custom_invoice_fields(self):
        """Control product-field visibility from the currently active company."""
        enabled = bool(self.env.company.use_custom_invoice)
        for product in self:
            product.show_custom_invoice_fields = enabled
