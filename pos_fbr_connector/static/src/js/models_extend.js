/** @odoo-module **/

import { Order } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";

patch(Order.prototype, {
    setup() {
        super.setup(...arguments);
        this.invoice_no = this.invoice_no || false;
        this.qr_image = this.qr_image || false;
        this.is_registered = this.is_registered || false;
    },

    export_as_JSON() {
        const json = super.export_as_JSON(...arguments);
        json.invoice_no = this.invoice_no || false;
        json.qr_image = this.qr_image || false;
        json.is_registered = this.is_registered || false;
        return json;
    },

    init_from_JSON(json) {
        super.init_from_JSON(...arguments);

        // Important for receipt re-print: when an old POS order is loaded
        // from the backend, the FBR invoice number comes in `json`.
        // Do not read it from `this.pos.get_order()` because that is only
        // the currently active order and can be empty/different.
        this.invoice_no = json.invoice_no || this.invoice_no || false;
        this.qr_image = json.qr_image || this.qr_image || false;
        this.is_registered = json.is_registered || this.is_registered || false;
    },

    export_for_printing() {
        const result = super.export_for_printing(...arguments);
        result.client = this.get_partner();
        result.invoice_no = this.invoice_no || false;
        result.qr_image = this.qr_image || false;
        result.is_registered = this.is_registered || false;
        return result;
    },
});
