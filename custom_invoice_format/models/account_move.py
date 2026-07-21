from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    invoice_type = fields.Selection(
        related='partner_id.invoice_type',
        store=True,
        readonly=True,
    )


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    ctn_size = fields.Float(
        related='product_id.product_tmpl_id.ctn_size',
        store=True,
        readonly=True,
    )
    grams = fields.Float(
        related='product_id.product_tmpl_id.grams',
        store=True,
        readonly=True,
    )
    trade_price = fields.Float(
        related='product_id.product_tmpl_id.trade_price',
        store=True,
        readonly=True,
    )
    msrp = fields.Float(
        related='product_id.product_tmpl_id.msrp',
        store=True,
        readonly=True,
    )

    ctn_qty = fields.Float(compute='_compute_custom_quantities', store=True, digits='Product Unit')
    pcs_qty = fields.Float(compute='_compute_custom_quantities', store=True, digits='Product Unit')
    kgs_qty = fields.Float(compute='_compute_custom_quantities', store=True, digits=(16, 3))

    gross_amount = fields.Monetary(
        currency_field='currency_id',
        compute='_compute_custom_amounts',
        store=True,
    )
    net_amount = fields.Monetary(
        currency_field='currency_id',
        compute='_compute_custom_amounts',
        store=True,
    )
    distributor_margin = fields.Float(compute='_compute_margin', store=True, digits=(16, 2))

    @api.depends('quantity', 'ctn_size', 'grams')
    def _compute_custom_quantities(self):
        for line in self:
            line.ctn_qty = line.quantity
            line.pcs_qty = line.quantity * line.ctn_size
            line.kgs_qty = (
                (line.pcs_qty * line.grams) / 1000.0
                if line.grams
                else 0.0
            )

    @api.depends('price_unit', 'quantity', 'discount', 'price_total')
    def _compute_custom_amounts(self):
        for line in self:
            line.gross_amount = line.price_unit * line.quantity
            line.net_amount = line.price_total

    @api.depends('price_unit', 'trade_price')
    def _compute_margin(self):
        for line in self:
            line.distributor_margin = (
                ((line.price_unit - line.trade_price) / line.trade_price) * 100.0
                if line.trade_price
                else 0.0
            )
