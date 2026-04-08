from odoo import models, fields, api

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    bag_qty = fields.Float(string="Bags", compute="_compute_bags", store=True)

    @api.depends('product_id', 'product_qty')
    def _compute_bags(self):
        for line in self:
            bag = 0
            config = self.env['product.bag.config'].search([
                ('product_id', '=', line.product_id.id)
            ], limit=1)

            if config and config.weight_per_bag > 0:
                if line.product_uom == config.uom_id:
                    bag = line.product_qty / config.weight_per_bag

            line.bag_qty = bag