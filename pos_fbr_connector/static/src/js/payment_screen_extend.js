/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { OfflineErrorPopup } from "@point_of_sale/app/errors/popups/offline_error_popup";
import { ConfirmPopup } from "@point_of_sale/app/utils/confirm_popup/confirm_popup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { _t } from "@web/core/l10n/translation";
import { ConnectionLostError } from "@web/core/network/rpc_service";

patch(PaymentScreen.prototype, {
    setup() {
        super.setup();
        this.orm = useService("orm")
    },
    async _finalizeValidation() {
        console.log('89');
        const self = this;
//        if ((this.currentOrder.is_paid_with_cash() || this.currentOrder.get_change()) && this.pos.config.iface_cashdrawer && this.env.proxy && this.env.proxy.printer) {
//            this.env.proxy.printer.open_cashbox();
//            console.log('8932');
//        }
        if (this.currentOrder.is_paid_with_cash() || this.currentOrder.get_change()) {
            this.hardwareProxy.openCashbox();
            }

        this.currentOrder.date_order = luxon.DateTime.now();
        for (const line of this.paymentLines) {
            if (!line.amount === 0) {
                this.currentOrder.remove_paymentline(line);
            }
        }
        this.currentOrder.finalized = true;

        this.env.services.ui.block();
        let syncOrderResult;
        try {
             // 1. Save order to server.
            syncOrderResult = await this.pos.push_single_order(this.currentOrder);
            if (!syncOrderResult) {
                return;
            }
            // 2. Invoice.
            if (this.shouldDownloadInvoice() && this.currentOrder.is_to_invoice()) {
                if (syncOrderResult[0]?.account_move) {
                    await this.report.doAction("account.account_invoices", [
                        syncOrderResult[0].account_move,
                    ]);
                } else {
                    throw {
                        code: 401,
                        message: "Backend Invoice",
                        data: { order: this.currentOrder },
                    };
                }
            }
            const pos_order = self.pos.get_order();
            console.log("pos order here === ");
            console.log("pos order here ===pos_order.uid  ", pos_order);
            const fbr_data = await this.orm.call(
                'pos.order',
                'data_to_fbr',
                [pos_order.export_as_JSON()]
            );
            if (fbr_data) {
                console.log(fbr_data, 'tashi');
                self.currentOrder.invoice_no = fbr_data[0];
                self.currentOrder.qr_image = fbr_data[1];
            }
        } catch (error) {
            if (error instanceof ConnectionLostError) {
                this.pos.showScreen(this.nextScreen);
                Promise.reject(error);
                return error;
            } else {
                throw error;
            }
        } finally {
            this.env.services.ui.unblock();
        }
        this.pos.showScreen(this.nextScreen);
    }
});

//registry.Component.extend(PaymentScreen, 'pos_fbr_connector.PaymentScreen');
//
//export default PaymentScreen;
