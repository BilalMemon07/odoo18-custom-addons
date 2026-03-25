# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class PublisherWarrantyContract(models.AbstractModel):
    _inherit = "publisher_warranty.contract"

    @api.model
    def _get_message(self):
        return True

    @api.model
    def _get_sys_logs(self):
        return True

    def update_notification(self, cron_mode=True):
        return True

