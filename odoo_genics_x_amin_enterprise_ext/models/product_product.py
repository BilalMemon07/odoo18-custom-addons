from odoo import models, fields, api
from datetime import time, timedelta
from odoo.tools import float_round

class ProductProduct(models.Model):
    _inherit = "product.product"
    def _compute_sales_count(self):
            r = {}
            self.sales_count = 0
            if not self.env.user.has_group('sales_team.group_sale_salesman'):
                return r
            date_from = fields.Datetime.to_string(fields.datetime.combine(fields.datetime.now() - timedelta(days=365),
                                                                        time.min))

            done_states = self.env['sale.report']._get_done_states()

            domain = [
                ('state', 'in', done_states),
                ('product_id', 'in', self.ids),
                ('date', '>=', date_from),
            ]
            for product, product_uom_qty in self.env['sale.report']._read_group(domain, ['product_id'], ['qty_delivered:sum']):
                r[product.id] = product_uom_qty
            for product in self:
                if not product.id:
                    product.sales_count = 0.0
                    continue
                product.sales_count = float_round(r.get(product.id, 0), precision_rounding=product.uom_id.rounding)
            return r
