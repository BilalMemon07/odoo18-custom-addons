from odoo import api, fields, models


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    bag_qty = fields.Float(
        string='Bags',
        compute='_compute_bag_qty',
        digits='Product Unit',
    )

    def _get_bag_config(self):
        self.ensure_one()
        if not self.product_id:
            return self.env['product.bag.config']

        company = self.company_id or self.env.company
        config_model = self.env['product.bag.config']
        return (
            config_model.search([
                ('product_id', '=', self.product_id.id),
                ('company_id', '=', company.id),
            ], limit=1)
            or config_model.search([
                ('product_id', '=', self.product_id.id),
                ('company_id', '=', False),
            ], limit=1)
        )

    @api.depends('product_id', 'quantity', 'company_id')
    def _compute_bag_qty(self):
        for quant in self:
            quant.bag_qty = 0.0
            config = quant._get_bag_config()
            source_uom = quant.product_id.uom_id
            if not config or not source_uom or not config.weight_per_bag:
                continue

            weight_qty = source_uom._compute_quantity(
                quant.quantity,
                config.uom_id,
                round=False,
            )
            quant.bag_qty = weight_qty / config.weight_per_bag
