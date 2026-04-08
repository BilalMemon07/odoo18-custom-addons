from odoo import models, fields, api

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    bag_qty = fields.Float(string="Bags", compute="_compute_bag_qty", readonly=False, store=True, inverse="_inverse_bag_qty",)
    bag_input = fields.Float(string="Bags (Manual)")

    @api.depends('product_id', 'product_uom_qty')
    def _compute_bag_qty(self):
        for line in self:
            bag = 0
            config = self.env['product.bag.config'].search([
                ('product_id', '=', line.product_id.id)
            ], limit=1)

            if config and config.weight_per_bag > 0:
                bag = line.product_uom_qty / config.weight_per_bag

            line.bag_qty = bag

    def _inverse_bag_qty(self):
        for line in self:
            if not line.product_id or not line.bag_qty:
                continue

            config = self.env['product.bag.config'].search([
                ('product_id', '=', line.product_id.id)
            ], limit=1)

            if config and config.weight_per_bag > 0:
                # Bags → KG
                line.product_uom_qty = line.bag_qty * config.weight_per_bag