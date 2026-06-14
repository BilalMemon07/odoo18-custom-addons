# -*- coding: utf-8 -*-
# Copyright (C) Cybat.

import base64
import json
import logging
import traceback
from io import BytesIO

import qrcode
import requests

from odoo import api, fields, models
from odoo.exceptions import ValidationError,UserError


import ssl
import urllib3
# from urllib3.util import create_urllib3_context

_logger = logging.getLogger(__name__)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

timeout = urllib3.Timeout(connect=5.0, read=245.0)

http = urllib3.PoolManager(
    cert_reqs='CERT_NONE',
    assert_hostname=False,
    timeout=timeout,
)

class PosConfig(models.Model):
    _inherit = 'pos.config'

    pos_id = fields.Char("POSID",required=1)
    auth_header = fields.Char("FBR Header Authorization",required=1)
    post_data = fields.Boolean()
    fbr_url = fields.Char('FBR Url',required=True, default='https://gw.fbr.gov.pk/imsp/v1/api/Live/PostData')
    allow_fbr_charges = fields.Boolean('Allow FBR Charges')
    service_product_id = fields.Many2one('product.product', string='FBR FEE',
                                         domain="[('available_in_pos', '=', True),"
                                                "('sale_ok', '=', True), ('type', '=', 'service'),('is_fbr_fee','=',True)]")

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    prod_pct_code = fields.Char("PCT Code", required=True)
    is_fbr_fee = fields.Boolean('Is FBR FEE?')
    un_registered = fields.Boolean('Is Un Registered?')

    @api.constrains('is_fbr_fee')
    def check_is_fbr_fee(self):
        product = self.env['product.template'].search([('is_fbr_fee','=',True)])
        if product.__len__()> 1:
            raise ValidationError('FBR FEE product already exists!')


class PosOrder(models.Model):
    _inherit = 'pos.order'

    invoice_no = fields.Char("FBR Invoice Number")
    response = fields.Text("FBR Response")
    is_registered = fields.Boolean("Post Successfully ?")
    reference = fields.Char(string='Receipt Reference', readonly=True)
    is_returned = fields.Boolean("Is Returned ?")
    return_invoice_number = fields.Char("FBR Return Invoice Number")
    qr_image = fields.Binary("QR Code", compute='_generate_qr_code')

    def _generate_qr_code(self):
        for order in self:
            if order.invoice_no:
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=20,
                    border=4,
                )
                qr.add_data(order.invoice_no)
                qr.make(fit=True)
                img = qr.make_image()
                buffer = BytesIO()
                img.save(buffer, format="PNG")
                order.qr_image = base64.b64encode(buffer.getvalue())
            else:
                order.qr_image = False

    @api.model
    def data_to_fbr(self, order_id):
        _logger.info("========== FBR START ==========")
        _logger.info("FBR received order_id: %s | type: %s", order_id, type(order_id))

        invoice_no = ''
        qrcode_img = ''

        order = self.sudo().browse(order_id).exists()
        _logger.info("FBR order found: %s", bool(order))

        if not order:
            _logger.warning("FBR stopped: No pos.order found for ID %s", order_id)
            return [invoice_no, self._normalize_fbr_qr_value(qrcode_img)]

        session = order.session_id
        config = session.config_id

        _logger.info(
            "FBR order info | id=%s | name=%s | pos_reference=%s | session=%s | config=%s",
            order.id, order.name, order.pos_reference, session.name, config.display_name
        )

        _logger.info(
            "FBR config | post_data=%s | url=%s | pos_id=%s | has_auth_header=%s",
            config.post_data, config.fbr_url, config.pos_id, bool(config.auth_header)
        )

        if not config.post_data:
            _logger.warning("FBR stopped: post_data is disabled on POS config %s", config.display_name)
            _logger.info("========== FBR END ==========")
            return [invoice_no, self._normalize_fbr_qr_value(qrcode_img)]

        try:
            url = config.fbr_url
            header = {
                "Content-Type": "application/json",
                "Authorization": "Bearer " + (config.auth_header or ""),
            }

            is_refund = order.amount_total < 0

            _logger.info(
                "FBR totals | amount_total=%s | amount_tax=%s | is_refund=%s | lines=%s",
                order.amount_total, order.amount_tax, is_refund, len(order.lines)
            )

            order_dict = {
                "InvoiceNumber": "",
                "USIN": "USIN0",
                "DateTime": fields.Datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "TotalBillAmount": abs(order.amount_total),
                "TotalSaleValue": abs(order.amount_total) - abs(order.amount_tax),
                "TotalTaxCharged": abs(order.amount_tax),
                "PaymentMode": 1,
                "InvoiceType": 3 if is_refund else 1,
                "POSID": config.pos_id,
            }

            if order.partner_id:
                _logger.info(
                    "FBR buyer | partner_id=%s | name=%s | mobile=%s | vat=%s",
                    order.partner_id.id,
                    order.partner_id.name,
                    order.partner_id.mobile,
                    order.partner_id.vat,
                )

                order_dict.update({
                    "BuyerName": order.partner_id.name,
                    "BuyerPhoneNumber": order.partner_id.mobile,
                    "BuyerNTN": order.partner_id.vat,
                })
            else:
                _logger.info("FBR buyer: no customer selected on POS order")

            items_list = []
            total_qty = 0.0

            for line in order.lines:
                product = line.product_id

                _logger.info(
                    "FBR checking line | line_id=%s | product=%s | qty=%s | price_unit=%s | subtotal=%s | subtotal_incl=%s",
                    line.id,
                    product.display_name if product else False,
                    line.qty,
                    line.price_unit,
                    line.price_subtotal,
                    line.price_subtotal_incl,
                )

                if product and not product.un_registered and product.type != 'service':
                    total_qty += line.qty

                    tax_rate = sum(line.tax_ids_after_fiscal_position.mapped('amount'))
                    line_is_refund = line.price_subtotal < 0

                    line_dic = {
                        "ItemCode": product.default_code,
                        "ItemName": product.name,
                        "Quantity": abs(line.qty) if line_is_refund else line.qty,
                        "PCTCode": product.prod_pct_code,
                        "TaxRate": tax_rate,
                        "SaleValue": abs(line.price_unit) if line_is_refund else line.price_unit,
                        "TotalAmount": abs(line.price_subtotal) if line_is_refund else line.price_subtotal,
                        "TaxCharged": abs(line.price_subtotal_incl - line.price_subtotal)
                            if line_is_refund
                            else round(line.price_subtotal_incl - line.price_subtotal, 4),
                        "InvoiceType": 3 if line_is_refund else 1,
                        "RefUSIN": "",
                    }

                    _logger.info("FBR line added: %s", line_dic)
                    items_list.append(line_dic)

                else:
                    _logger.warning(
                        "FBR line skipped/adjusted | product=%s | un_registered=%s | detailed_type=%s",
                        product.display_name if product else False,
                        product.un_registered if product else False,
                        product.type if product else False,
                    )

                    order_dict["TotalBillAmount"] -= line.price_subtotal_incl
                    order_dict["TotalSaleValue"] -= line.price_subtotal
                    order_dict["TotalTaxCharged"] -= round(
                        line.price_subtotal_incl - line.price_subtotal, 4
                    )

            order_dict.update({
                "Items": items_list,
                "TotalQuantity": abs(total_qty),
            })

            _logger.info("FBR final payload items count: %s", len(items_list))
            _logger.info("FBR final payload: %s", json.dumps(order_dict, indent=2))

            r_json = {}

            try:
                _logger.info("FBR API call starting | url=%s", url)

                body = json.dumps(order_dict).encode("utf-8")
                
                response = http.request(
                    "POST",
                    url,
                    body=body,
                    headers=header,
                    retries=False,
                )

                _logger.info("FBR API call completed | status=%s", response.status)

                response_text = response.data.decode("utf-8", errors="ignore")
                _logger.info("FBR raw response: %s", response_text)

                if response.status != 200:
                    _logger.warning(
                        "FBR API returned non-200 status | status=%s | body=%s",
                        response.status,
                        response_text,
                    )

                try:
                    r_json = json.loads(response_text)
                    _logger.info("FBR parsed JSON response: %s", r_json)
                except ValueError:
                    _logger.exception("FBR JSON parse failed")
                    r_json = {}

                invoice_no = r_json.get("InvoiceNumber") or ""
                _logger.info("FBR invoice number received: %s", invoice_no)

            except Exception as e:
                _logger.exception("FBR API call failed: %s", e)
                invoice_no = ""

            _logger.info("FBR QR generation starting")

            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=20,
                border=4,
            )
            qr.add_data(invoice_no)
            qr.make(fit=True)

            img = qr.make_image()
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            qrcode_img = base64.b64encode(buffer.getvalue()).decode("utf-8")

            _logger.info("FBR QR generated successfully | length=%s", len(qrcode_img or ""))

            order.write({
                "invoice_no": invoice_no,
                "is_registered": True,
                "response": r_json,
            })

            _logger.info(
                "FBR order updated | order_id=%s | invoice_no=%s | is_registered=True",
                order.id,
                invoice_no,
            )

            _logger.info("========== FBR END SUCCESS ==========")
            return [invoice_no, self._normalize_fbr_qr_value(qrcode_img)]

        except Exception as e:
            _logger.exception("FBR main method failed: %s", e)

        _logger.info("========== FBR END FAILED ==========")
        return [invoice_no, self._normalize_fbr_qr_value(qrcode_img)]

    def cron_to_post_data(self):
        pending_orders = self.search([('is_registered','=',False),('invoice_no','=',False)])
        self.pending_order_post(pending_orders)

    def action_to_post_data_to_fbr(self):
        orders = []
        for order in self:
            if not order.is_registered and not order.invoice_no:
                orders.append(order.id)
        pending_orders = self.browse(orders)
        self.pending_order_post(pending_orders)

    def pending_order_post(self,pending_orders):
        header = {"Content-Type": "application/json"}
        for order in pending_orders:
            try:
                url = order.session_id.config_id.fbr_url
                if order and order.session_id and order.session_id.config_id and order.session_id.config_id.auth_header:
                    header.update({'Authorization': 'Bearer ' + order.session_id.config_id.auth_header})
                    bill_amount = order.amount_total
                    tax_amount = order.amount_tax
                    sale_amount = order.amount_total - order.amount_tax
                    if bill_amount < 0:
                        order_dict = {
                            "InvoiceNumber": "",
                            "POSID": order.session_id.config_id.pos_id,
                            "USIN": "USIN0",
                            "DateTime": order.date_order.strftime("%Y-%m-%d %H:%M:%S"),
                            "TotalBillAmount": abs(bill_amount),
                            "TotalSaleValue": abs(sale_amount),
                            "TotalTaxCharged": abs(tax_amount),
                            "PaymentMode": 1,
                            "InvoiceType": 3,
                        }
                    else:
                        order_dict = {
                            "InvoiceNumber": "",
                            "POSID": order.session_id.config_id.pos_id,
                            "USIN": "USIN0",
                            "DateTime": order.date_order.strftime("%Y-%m-%d %H:%M:%S"),
                            "TotalBillAmount": bill_amount,
                            "TotalSaleValue": sale_amount,
                            "TotalTaxCharged": tax_amount,
                            "PaymentMode": 1,
                            "InvoiceType": 1,
                        }
                    if order.partner_id:
                        order_dict.update({
                            "BuyerName": order.partner_id.name,
                            "BuyerPhoneNumber": order.partner_id.mobile,
                            "BuyerNTN": order.partner_id.vat,
                        })
                    if order.lines:
                        items_list = []
                        total_qty = 0.0
                        for line in order.lines:
                            if line.product_id and not line.product_id.un_registered and line.product_id.detailed_type != 'service':
                                tax_rate = 0.0
                                if line.tax_ids_after_fiscal_position:
                                    for tax in line.tax_ids_after_fiscal_position:
                                        tax_rate += tax.amount
                                total_qty += line.qty
                                if line.price_subtotal < 0:
                                    line_dic = {
                                        "ItemCode": line.product_id.default_code,
                                        "ItemName": line.product_id.name,
                                        "Quantity": abs(line.qty),
                                        "PCTCode": line.product_id.prod_pct_code,
                                        "TaxRate": tax_rate,
                                        "SaleValue": abs(line.price_unit),
                                        "TotalAmount": abs(line.price_subtotal),
                                        "TaxCharged": abs(line.price_subtotal_incl) - abs(line.price_subtotal),
                                        "InvoiceType": 3,
                                        "RefUSIN": ""
                                    }
                                else:
                                    line_dic = {
                                        "ItemCode": line.product_id.default_code,
                                        "ItemName": line.product_id.name,
                                        "Quantity": line.qty,
                                        "PCTCode": line.product_id.prod_pct_code,
                                        "TaxRate": tax_rate,
                                        "SaleValue": line.price_unit,
                                        "TotalAmount": line.price_subtotal,
                                        "TaxCharged": line.price_subtotal_incl - line.price_subtotal,
                                        "InvoiceType": 1,
                                        "RefUSIN": ""
                                    }
                                items_list.append(line_dic)
                            else:
                                order_dict['TotalBillAmount'] = order_dict['TotalBillAmount'] - line.price_subtotal_incl
                                order_dict['TotalSaleValue'] = order_dict['TotalSaleValue'] - line.price_subtotal
                                order_dict['TotalTaxCharged'] = order_dict['TotalTaxCharged'] - (line.price_subtotal_incl - line.price_subtotal)
                        order_dict.update({
                            "Items": items_list,
                            'TotalQuantity': abs(total_qty)
                        })
                    # payment_response = requests.post(url, data=json.dumps(order_dict), headers=header, verify=False,
                    #                                  timeout=20)
                    # r_json = payment_response.json()
                    # invoice_no = r_json.get('InvoiceNumber')

                    try:

                        body = json.dumps(order_dict).encode("utf-8")
                        # Make the POST request
                        response = http.request(
                            "POST",
                            url,
                            body=body,
                            headers=header,  # e.g. {'Content-Type': 'application/json', ...}
                            retries=False  # you can adjust retries if needed
                        )
                        _logger.info("FBR API BODY ===>>>: %s", body)

                        # Check status
                        if response.status != 200:
                            _logger.warning("FBR API returned non-200 status: %s, body: %s", response.status, response.data.decode("utf-8", errors="ignore"))
                        # Parse JSON safely
                        try:
                            r_json = json.loads(response.data.decode("utf-8"))
                        except ValueError:
                            _logger.error("Failed to parse JSON from FBR response: %s", response.data)
                            r_json = {}

                        _logger.info('what is response from json fbr api %s and fbr Invoice number %s', r_json, r_json.get('InvoiceNumber'))
                        invoice_no = r_json.get('InvoiceNumber')

                    except Exception as e:
                        _logger.exception("Error calling FBR API: %s", e)
                        invoice_no = None
                    
                    order.sudo().write({'response': r_json, 'is_registered': True, 'invoice_no': invoice_no})

            except Exception as e:
                values = dict(
                    exception=e,
                    traceback=traceback.format_exc(),
                )
                order.write({'response': values})


    def return_order_to_fbr_action(self):
        header = {"Content-Type": "application/json"}
        for order in self:
            fbr_url = order.session_id.config_id.fbr_url
            if order.is_registered and order.invoice_no:
                if not order.is_returned and not order.return_invoice_number:
                    try:
                        if order and order.session_id and order.session_id.config_id and order.session_id.config_id.auth_header:
                            header.update({'Authorization': 'Bearer ' + order.session_id.config_id.auth_header})
                            bill_amount = order.amount_total
                            tax_amount = order.amount_tax
                            sale_amount = order.amount_total - order.amount_tax
                            order_dict = {
                                "InvoiceNumber": "",
                                "POSID": order.session_id.config_id.pos_id,
                                "USIN": order.name,
                                "DateTime": order.date_order.strftime("%Y-%m-%d %H:%M:%S"),
                                "TotalBillAmount": abs(bill_amount),
                                "TotalSaleValue": abs(sale_amount),
                                "TotalTaxCharged": abs(tax_amount),
                                "PaymentMode": 1,
                                "InvoiceType": 3,
                            }
                            if order.partner_id:
                                order_dict.update({
                                    "BuyerName": order.partner_id.name,
                                    "BuyerPhoneNumber": order.partner_id.mobile,
                                    "BuyerNTN": order.partner_id.vat,
                                })
                            if order.lines:
                                items_list = []
                                total_qty = 0.0
                                for line in order.lines:
                                    if not line.product_id.un_registered:
                                        tax_rate = 0.0
                                        if line.tax_ids_after_fiscal_position:
                                            for i in line.tax_ids_after_fiscal_position:
                                                tax = self.env['account.tax'].sudo().search([('id', '=', i.id)])
                                                tax_rate += tax.amount
                                        total_qty += line.qty
                                        line_dic = {
                                            "ItemCode": line.product_id.default_code,
                                            "ItemName": line.product_id.name,
                                            "Quantity": line.qty,
                                            "PCTCode": line.product_id.prod_pct_code,
                                            "TaxRate": tax_rate,
                                            "SaleValue": line.price_unit,
                                            "TotalAmount": line.price_subtotal,
                                            "TaxCharged": line.price_subtotal_incl - line.price_subtotal,
                                            "InvoiceType": 3,
                                            "RefUSIN": ""
                                        }
                                        items_list.append(line_dic)
                                    else:
                                        order_dict['TotalBillAmount'] = order_dict['TotalBillAmount'] - line.price_subtotal_incl
                                        order_dict['TotalSaleValue'] = order_dict['TotalSaleValue'] - line.price_subtotal
                                        order_dict['TotalTaxCharged'] = order_dict['TotalTaxCharged'] - (line.price_subtotal_incl - line.price_subtotal)
                                order_dict.update({
                                    "Items": items_list, 'TotalQuantity': total_qty
                                })
                            payment_response = requests.post(fbr_url, data=json.dumps(order_dict), headers=header, verify=False,
                                                             timeout=50)
                            r_json = payment_response.json()
                            _logger.info(payment_response.text)
                            invoice_no = r_json.get('InvoiceNumber')

                            order.sudo().write({'return_invoice_number': invoice_no,'is_returned':True})
                            return
                    except Exception as e:
                        _logger.info(e)
                        raise ValidationError(e)
                raise ValidationError('This order is already returned to FBR.')
            else:
                raise ValidationError('This order '+order.name+' is not posted yet to FBR.')


    @api.model
    def _order_fields(self, ui_order):
        vals = super()._order_fields(ui_order)
        vals["invoice_no"] = ui_order.get("invoice_no") or False
        vals["is_registered"] = ui_order.get("is_registered") or False
        return vals

    def _fbr_qr_to_base64(self, order):
        """Return QR image as a plain base64 string for the POS frontend."""
        if not order.qr_image:
            return False
        if isinstance(order.qr_image, bytes):
            return order.qr_image.decode("utf-8")
        return order.qr_image

    def _normalize_fbr_qr_value(self, qr_value):
        """Normalize QR value before sending it to the POS JSON frontend."""
        if not qr_value:
            return False
        if isinstance(qr_value, bytes):
            return qr_value.decode("utf-8")
        return qr_value

    def _export_for_ui(self, order):
        data = super()._export_for_ui(order)
        data.update({
            "invoice_no": order.invoice_no or False,
            "is_registered": order.is_registered or False,
            "qr_image": self._fbr_qr_to_base64(order),
        })
        return data
