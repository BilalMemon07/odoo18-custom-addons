from odoo import models, fields, api

class StockQuant(models.Model):
    _inherit = 'stock.quant'

    bag_qty = fields.Float(
        string="Bags",
        compute="_compute_bag_qty",
        store=True
    )

    @api.depends('product_id', 'quantity')
    def _compute_bag_qty(self):
        for quant in self:
            bag = 0

            config = self.env['product.bag.config'].search([
                ('product_id', '=', quant.product_id.id)
            ], limit=1)

            if config and config.weight_per_bag > 0:
                bag = quant.quantity / config.weight_per_bag

            quant.bag_qty = bag