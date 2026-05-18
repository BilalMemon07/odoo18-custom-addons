// odoo.define('pos_fbr_connector.models', function (require) {
// "use strict";

//     var { Order } = require('point_of_sale.models');
//     var Registries = require('point_of_sale.Registries');

//     const CustomOrder = (Order) => class CustomOrder extends Order {
//         constructor(obj, options) {
//             super(...arguments);

//             this.invoice_no = '';
//             this.qr_image = '';
//         }
//         init_from_JSON(json) {
//             super.init_from_JSON(...arguments);
//             console.log("json.invoice_no === ", json.invoice_no)
//             this.invoice_no = json.invoice_no
//             this.qr_image = json.qr_image
//         }
//         export_as_JSON() {
//             const json = super.export_as_JSON(...arguments);
//             console.log("export_as_JSON.invoice_no === ", json.invoice_no)
//             json.invoice_no = this.invoice_no;
//             json.qr_image = this.qr_image;
//             return json;
//         }
//         export_for_printing() {
//             var result = super.export_for_printing(...arguments);
//             result.client = this.get_partner();
//             console.log("export_for_printing.invoice_no === ", json.invoice_no)
//             result.invoice_no = this.invoice_no
//             result.qr_image = this.qr_image
//             return result;
//             }

//         }
//         Registries.Model.extend(Order, CustomOrder);
//     });



// odoo.define('pos_fbr_connector.PaymentScreen', function (require) {
//     'use strict';

//     const PaymentScreen = require('point_of_sale.PaymentScreen');
//     const Registries = require('point_of_sale.Registries');
//     const web_rpc = require('web.rpc');
//     const PosExtPaymentScreen = (PaymentScreen_) =>
//         class extends PaymentScreen_ {
//             async _finalizeValidation() {
//             console.log('89');
//             var self = this
//             if ((this.currentOrder.is_paid_with_cash() || this.currentOrder.get_change()) && this.pos.config.iface_cashdrawer && this.env.proxy && this.env.proxy.printer) {
//                 this.env.proxy.printer.open_cashbox();
//                 console.log('8932');
//             }

//             this.currentOrder.initialize_validation_date();
//             for (let line of this.paymentLines) {
//                 if (!line.amount === 0) {
//                     console.log('8943422342');
//                      this.currentOrder.remove_paymentline(line);
//                 }
//             }
//             this.currentOrder.finalized = true;

//             let syncOrderResult, hasError;

//             try {
//               console.log('324234242424');
//                 // 1. Save order to server.
//                 syncOrderResult = await this.env.pos.push_single_order(this.currentOrder);

//                 // 2. Invoice.
//                 if (this.shouldDownloadInvoice() && this.currentOrder.is_to_invoice()) {
//                     if (syncOrderResult.length) {
//                         console.log('89r524242443422342');
//                         await this.env.legacyActionManager.do_action('account.account_invoices', {
//                             additional_context: {
//                                 active_ids: [syncOrderResult[0].account_move],
//                             },
//                         });
//                     } else {
//                         throw { code: 401, message: 'Backend Invoice', data: { order: this.currentOrder } };
//                     }
//                 }

//                 // 3. Post process.
//                 if (syncOrderResult.length && this.currentOrder.wait_for_push_order()) {
//                     const postPushResult = await this._postPushOrderResolve(
//                         this.currentOrder,
//                         syncOrderResult.map((res) => res.id)
//                     );
//                     if (!postPushResult) {
//                         this.showPopup('ErrorPopup', {
//                             title: this.env._t('Error: no internet connection.'),
//                             body: this.env._t('Some, if not all, post-processing after syncing order failed.'),
//                         });
//                     }
//                 }
//                 var pos_order = this.currentOrder;
//                 console.log("pos order here === ")
//                 await web_rpc.query({
//                     model: 'pos.order',
//                     method: 'data_to_fbr',
//                     args: [[pos_order.uid],[pos_order.export_as_JSON()]],
//                 })
//                 .then(function(data){
//                 	if(data && data[0]){
//                 	    console.log(data[1],'tashi');
//                 		self.currentOrder.invoice_no = data[0];
//                 		self.currentOrder.qr_image = data[1];
//                 	}
//                 });
//             } catch (error) {
//                 if (error.code == 700 || error.code == 701)
//                     this.error = true;

//                 if ('code' in error) {
//                     // We started putting `code` in the rejected object for invoicing error.
//                     // We can continue with that convention such that when the error has `code`,
//                     // then it is an error when invoicing. Besides, _handlePushOrderError was
//                     // introduce to handle invoicing error logic.
//                     await this._handlePushOrderError(error);
//                 } else {
//                     // We don't block for connection error. But we rethrow for any other errors.
//                     if (isConnectionError(error)) {
//                         this.showPopup('OfflineErrorPopup', {
//                             title: this.env._t('Connection Error'),
//                             body: this.env._t('Order is not synced. Check your internet connection'),
//                         });
//                     } else {
//                         throw error;
//                     }
//                 }
//             } finally {
//                 // Always show the next screen regardless of error since pos has to
//                 // continue working even offline.
//                 this.showScreen(this.nextScreen);
//                 // Remove the order from the local storage so that when we refresh the page, the order
//                 // won't be there
//                 this.env.pos.db.remove_unpaid_order(this.currentOrder);

//                 // Ask the user to sync the remaining unsynced orders.
//                 if (!hasError && syncOrderResult && this.env.pos.db.get_orders().length) {
//                     const { confirmed } = await this.showPopup('ConfirmPopup', {
//                         title: this.env._t('Remaining unsynced orders'),
//                         body: this.env._t(
//                             'There are unsynced orders. Do you want to sync these orders?'
//                         ),
//                     });
//                     if (confirmed) {
//                         // NOTE: Not yet sure if this should be awaited or not.
//                         // If awaited, some operations like changing screen
//                         // might not work.
//                         this.env.pos.push_orders();
//                     }
//                 }
//             }
//         }
//           };

// Registries.Component.extend(PaymentScreen, PosExtPaymentScreen);

// return PaymentScreen;
// });
