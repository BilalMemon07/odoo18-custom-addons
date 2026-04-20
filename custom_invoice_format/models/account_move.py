from odoo import models, fields, api

class AccountMove(models.Model):
    _inherit = 'account.move'

    invoice_type = fields.Selection(
        related='partner_id.invoice_type',
        store=True
    )


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    ctn_size = fields.Float(related='product_id.product_tmpl_id.ctn_size', store=True)
    grams = fields.Float(related='product_id.product_tmpl_id.grams', store=True)
    trade_price = fields.Float(related='product_id.product_tmpl_id.trade_price', store=True)
    msrp = fields.Float(related='product_id.product_tmpl_id.msrp', store=True)

    ctn_qty = fields.Float(compute="_compute_qty", store=True)
    pcs_qty = fields.Float(compute="_compute_qty", store=True)
    kgs_qty = fields.Float(compute="_compute_qty", store=True)

    gross_amount = fields.Float(compute="_compute_amounts", store=True)
    net_amount = fields.Float(compute="_compute_amounts", store=True)

    distributor_margin = fields.Float(compute="_compute_margin", store=True)

    @api.depends('quantity', 'ctn_size', 'grams')
    def _compute_qty(self):
        for line in self:
            line.ctn_qty = line.quantity
            line.pcs_qty = line.quantity * line.ctn_size
            line.kgs_qty = (line.pcs_qty * line.grams) / 1000 if line.grams else 0

    @api.depends('price_unit', 'quantity', 'tax_ids')
    def _compute_amounts(self):
        for line in self:
            line.gross_amount = line.price_unit * line.quantity
            line.net_amount = line.price_total

    @api.depends('price_unit', 'trade_price')
    def _compute_margin(self):
        for line in self:
            if line.trade_price:
                line.distributor_margin = ((line.price_unit - line.trade_price) / line.trade_price) * 100
            else:
                line.distributor_margin = 0