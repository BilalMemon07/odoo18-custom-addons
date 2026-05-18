/** @odoo-module **/

import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import { patch } from "@web/core/utils/patch";
import { useState, onWillRender } from "@odoo/owl";

patch(OrderReceipt.prototype, {
    setup() {
        super.setup(...arguments);
        this.state = useState({
            invoice_no: this.props.data.invoice_no || false,
            qr_image: this.props.data.qr_image || false,
        });

        onWillRender(() => {
            this.state.invoice_no = this.props.data.invoice_no || false;
            this.state.qr_image = this.props.data.qr_image || false;
        });
    },
});
