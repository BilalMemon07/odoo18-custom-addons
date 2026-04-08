from odoo import models, fields

class ProductBag(models.Model):
    _name = 'product.bag.config'
    _description = 'Product Bag Configuration'

    product_id = fields.Many2one('product.product', required=True)
    weight_per_bag = fields.Float(string="Weight per Bag", required=True)
    uom_id = fields.Many2one('uom.uom', string="UOM", required=True)