from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    company_use_custom_invoice = fields.Boolean(
        related='company_id.use_custom_invoice',
        readonly=True,
    )


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    bag_qty = fields.Float(
        string='Bags',
        compute='_compute_bag_values',
        inverse='_inverse_bag_qty',
        readonly=False,
        digits='Product Unit',
    )
    bag_weight_qty = fields.Float(
        string='Weight Quantity',
        compute='_compute_bag_values',
        digits='Product Unit',
    )
    bag_uom_id = fields.Many2one(
        comodel_name='uom.uom',
        string='Weight UoM',
        compute='_compute_bag_values',
    )

    def _get_bag_config(self):
        self.ensure_one()
        if not self.product_id:
            return self.env['product.bag.config']

        company = self.move_id.company_id or self.env.company
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
        'quantity',
        'product_uom_id',
        'move_id.company_id',
    )
    def _compute_bag_values(self):
        for line in self:
            line.bag_qty = 0.0
            line.bag_weight_qty = 0.0
            line.bag_uom_id = False

            config = line._get_bag_config()
            source_uom = line.product_uom_id or line.product_id.uom_id
            if not config or not source_uom or not config.weight_per_bag:
                continue

            weight_qty = source_uom._compute_quantity(
                line.quantity,
                config.uom_id,
                round=False,
            )
            line.bag_weight_qty = weight_qty
            line.bag_uom_id = config.uom_id
            line.bag_qty = weight_qty / config.weight_per_bag

    def _inverse_bag_qty(self):
        for line in self:
            company = line.move_id.company_id or self.env.company
            if company.use_custom_invoice or not line.product_id:
                continue

            config = line._get_bag_config()
            if not config:
                continue

            line.product_uom_id = config.uom_id
            line.quantity = line.bag_qty * config.weight_per_bag

    @api.onchange('product_id')
    def _onchange_product_id_use_bag_weight_uom(self):
        for line in self:
            company = line.move_id.company_id or self.env.company
            if company.use_custom_invoice:
                continue
            config = line._get_bag_config()
            if config:
                line.product_uom_id = config.uom_id
