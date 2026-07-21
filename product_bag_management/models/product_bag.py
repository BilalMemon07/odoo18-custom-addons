from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ProductBag(models.Model):
    _name = 'product.bag.config'
    _description = 'Product Bag Configuration'
    _rec_name = 'product_id'

    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Product',
        required=True,
        check_company=True,
        index=True,
    )
    weight_per_bag = fields.Float(
        string='Weight per Bag',
        required=True,
        digits='Product Unit of Measure',
    )
    uom_id = fields.Many2one(
        comodel_name='uom.uom',
        string='Weight UoM',
        required=True,
        help='Use KG here when invoice and stock quantities must be handled in kilograms.',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        default=lambda self: self.env.company,
        index=True,
        help='Leave empty to use this configuration as a fallback for all companies.',
    )

    _sql_constraints = [
        (
            'positive_weight_per_bag',
            'CHECK(weight_per_bag > 0)',
            'Weight per bag must be greater than zero.',
        ),
    ]

    @api.constrains('product_id', 'uom_id')
    def _check_uom_category(self):
        for config in self:
            if (
                config.product_id
                and config.uom_id
                and config.product_id.uom_id.category_id != config.uom_id.category_id
            ):
                raise ValidationError(_(
                    'The bag Weight UoM must belong to the same UoM category as '
                    'the product unit of measure.'
                ))
