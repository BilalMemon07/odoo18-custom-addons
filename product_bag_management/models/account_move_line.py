from odoo import models, fields, api

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    bag_qty = fields.Float(string="Bags", compute="_compute_bags", store=True)

    @api.depends('product_id', 'quantity')
    def _compute_bags(self):
        for line in self:
            bag = 0
            config = self.env['product.bag.config'].search([
                ('product_id', '=', line.product_id.id)
            ], limit=1)

            if config and config.weight_per_bag > 0:
                if line.product_uom_id == config.uom_id:
                    bag = line.quantity / config.weight_per_bag

            line.bag_qty = bag