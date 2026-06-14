# -*- coding: utf-8 -*-
"""End-to-end Splendid → Odoo sync additions.

This extension intentionally keeps the base API client/mapping/logging methods from
splendid_connection.py and adds module-wise sync flows for Sales, Purchase,
Inventory, Accounting and Bank Deposits.
"""

from odoo import _, fields, models
from odoo.exceptions import UserError


class SplendidAccountConnection(models.Model):
    _inherit = "splendid.account.connection"

    auto_confirm_sale_orders = fields.Boolean(
        string="Auto Confirm Sale Orders",
        default=False,
        help="Confirm imported sale orders. Keep disabled for first sync.",
    )
    auto_confirm_purchase_orders = fields.Boolean(
        string="Auto Confirm Purchase Orders",
        default=False,
        help="Confirm imported purchase orders. Keep disabled for first sync.",
    )
    auto_reconcile_payments = fields.Boolean(
        string="Auto Reconcile Payments",
        default=True,
        help="When invoices/bills and payments are posted, reconcile them using Splendid settlement lines.",
    )
    default_undeposited_account_id = fields.Many2one(
        "account.account",
        string="Default Undeposited/Suspense Account",
        domain="[('deprecated','=',False)]",
        help="Used as the source account for bank deposits when the Splendid instrument/account cannot be resolved.",
    )

    last_sale_orders_sync = fields.Datetime(copy=False, string="Last Sale Orders Sync")
    last_sale_deliveries_sync = fields.Datetime(copy=False, string="Last Sale Deliveries Sync")
    last_purchase_orders_sync = fields.Datetime(copy=False, string="Last Purchase Orders Sync")
    last_purchase_receipts_sync = fields.Datetime(copy=False, string="Last Purchase Receipts Sync")
    last_bank_deposits_sync = fields.Datetime(copy=False, string="Last Bank Deposits Sync")
    last_customer_refunds_sync = fields.Datetime(copy=False, string="Last Customer Refunds Sync")
    last_vendor_refunds_sync = fields.Datetime(copy=False, string="Last Vendor Refunds Sync")
    last_sales_module_sync = fields.Datetime(copy=False, string="Last Sales Module Sync")
    last_purchase_module_sync = fields.Datetime(copy=False, string="Last Purchase Module Sync")
    last_accounting_module_sync = fields.Datetime(copy=False, string="Last Accounting Module Sync")

    END_TO_END_ENDPOINTS = {
        "sale_orders": "/SaleOrders",
        "sale_deliveries": "/SaleDeliveries",
        "purchase_orders": "/PurchaseOrders",
        "purchase_receipts": "/PurchaseReceipts",
        "bank_deposits": "/BankDeposits",
        "customer_refunds": "/CustomerRefunds",
        "vendor_refunds": "/VendorRefunds",
    }

    END_TO_END_LAST_FIELDS = {
        "sale_orders": "last_sale_orders_sync",
        "sale_deliveries": "last_sale_deliveries_sync",
        "purchase_orders": "last_purchase_orders_sync",
        "purchase_receipts": "last_purchase_receipts_sync",
        "bank_deposits": "last_bank_deposits_sync",
        "customer_refunds": "last_customer_refunds_sync",
        "vendor_refunds": "last_vendor_refunds_sync",
    }

    SALES_SYNC_SEQUENCE = (
        "customers",
        "products",
        "warehouses",
        "sale_orders",
        "sale_deliveries",
        "sales",
        "sale_returns",
        "customer_receipts",
        "customer_refunds",
    )
    PURCHASE_SYNC_SEQUENCE = (
        "vendors",
        "products",
        "warehouses",
        "purchase_orders",
        "purchase_receipts",
        "purchases",
        "purchase_returns",
        "vendor_payments",
        "vendor_refunds",
    )
    ACCOUNTING_SYNC_SEQUENCE = (
        "chart_accounts",
        "journal_entries",
        "expenses",
        "bank_deposits",
    )

    def _onchange_company_id(self):
        res = super()._onchange_company_id()
        for rec in self:
            rec.default_undeposited_account_id = False
        return res

    # -------------------------------------------------------------------------
    # Buttons / grouped syncs
    # -------------------------------------------------------------------------
    def _sync_sequence(self, sync_types, last_field=False):
        self.ensure_one()
        for sync_type in sync_types:
            self._sync_single_model(sync_type)
        if last_field:
            self.write({last_field: fields.Datetime.now()})
        return True

    def action_sync_sales_module(self):
        for rec in self:
            rec._with_target_company()._sync_sequence(rec.SALES_SYNC_SEQUENCE, "last_sales_module_sync")
        return True

    def action_sync_purchase_module(self):
        for rec in self:
            rec._with_target_company()._sync_sequence(rec.PURCHASE_SYNC_SEQUENCE, "last_purchase_module_sync")
        return True

    def action_sync_accounting_module(self):
        for rec in self:
            rec._with_target_company()._sync_sequence(rec.ACCOUNTING_SYNC_SEQUENCE, "last_accounting_module_sync")
        return True

    def action_sync_sale_orders(self):
        return self._action_sync_single("sale_orders")

    def action_sync_sale_deliveries(self):
        return self._action_sync_single("sale_deliveries")

    def action_sync_purchase_orders(self):
        return self._action_sync_single("purchase_orders")

    def action_sync_purchase_receipts(self):
        return self._action_sync_single("purchase_receipts")

    def action_sync_bank_deposits(self):
        return self._action_sync_single("bank_deposits")

    def action_sync_customer_refunds(self):
        return self._action_sync_single("customer_refunds")

    def action_sync_vendor_refunds(self):
        return self._action_sync_single("vendor_refunds")

    def _sync_single_model(self, sync_type):
        self.ensure_one()
        if sync_type in self.END_TO_END_ENDPOINTS:
            self._sync_endpoint(sync_type, self.END_TO_END_ENDPOINTS[sync_type])
            last_field = self.END_TO_END_LAST_FIELDS.get(sync_type)
            if last_field and last_field in self._fields:
                self.write({last_field: fields.Datetime.now()})
            self.env.cr.commit()
            return True
        return super()._sync_single_model(sync_type)

    def _sync_transactions(self):
        self.ensure_one()
        self._sync_sequence(
            self.SALES_SYNC_SEQUENCE + self.PURCHASE_SYNC_SEQUENCE + self.ACCOUNTING_SYNC_SEQUENCE,
            "last_transaction_sync",
        )
        return True

    def action_sync_all(self):
        for rec in self:
            rec = rec._with_target_company()
            rec._sync_masters()
            rec.action_sync_sales_module()
            rec.action_sync_purchase_module()
            rec._sync_inventory()
            rec._sync_manufacturing()
            rec.action_sync_accounting_module()
            rec.last_full_sync = fields.Datetime.now()
        return True

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    def _first_list(self, payload, *keys):
        for key in keys:
            value = self._find_value(payload, key)
            if isinstance(value, list):
                return value
        return []

    def _document_number(self, payload, fallback=False):
        return self._find_value(payload, "number", "depositNumber", "reference", "paymentReference") or fallback or self._external_id(payload)

    def _document_is_approved(self, payload):
        status = self._find_value(payload, "status")
        if isinstance(status, dict):
            status_text = " ".join(str(x or "") for x in status.values()).lower()
        else:
            status_text = str(status or "").lower()
        return any(word in status_text for word in ("approved", "posted", "completed", "delivered", "paid", "received"))

    def _required_partner(self, payload, kind):
        partner = self._resolve_partner_from_payload(payload, kind)
        if partner:
            return partner
        external_id = self._find_value(payload, "customerId" if kind == "customer" else "vendorId") or self._external_id(payload)
        name = self._find_value(payload, "customerName", "vendorName", "contactName", "name") or _("Splendid %s %s") % (kind.title(), external_id)
        vals = {
            "name": name,
            "company_type": "company",
            "ref": str(external_id or ""),
            "splendid_is_imported": True,
        }
        if "company_id" in self.env["res.partner"]._fields:
            vals["company_id"] = self.company_id.id
        if kind == "customer":
            vals["customer_rank"] = 1
            vals["splendid_customer_id"] = str(external_id or "")
            if self.default_receivable_account_id:
                vals["property_account_receivable_id"] = self.default_receivable_account_id.id
            model_key = "customer"
        else:
            vals["supplier_rank"] = 1
            vals["splendid_vendor_id"] = str(external_id or "")
            if self.default_payable_account_id:
                vals["property_account_payable_id"] = self.default_payable_account_id.id
            model_key = "vendor"
        partner = self.env["res.partner"].with_company(self.company_id).sudo().create(vals)
        if external_id:
            self._set_mapping(model_key, external_id, partner, payload, name)
        return partner

    def _default_uom(self):
        return self.env.ref("uom.product_uom_unit", raise_if_not_found=False) or self.env["uom.uom"].sudo().search([], limit=1)

    def _order_product_variant(self, product_tmpl):
        if product_tmpl:
            return product_tmpl.product_variant_id
        return self.env["product.product"]

    def _line_quantity(self, line, default=1.0):
        return self._safe_float(self._find_value(line, "quantity", "qty", default=default), default)

    def _line_price(self, line, qty=1.0):
        value = self._find_value(line, "price", "salePrice", "purchasePrice", "rate", "unitPrice")
        if value in (False, None, ""):
            net = self._safe_float(self._find_value(line, "netAmount", "grossAmount", "amount", default=0.0), 0.0)
            return net / qty if qty else net
        return self._safe_float(value, 0.0)

    def _customer_location(self):
        location = self.env.ref("stock.stock_location_customers", raise_if_not_found=False)
        if not location:
            location = self.env["stock.location"].sudo().search([("usage", "=", "customer")], limit=1)
        if not location:
            raise UserError(_("No customer stock location found."))
        return location

    def _supplier_location(self):
        location = self.env.ref("stock.stock_location_suppliers", raise_if_not_found=False)
        if not location:
            location = self.env["stock.location"].sudo().search([("usage", "=", "supplier")], limit=1)
        if not location:
            raise UserError(_("No supplier stock location found."))
        return location

    def _default_picking_type(self, warehouse=False, code="outgoing"):
        warehouse = warehouse or self._default_warehouse()
        if code == "outgoing" and warehouse and warehouse.out_type_id:
            return warehouse.out_type_id
        if code == "incoming" and warehouse and warehouse.in_type_id:
            return warehouse.in_type_id
        if code == "internal" and warehouse and warehouse.int_type_id:
            return warehouse.int_type_id
        picking_type = self.env["stock.picking.type"].with_company(self.company_id).sudo().search([
            ("code", "=", code), ("company_id", "=", self.company_id.id)
        ], limit=1)
        if not picking_type:
            raise UserError(_("No %s picking type found for company %s.") % (code, self.company_id.display_name))
        return picking_type

    def _source_to_move_model(self, source, payment_model=False):
        source = str(source or "").lower().replace(" ", "").replace("_", "")
        if "purchaseinvoice" in source or "vendorbill" in source or source == "bill":
            return "purchase_invoice"
        if "salereturn" in source or "creditnote" in source:
            return "sale_return"
        if "purchasereturn" in source or "debitnote" in source:
            return "purchase_return"
        if "saleinvoice" in source or "invoice" in source:
            return "sale_invoice" if payment_model in (False, "customer") else "purchase_invoice"
        return False

    def _settlement_lines(self, payload):
        result = []
        for key in (
            "customerPaymentSettlementDetails",
            "vendorPaymentSettlementDetails",
            "customerRefundSettlementDetails",
            "vendorRefundSettlementDetails",
            "customerSingleSettledEntryItems",
            "vendorSingleSettledEntryItems",
            "settlementDetails",
            "settledEntries",
        ):
            value = self._find_value(payload, key)
            if isinstance(value, list):
                result.extend(value)
        return result

    def _reconcile_payment_allocations(self, payment, payload, payment_model=False):
        if not self.auto_reconcile_payments or not payment or not getattr(payment, "move_id", False):
            return False
        if getattr(payment, "state", False) != "posted":
            return False
        pay_lines = payment.move_id.line_ids.filtered(lambda l: not l.reconciled and l.account_id.account_type in ("asset_receivable", "liability_payable"))
        if not pay_lines:
            return False
        reconciled = 0
        for line in self._settlement_lines(payload):
            source_id = self._find_value(line, "sourceId", "invoiceId", "documentId")
            source_model = self._source_to_move_model(self._find_value(line, "source"), payment_model=payment_model)
            move = self.env["account.move"]
            if source_model and source_id:
                move = self._mapped_record(source_model, source_id, "account.move")
            if not move and self._find_value(line, "number", "sourceNumber"):
                number = self._find_value(line, "number", "sourceNumber")
                move = self.env["account.move"].with_company(self.company_id).sudo().search([
                    ("company_id", "=", self.company_id.id),
                    "|", ("ref", "=", number), ("name", "=", number),
                ], limit=1)
            if not move or move.state != "posted":
                continue
            move_lines = move.line_ids.filtered(lambda l: not l.reconciled and l.account_id in pay_lines.account_id)
            if not move_lines:
                continue
            try:
                (pay_lines + move_lines).reconcile()
                reconciled += 1
            except Exception as exc:  # pylint: disable=broad-except
                self._log("payment_reconcile", "error", str(exc), line, source_id, move)
        if reconciled:
            self._log("payment_reconcile", "success", _("Reconciled %s payment allocation(s).") % reconciled, payload, self._external_id(payload), payment)
        return True

    # -------------------------------------------------------------------------
    # Sales / Purchase Orders
    # -------------------------------------------------------------------------
    def _sale_order_line_cmds(self, payload):
        details = self._first_list(payload, "saleOrderDetails", "details", "items")
        cmds = []
        for line in details:
            product_tmpl = self._resolve_product_from_line(line)
            product = self._order_product_variant(product_tmpl)
            qty = self._line_quantity(line, 1.0)
            vals = {
                "name": self._find_value(line, "description") or (product.display_name if product else _("Splendid Sale Line")),
                "product_uom_qty": qty,
                "price_unit": self._line_price(line, qty),
                "discount": self._safe_float(self._find_value(line, "discountInPercent", default=0.0), 0.0),
            }
            if product:
                vals["product_id"] = product.id
                vals["product_uom"] = product.uom_id.id
            else:
                uom = self._default_uom()
                if uom:
                    vals["product_uom"] = uom.id
            cmds.append((0, 0, vals))
        return cmds

    def _purchase_order_line_cmds(self, payload):
        details = self._first_list(payload, "purchaseOrderDetails", "details", "items")
        cmds = []
        planned = self._parse_datetime(self._find_value(payload, "deliveryDate", "dueDate", "date"))
        for line in details:
            product_tmpl = self._resolve_product_from_line(line)
            product = self._order_product_variant(product_tmpl)
            qty = self._line_quantity(line, 1.0)
            vals = {
                "name": self._find_value(line, "description") or (product.display_name if product else _("Splendid Purchase Line")),
                "product_qty": qty,
                "price_unit": self._line_price(line, qty),
                "date_planned": planned,
            }
            if product:
                vals["product_id"] = product.id
                vals["product_uom"] = product.uom_po_id.id or product.uom_id.id
            else:
                uom = self._default_uom()
                if uom:
                    vals["product_uom"] = uom.id
            cmds.append((0, 0, vals))
        return cmds

    def _import_sale_orders(self, payload):
        external_id = self._external_id(payload)
        existing = self._mapped_record("sale_order", external_id, "sale.order")
        partner = self._required_partner(payload, "customer")
        order_lines = self._sale_order_line_cmds(payload)
        vals = {
            "partner_id": partner.id,
            "company_id": self.company_id.id,
            "date_order": self._parse_datetime(self._find_value(payload, "date")),
            "client_order_ref": self._find_value(payload, "reference") or False,
            "origin": self._find_value(payload, "saleQuotationNumber") or False,
            "note": self._find_value(payload, "comments", "narration", "subject") or False,
            "splendid_external_id": external_id,
            "splendid_source_model": "sale_order",
            "splendid_is_imported": True,
            "splendid_raw_payload": payload,
        }
        SaleOrder = self.env["sale.order"]
        if "partner_invoice_id" in SaleOrder._fields:
            vals["partner_invoice_id"] = partner.address_get(["invoice"]).get("invoice") or partner.id
        if "partner_shipping_id" in SaleOrder._fields:
            vals["partner_shipping_id"] = partner.address_get(["delivery"]).get("delivery") or partner.id
        if "pricelist_id" in SaleOrder._fields and hasattr(partner, "property_product_pricelist") and partner.property_product_pricelist:
            vals["pricelist_id"] = partner.property_product_pricelist.id
        if order_lines:
            vals["order_line"] = order_lines
        if existing:
            order = existing
            if order.state in ("draft", "sent"):
                write_vals = dict(vals)
                if order_lines:
                    write_vals["order_line"] = [(5, 0, 0)] + order_lines
                order.write(write_vals)
        else:
            order = self.env["sale.order"].with_company(self.company_id).sudo().create(vals)
        self._set_mapping("sale_order", external_id, order, payload, self._document_number(payload, order.name))
        if self.auto_confirm_sale_orders and order.state in ("draft", "sent"):
            order.action_confirm()
        return order

    def _import_purchase_orders(self, payload):
        external_id = self._external_id(payload)
        existing = self._mapped_record("purchase_order", external_id, "purchase.order")
        partner = self._required_partner(payload, "vendor")
        order_lines = self._purchase_order_line_cmds(payload)
        vals = {
            "partner_id": partner.id,
            "company_id": self.company_id.id,
            "date_order": self._parse_datetime(self._find_value(payload, "date")),
            "partner_ref": self._find_value(payload, "reference") or False,
            "origin": self._find_value(payload, "saleOrderNumber") or False,
            "notes": self._find_value(payload, "comments", "narration", "subject") or False,
            "splendid_external_id": external_id,
            "splendid_source_model": "purchase_order",
            "splendid_is_imported": True,
            "splendid_raw_payload": payload,
        }
        if order_lines:
            vals["order_line"] = order_lines
        if existing:
            order = existing
            if order.state in ("draft", "sent", "to approve"):
                write_vals = dict(vals)
                if order_lines:
                    write_vals["order_line"] = [(5, 0, 0)] + order_lines
                order.write(write_vals)
        else:
            order = self.env["purchase.order"].with_company(self.company_id).sudo().create(vals)
        self._set_mapping("purchase_order", external_id, order, payload, self._document_number(payload, order.name))
        if self.auto_confirm_purchase_orders and order.state in ("draft", "sent", "to approve"):
            order.button_confirm()
        return order

    # -------------------------------------------------------------------------
    # Delivery / Receipt / Inventory stock documents
    # -------------------------------------------------------------------------
    def _stock_move_cmds_from_lines(self, lines, source_location, dest_location):
        cmds = []
        for line in lines:
            product_tmpl = self._resolve_product_from_line(line)
            if not product_tmpl:
                continue
            product = self._stockable_product_variant(product_tmpl)
            qty = self._line_quantity(line, 0.0)
            if qty <= 0:
                continue
            cmds.append((0, 0, {
                "name": self._find_value(line, "description") or product.display_name,
                "product_id": product.id,
                "product_uom_qty": qty,
                "product_uom": product.uom_id.id,
                "location_id": source_location.id,
                "location_dest_id": dest_location.id,
                "company_id": self.company_id.id,
            }))
        return cmds

    def _import_stock_document(self, payload, external_model, partner_kind, detail_key, direction):
        external_id = self._external_id(payload)
        existing = self._mapped_record(external_model, external_id, "stock.picking")
        if existing:
            return existing
        partner = self._required_partner(payload, partner_kind)
        warehouse = self._resolve_warehouse(payload)
        internal_location = self._warehouse_stock_location(warehouse)
        if direction == "outgoing":
            source_location = internal_location
            dest_location = self._customer_location()
            picking_type = self._default_picking_type(warehouse, "outgoing")
        else:
            source_location = self._supplier_location()
            dest_location = internal_location
            picking_type = self._default_picking_type(warehouse, "incoming")
        lines = self._first_list(payload, detail_key, "details", "items")
        move_cmds = self._stock_move_cmds_from_lines(lines, source_location, dest_location)
        if not move_cmds:
            raise UserError(_("No stockable lines found for Splendid document %s.") % external_id)
        picking = self.env["stock.picking"].with_company(self.company_id).sudo().create({
            "picking_type_id": picking_type.id,
            "partner_id": partner.id,
            "location_id": source_location.id,
            "location_dest_id": dest_location.id,
            "origin": self._document_number(payload, external_id),
            "scheduled_date": self._parse_datetime(self._find_value(payload, "date", "deliveryDate")),
            "company_id": self.company_id.id,
            "move_ids": move_cmds,
            "splendid_external_id": external_id,
            "splendid_source_model": external_model,
            "splendid_is_imported": True,
            "splendid_raw_payload": payload,
        })
        self._set_mapping(external_model, external_id, picking, payload, picking.name)
        self._confirm_or_validate_picking(picking)
        return picking

    def _import_sale_deliveries(self, payload):
        return self._import_stock_document(payload, "sale_delivery", "customer", "saleDeliveryDetails", "outgoing")

    def _import_purchase_receipts(self, payload):
        return self._import_stock_document(payload, "purchase_receipt", "vendor", "purchaseReceiptDetails", "incoming")

    # -------------------------------------------------------------------------
    # Payments / refunds / reconciliation
    # -------------------------------------------------------------------------
    def _resolve_journal_for_payment(self, payload, payment_type):
        detail_keys = (
            "customerPaymentDetails",
            "vendorPaymentDetails",
            "customerRefundDetails",
            "vendorRefundDetails",
            "paymentDetails",
            "details",
        )
        account = self.env["account.account"]
        for detail_key in detail_keys:
            details = self._find_value(payload, detail_key) or []
            if isinstance(details, list):
                for detail in details:
                    account = self._resolve_splendid_account(detail, fallback_kind=False, required=False)
                    if account:
                        break
            if account:
                break
        if not account:
            account = self._resolve_splendid_account(payload, fallback_kind=False, required=False)
        if account:
            journal = self.env["account.journal"].with_company(self.company_id).sudo().search([
                ("company_id", "=", self.company_id.id),
                ("type", "in", ("bank", "cash")),
                ("default_account_id", "=", account.id),
            ], limit=1)
            if journal:
                return journal
        return self._default_journal("bank")

    def _import_payment(self, payload, external_model, payment_type, partner_type):
        payment = super()._import_payment(payload, external_model, payment_type, partner_type)
        payment_model = "customer" if partner_type == "customer" else "vendor"
        self._reconcile_payment_allocations(payment, payload, payment_model=payment_model)
        return payment

    def _import_customer_refunds(self, payload):
        return self._import_payment(payload, "customer_refund", "outbound", "customer")

    def _import_vendor_refunds(self, payload):
        return self._import_payment(payload, "vendor_refund", "inbound", "supplier")

    # -------------------------------------------------------------------------
    # Bank deposits
    # -------------------------------------------------------------------------
    def _bank_deposit_bank_account(self, payload):
        bank_account_payload = self._nested(payload, "bankAccount")
        if bank_account_payload:
            account = self._resolve_splendid_account(
                bank_account_payload,
                fallback_kind=False,
                required=False,
                id_keys=("accountId",),
                nested_keys=("account",),
                code_keys=("accountCode", "code", "accountNumber"),
            )
            if account:
                return account
        if self.bank_journal_id and self.bank_journal_id.default_account_id:
            return self.bank_journal_id.default_account_id
        return self._default_account("suspense")

    def _bank_deposit_source_account(self, line):
        account = self._resolve_splendid_account(line, fallback_kind=False, required=False)
        if account:
            return account
        instrument = self._nested(line, "instrument")
        if instrument:
            # Instruments often represent undeposited cheques/cash. If an account is
            # not explicitly provided, use the configured undeposited/suspense account.
            account = self._resolve_splendid_account(instrument, fallback_kind=False, required=False)
            if account:
                return account
        return self.default_undeposited_account_id or self.default_suspense_account_id or self._default_account("suspense")

    def _bank_deposit_detail_lines(self, payload):
        result = []
        for key in ("bankDepositCashDetails", "bankDepositDetails", "unDepositedCheques"):
            lines = self._find_value(payload, key)
            if isinstance(lines, list):
                result.extend(lines)
        return result

    def _import_bank_deposits(self, payload):
        external_id = self._external_id(payload)
        existing = self._mapped_record("bank_deposit", external_id, "account.move")
        if existing:
            return existing
        journal = self.bank_journal_id or self._default_journal("bank")
        bank_account = self._bank_deposit_bank_account(payload)
        detail_lines = self._bank_deposit_detail_lines(payload)
        source_line_vals = []
        source_total = 0.0
        for line in detail_lines:
            instrument = self._nested(line, "instrument")
            amount = self._safe_float(self._find_value(line, "amount", "balanceAmount", default=False), 0.0)
            if not amount and instrument:
                amount = self._safe_float(self._find_value(instrument, "amount", default=0.0), 0.0)
            if amount <= 0:
                continue
            account = self._bank_deposit_source_account(line)
            source_total += amount
            source_line_vals.append((0, 0, {
                "name": self._find_value(line, "description") or self._find_value(instrument, "instrumentNumber") or _("Splendid Bank Deposit Source"),
                "account_id": account.id,
                "debit": 0.0,
                "credit": amount,
                "partner_id": False,
            }))
        total = self._safe_float(self._find_value(payload, "totalAmount", "amount", "netAmount", default=source_total), source_total)
        if total <= 0:
            raise UserError(_("Bank deposit %s has no amount.") % external_id)
        diff = round(total - source_total, 2)
        if abs(diff) >= 0.01:
            suspense = self.default_undeposited_account_id or self.default_suspense_account_id or self._default_account("suspense")
            source_line_vals.append((0, 0, {
                "name": _("Splendid Bank Deposit Difference"),
                "account_id": suspense.id,
                "debit": 0.0 if diff > 0 else abs(diff),
                "credit": diff if diff > 0 else 0.0,
            }))
        line_ids = [(0, 0, {
            "name": self._document_number(payload, external_id),
            "account_id": bank_account.id,
            "debit": total,
            "credit": 0.0,
        })] + source_line_vals
        move = self.env["account.move"].with_company(self.company_id).sudo().with_context(check_move_validity=False).create({
            "move_type": "entry",
            "date": self._parse_date(self._find_value(payload, "date")),
            "journal_id": journal.id,
            "ref": self._document_number(payload, external_id),
            "narration": self._find_value(payload, "narration", "comments") or False,
            "line_ids": line_ids,
            "company_id": self.company_id.id,
            "splendid_external_id": external_id,
            "splendid_source_model": "bank_deposit",
            "splendid_is_imported": True,
            "splendid_raw_payload": payload,
        })
        self._set_mapping("bank_deposit", external_id, move, payload, move.ref)
        if self.auto_post_moves and not self.import_as_draft and self._document_is_approved(payload) and move.state == "draft":
            move.action_post()
        return move
