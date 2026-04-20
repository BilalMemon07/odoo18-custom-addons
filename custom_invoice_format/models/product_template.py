from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    ctn_size = fields.Float("Carton Size")
    grams = fields.Float("Grams")
    trade_price = fields.Float("Trade Price")
    msrp = fields.Float("MSRP")