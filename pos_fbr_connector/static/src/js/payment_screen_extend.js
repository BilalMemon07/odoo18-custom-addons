/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { ConnectionLostError, RPCError } from "@web/core/network/rpc";
import { serializeDateTime } from "@web/core/l10n/dates";
import { handleRPCError } from "@point_of_sale/app/errors/error_handlers";

patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.orm = useService("orm");
    },

    async _finalizeValidation() {
        if (this.currentOrder.is_paid_with_cash() || this.currentOrder.get_change()) {
            this.hardwareProxy.openCashbox();
        }

        this.currentOrder.date_order = serializeDateTime(luxon.DateTime.now());

        for (const line of this.paymentLines) {
            if (!line.amount === 0) {
                this.currentOrder.remove_paymentline(line);
            }
        }

        this.pos.addPendingOrder([this.currentOrder.id]);
        this.currentOrder.state = "paid";

        this.env.services.ui.block();

        let syncOrderResult;

        try {
            // 1. Save / sync order to backend
            syncOrderResult = await this.pos.syncAllOrders({ throw: true });

            if (!syncOrderResult) {
                return;
            }

            // 2. Download invoice if needed
            if (this.shouldDownloadInvoice() && this.currentOrder.is_to_invoice()) {
                if (this.currentOrder.raw.account_move) {
                    await this.invoiceService.downloadPdf(this.currentOrder.raw.account_move);
                } else {
                    throw {
                        code: 401,
                        message: "Backend Invoice",
                        data: { order: this.currentOrder },
                    };
                }
            }

            // 3. Send order data to FBR
            const fbrData = await this.orm.call(
                "pos.order",
                "data_to_fbr",
                [this.currentOrder.id]
            );

            if (fbrData) {
                console.log("FBR Data:", fbrData);

                this.currentOrder.invoice_no = fbrData[0];
                this.currentOrder.qr_image = fbrData[1];

                if (this.currentOrder.raw) {
                    this.currentOrder.raw.invoice_no = fbrData[0];
                    this.currentOrder.raw.qr_image = fbrData[1];
                }
            }

        } catch (error) {
            if (error instanceof ConnectionLostError) {
                this.afterOrderValidation();
                Promise.reject(error);
            } else if (error instanceof RPCError) {
                this.currentOrder.state = "draft";
                handleRPCError(error, this.dialog);
            } else {
                throw error;
            }
            return error;
        } finally {
            this.env.services.ui.unblock();
        }

        // 4. Post push process
        const postPushOrders = syncOrderResult.filter((order) =>
            order.wait_for_push_order()
        );

        if (postPushOrders.length > 0) {
            await this.postPushOrderResolve(postPushOrders.map((order) => order.id));
        }

        await this.afterOrderValidation(
            !!syncOrderResult && syncOrderResult.length > 0
        );
    },
});