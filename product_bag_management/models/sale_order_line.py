from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    company_use_custom_invoice = fields.Boolean(
        related='company_id.use_custom_invoice',
        readonly=True,
    )


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    bag_qty = fields.Float(
        string='Bags',
        compute='_compute_bag_qty',
        inverse='_inverse_bag_qty',
        readonly=False,
        digits='Product Unit',
    )

    def _get_bag_config(self):
        self.ensure_one()
        if not self.product_id:
            return self.env['product.bag.config']

        company = self.order_id.company_id or self.env.company
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

    @api.depends(
        'product_id',
        'product_uom_qty',
        'product_uom',
        'order_id.company_id',
    )
    def _compute_bag_qty(self):
        for line in self:
            line.bag_qty = 0.0
            config = line._get_bag_config()
            source_uom = line.product_uom or line.product_id.uom_id
            if not config or not source_uom or not config.weight_per_bag:
                continue

            weight_qty = source_uom._compute_quantity(
                line.product_uom_qty,
                config.uom_id,
                round=False,
            )
            line.bag_qty = weight_qty / config.weight_per_bag

    def _inverse_bag_qty(self):
        for line in self:
            company = line.order_id.company_id or self.env.company
            if company.use_custom_invoice or not line.product_id:
                continue

            config = line._get_bag_config()
            if not config:
                continue

            # In non-custom-invoice companies, a bag entry is converted to the
            # configured weight UoM (normally KG). The invoice then inherits the
            # same weight quantity and UoM from the sale order line.
            target_weight_qty = line.bag_qty * config.weight_per_bag
            current_uom = line.product_uom_id or line.product_id.uom_id
            allowed_uoms = line.allowed_uom_ids or line.product_id.uom_id
            if config.uom_id in allowed_uoms:
                line.product_uom_id = config.uom_id
                line.product_uom_qty = target_weight_qty
            elif current_uom:
                line.product_uom_qty = config.uom_id._compute_quantity(
                    target_weight_qty,
                    current_uom,
                    round=False,
                )
