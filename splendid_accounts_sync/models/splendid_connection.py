# -*- coding: utf-8 -*-
import hashlib
import json
import logging
import re
from datetime import datetime
from urllib.parse import urljoin

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SplendidAccountConnection(models.Model):
    _name = "splendid.account.connection"
    _description = "Splendid Accounts API Connection"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(required=True, default="Splendid Accounts")
    active = fields.Boolean(default=True)
    base_url = fields.Char(required=True, default="https://app.splendidaccounts.com")
    tenant = fields.Char(required=True)
    branch = fields.Char(required=True)
    api_key = fields.Char(required=True, string="API Key")
    api_secret = fields.Char(required=True, string="API Secret")
    app_id = fields.Char(required=True, string="App ID")
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    page_size = fields.Integer(default=100)
    timeout = fields.Integer(default=60)
    verify_ssl = fields.Boolean(default=True)
    import_as_draft = fields.Boolean(
        default=True,
        help="Recommended for first sync. Odoo will create draft accounting documents for review.",
    )
    auto_post_moves = fields.Boolean(
        default=False,
        help="Post created accounting entries after import. Use only after validating account/tax mapping.",
    )
    force_splendid_accounts = fields.Boolean(
        string="Force Splendid Accounts",
        default=True,
        help="When Splendid sends accountId/account object on a transaction line, use the imported Splendid account. "
             "If the account cannot be resolved, the line is logged as an error instead of silently using a default account.",
    )
    auto_fetch_missing_accounts = fields.Boolean(
        string="Auto Fetch Missing Accounts",
        default=True,
        help="If a transaction references a Splendid account that is not yet mapped in Odoo, fetch /Accounts/{id} and import it automatically.",
    )
    update_existing_draft_records = fields.Boolean(
        string="Update Existing Draft Records",
        default=True,
        help="When re-syncing, update already imported draft invoices, payments and journal entries so corrected Splendid account mapping is applied.",
    )
    sync_inventory_snapshot = fields.Boolean(
        string="Sync Inventory Snapshot",
        default=True,
        help="Read Products/Inventory and adjust Odoo on-hand quantity to match Splendid per product/warehouse.",
    )
    auto_validate_stock_pickings = fields.Boolean(
        string="Auto Validate Stock Pickings",
        default=False,
        help="Validate imported stock movements/adjustments automatically. Keep disabled until testing is completed.",
    )
    auto_confirm_mrp = fields.Boolean(
        string="Auto Confirm Manufacturing Orders",
        default=False,
        help="Confirm imported manufacturing orders after creation. Keep disabled for first sync.",
    )

    sale_journal_id = fields.Many2one("account.journal", domain="[('type','=','sale'), ('company_id','=',company_id)]")
    purchase_journal_id = fields.Many2one("account.journal", domain="[('type','=','purchase'), ('company_id','=',company_id)]")
    bank_journal_id = fields.Many2one("account.journal", domain="[('type','in',('bank','cash')), ('company_id','=',company_id)]")
    misc_journal_id = fields.Many2one("account.journal", domain="[('type','=','general'), ('company_id','=',company_id)]")
    default_receivable_account_id = fields.Many2one("account.account", domain="[('account_type','=','asset_receivable'), ('deprecated','=',False)]")
    default_payable_account_id = fields.Many2one("account.account", domain="[('account_type','=','liability_payable'), ('deprecated','=',False)]")
    default_income_account_id = fields.Many2one("account.account", domain="[('account_type','in',('income','income_other')), ('deprecated','=',False)]")
    default_expense_account_id = fields.Many2one("account.account", domain="[('account_type','in',('expense','expense_direct_cost')), ('deprecated','=',False)]")
    default_stock_account_id = fields.Many2one("account.account", domain="[('account_type','in',('asset_current','asset_fixed')), ('deprecated','=',False)]")
    default_suspense_account_id = fields.Many2one("account.account", domain="[('deprecated','=',False)]")

    last_master_sync = fields.Datetime(copy=False)
    last_transaction_sync = fields.Datetime(copy=False)
    last_inventory_sync = fields.Datetime(copy=False)
    last_manufacturing_sync = fields.Datetime(copy=False)
    last_chart_accounts_sync = fields.Datetime(copy=False, string="Last Chart of Accounts Sync")
    last_customers_sync = fields.Datetime(copy=False, string="Last Customers Sync")
    last_vendors_sync = fields.Datetime(copy=False, string="Last Vendors Sync")
    last_products_sync = fields.Datetime(copy=False, string="Last Products Sync")
    last_warehouses_sync = fields.Datetime(copy=False, string="Last Warehouses Sync")
    last_inventory_snapshot_sync = fields.Datetime(copy=False, string="Last Inventory Snapshot Sync")
    last_inventory_adjustments_sync = fields.Datetime(copy=False, string="Last Inventory Adjustments Sync")
    last_stock_movements_sync = fields.Datetime(copy=False, string="Last Stock Movements Sync")
    last_boms_sync = fields.Datetime(copy=False, string="Last BOMs Sync")
    last_manufacturing_orders_sync = fields.Datetime(copy=False, string="Last Manufacturing Orders Sync")
    last_sales_sync = fields.Datetime(copy=False, string="Last Sales Sync")
    last_sale_returns_sync = fields.Datetime(copy=False, string="Last Sales Returns Sync")
    last_purchases_sync = fields.Datetime(copy=False, string="Last Purchases Sync")
    last_purchase_returns_sync = fields.Datetime(copy=False, string="Last Purchase Returns Sync")
    last_customer_receipts_sync = fields.Datetime(copy=False, string="Last Customer Receipts Sync")
    last_vendor_payments_sync = fields.Datetime(copy=False, string="Last Vendor Payments Sync")
    last_journal_entries_sync = fields.Datetime(copy=False, string="Last Journal Entries Sync")
    last_expenses_sync = fields.Datetime(copy=False, string="Last Expenses Sync")
    last_full_sync = fields.Datetime(copy=False)
    log_ids = fields.One2many("splendid.sync.log", "connection_id")
    mapping_ids = fields.One2many("splendid.sync.map", "connection_id")

    # Splendid tags/endpoints confirmed from the provided OpenAPI JSON.
    MASTER_ENDPOINTS = {
        "chart_accounts": "/Accounts",
        "customers": "/Customers",
        "vendors": "/Vendors",
        "products": "/Products",
        "warehouses": "/Entities/Warehouses",
    }
    INVENTORY_ENDPOINTS = {
        "inventory_adjustments": "/InventoryAdjustments",
        "stock_movements": "/StocksMovement",
    }
    MANUFACTURING_ENDPOINTS = {
        "manufacturing_orders": "/JobOrders",
    }
    TRANSACTION_ENDPOINTS = {
        "sales": "/SaleInvoices",
        "sale_returns": "/SaleReturns",
        "purchases": "/PurchaseInvoices",
        "purchase_returns": "/PurchaseReturns",
        "customer_receipts": "/CustomerPayments",
        "vendor_payments": "/VendorPayments",
        "journal_entries": "/JournalEntries",
        "expenses": "/Expenses",
    }

    SINGLE_SYNC_ENDPOINTS = {}
    SINGLE_SYNC_ENDPOINTS.update(MASTER_ENDPOINTS)
    SINGLE_SYNC_ENDPOINTS.update(INVENTORY_ENDPOINTS)
    SINGLE_SYNC_ENDPOINTS.update(MANUFACTURING_ENDPOINTS)
    SINGLE_SYNC_ENDPOINTS.update(TRANSACTION_ENDPOINTS)

    SINGLE_SYNC_LAST_FIELDS = {
        "chart_accounts": "last_chart_accounts_sync",
        "customers": "last_customers_sync",
        "vendors": "last_vendors_sync",
        "products": "last_products_sync",
        "warehouses": "last_warehouses_sync",
        "inventory_snapshot": "last_inventory_snapshot_sync",
        "inventory_adjustments": "last_inventory_adjustments_sync",
        "stock_movements": "last_stock_movements_sync",
        "boms": "last_boms_sync",
        "manufacturing_orders": "last_manufacturing_orders_sync",
        "sales": "last_sales_sync",
        "sale_returns": "last_sale_returns_sync",
        "purchases": "last_purchases_sync",
        "purchase_returns": "last_purchase_returns_sync",
        "customer_receipts": "last_customer_receipts_sync",
        "vendor_payments": "last_vendor_payments_sync",
        "journal_entries": "last_journal_entries_sync",
        "expenses": "last_expenses_sync",
    }

    def _company_domain(self):
        self.ensure_one()
        return ["|", ("company_id", "=", False), ("company_id", "=", self.company_id.id)]

    def _with_target_company(self):
        self.ensure_one()
        return self.with_company(self.company_id).with_context(
            allowed_company_ids=[self.company_id.id],
            force_company=self.company_id.id,
        )

    @api.onchange("company_id")
    def _onchange_company_id(self):
        for rec in self:
            rec.sale_journal_id = False
            rec.purchase_journal_id = False
            rec.bank_journal_id = False
            rec.misc_journal_id = False
            rec.default_receivable_account_id = False
            rec.default_payable_account_id = False
            rec.default_income_account_id = False
            rec.default_expense_account_id = False
            rec.default_stock_account_id = False
            rec.default_suspense_account_id = False

    def _headers(self):
        self.ensure_one()
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Api-Key": self.api_key or "",
            "X-Api-Secret": self.api_secret or "",
            "X-App-Id": self.app_id or "",
        }

    def _api_path(self, endpoint):
        endpoint = endpoint.strip()
        if endpoint.startswith("/api/"):
            return endpoint.format(tenant=self.tenant, branch=self.branch)
        return "/api/%s/%s%s" % (self.tenant, self.branch, endpoint if endpoint.startswith("/") else "/" + endpoint)

    def _api_url(self, endpoint):
        self.ensure_one()
        return urljoin(self.base_url.rstrip("/") + "/", self._api_path(endpoint).lstrip("/"))

    def _api_request(self, method, endpoint, params=None, payload=None):
        self.ensure_one()
        url = self._api_url(endpoint)
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self._headers(),
                params=params or {},
                json=payload,
                timeout=self.timeout or 60,
                verify=self.verify_ssl,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            raise UserError(_("Splendid API request failed: %s") % exc) from exc

        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            return {"raw": response.text}

    def _extract_list(self, data):
        if not data:
            return []
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("data", "items", "records", "results", "result", "value", "list", "rows"):
                value = data.get(key)
                if isinstance(value, list):
                    return value
                if isinstance(value, dict):
                    nested = self._extract_list(value)
                    if nested:
                        return nested
            for value in data.values():
                if isinstance(value, list):
                    return value
            if any(k.lower() in data for k in ("id", "code", "number", "name")):
                return [data]
        return []

    def _fetch_collection(self, endpoint, params=None, use_paging=True):
        self.ensure_one()
        all_rows = []
        page = 1
        size = self.page_size or 100
        while True:
            request_params = dict(params or {})
            if use_paging:
                request_params.setdefault("page", page)
                request_params.setdefault("size", size)
            data = self._api_request("GET", endpoint, params=request_params)
            rows = self._extract_list(data)
            all_rows.extend(rows)
            if not use_paging or len(rows) < size or not rows:
                break
            page += 1
            if page > 10000:
                raise UserError(_("Paging stopped after 10,000 pages for endpoint %s") % endpoint)
        return all_rows

    def _find_value(self, payload, *keys, default=False):
        if not isinstance(payload, dict):
            return default
        lower = {str(k).lower(): v for k, v in payload.items()}
        for key in keys:
            if key in payload:
                return payload[key]
            value = lower.get(str(key).lower())
            if value is not None:
                return value
        return default

    def _nested(self, payload, key):
        value = self._find_value(payload, key)
        return value if isinstance(value, dict) else {}

    def _external_id(self, payload):
        value = self._find_value(payload, "id", "Id", "externalId", "sourceId")
        if value in (False, None, ""):
            value = self._find_value(payload, "number", "code", "sku", "name")
        return str(value or "")

    def _payload_hash(self, payload):
        raw = json.dumps(payload or {}, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _parse_date(self, value):
        if not value:
            return fields.Date.context_today(self)
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            value = value.replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(value).date()
            except ValueError:
                return value[:10]
        return value

    def _map_search(self, external_model, external_id, odoo_model):
        return self.env["splendid.sync.map"].sudo().search(
            [
                ("connection_id", "=", self.id),
                ("external_model", "=", external_model),
                ("external_id", "=", str(external_id)),
                ("odoo_model", "=", odoo_model),
            ],
            limit=1,
        )

    def _mapped_record(self, external_model, external_id, odoo_model):
        mapping = self._map_search(external_model, external_id, odoo_model)
        if mapping and mapping.res_id:
            return self.env[odoo_model].with_company(self.company_id).sudo().browse(mapping.res_id).exists()
        return self.env[odoo_model].with_company(self.company_id)

    def _set_mapping(self, external_model, external_id, odoo_record, payload=None, external_name=None):
        if not external_id or not odoo_record:
            return False
        vals = {
            "connection_id": self.id,
            "external_model": external_model,
            "external_id": str(external_id),
            "external_name": external_name or self._find_value(payload or {}, "name", "displayName", "number", "code"),
            "odoo_model": odoo_record._name,
            "res_id": odoo_record.id,
            "last_payload_hash": self._payload_hash(payload),
            "last_sync_date": fields.Datetime.now(),
        }
        mapping = self._map_search(external_model, external_id, odoo_record._name)
        if mapping:
            mapping.write(vals)
        else:
            mapping = self.env["splendid.sync.map"].with_company(self.company_id).sudo().create(vals)
        return mapping

    def _log(self, sync_type, state, message=None, payload=None, external_id=None, record=None):
        self.env["splendid.sync.log"].with_company(self.company_id).sudo().create(
            {
                "connection_id": self.id,
                "sync_type": sync_type,
                "state": state,
                "message": message,
                "payload": payload,
                "external_id": str(external_id or ""),
                "odoo_model": record._name if record else False,
                "res_id": record.id if record else False,
            }
        )

    def _default_journal(self, journal_type):
        journal = {
            "sale": self.sale_journal_id,
            "purchase": self.purchase_journal_id,
            "bank": self.bank_journal_id,
            "general": self.misc_journal_id,
        }.get(journal_type)
        if journal:
            return journal
        domain = [("company_id", "=", self.company_id.id)]
        if journal_type == "bank":
            domain.append(("type", "in", ("bank", "cash")))
        else:
            domain.append(("type", "=", journal_type))
        journal = self.env["account.journal"].with_company(self.company_id).search(domain, limit=1)
        if not journal:
            raise UserError(_("Please configure a %s journal for Splendid sync.") % journal_type)
        return journal

    def _default_account(self, kind):
        account = {
            "income": self.default_income_account_id,
            "expense": self.default_expense_account_id,
            "receivable": self.default_receivable_account_id,
            "payable": self.default_payable_account_id,
            "stock": self.default_stock_account_id,
            "suspense": self.default_suspense_account_id,
        }.get(kind)
        if account:
            return account
        account_type_map = {
            "income": ("income", "income_other"),
            "expense": ("expense", "expense_direct_cost"),
            "receivable": ("asset_receivable",),
            "payable": ("liability_payable",),
            "stock": ("asset_current", "asset_fixed"),
        }
        account_types = account_type_map.get(kind) or ("asset_current", "expense")
        domain = [("deprecated", "=", False), ("account_type", "in", account_types)]
        account_fields = self.env["account.account"]._fields
        if "company_id" in account_fields:
            domain.append(("company_id", "=", self.company_id.id))
        elif "company_ids" in account_fields:
            domain.append(("company_ids", "in", self.company_id.id))
        account = self.env["account.account"].with_company(self.company_id).search(domain, limit=1)
        if not account:
            raise UserError(_("Please configure a default %s account for Splendid sync.") % kind)
        return account

    def _account_company_domain(self):
        self.ensure_one()
        account_fields = self.env["account.account"]._fields
        if "company_id" in account_fields:
            return [("company_id", "=", self.company_id.id)]
        if "company_ids" in account_fields:
            return [("company_ids", "in", self.company_id.id)]
        return []

    def _payload_has_account_reference(self, payload, id_keys=None, nested_keys=None, code_keys=None):
        if not isinstance(payload, dict):
            return False
        id_keys = id_keys or ("accountId", "accountID", "account_id")
        nested_keys = nested_keys or ("account",)
        code_keys = code_keys or ("accountCode", "accountNumber", "accountNo")
        for key in id_keys:
            value = self._find_value(payload, key)
            if value not in (False, None, ""):
                return True
        for key in nested_keys:
            value = self._find_value(payload, key)
            if isinstance(value, dict) and value:
                return True
        for key in code_keys:
            value = self._find_value(payload, key)
            if value not in (False, None, ""):
                return True
        return False

    def _clean_account_code(self, code):
        """Return an Odoo-safe account code.

        Odoo account.account.code accepts only alphanumeric characters and dots.
        Splendid sometimes sends codes with spaces, slashes, hyphens or other
        separators, so we normalize those values before searching/creating
        accounts.
        """
        code = str(code or "").strip()
        code = re.sub(r"[\s\-_/]+", ".", code)
        code = re.sub(r"[^A-Za-z0-9.]", "", code)
        code = re.sub(r"\.+", ".", code).strip(".")
        return code[:64]

    def _get_payload_account_code(self, payload, external_id=False):
        raw_code = self._find_value(payload, "code", "number", "accountCode", "accountNumber", "accountNo")
        code = self._clean_account_code(raw_code)
        if code:
            return code

        # If the API sends the account number inside the name/description, use it.
        # Example: "GST/HST on Purchases - 118100" -> "118100".
        for key in ("name", "displayName", "description"):
            text = str(self._find_value(payload, key, default="") or "")
            match = re.search(r"\b[A-Za-z]*\d[A-Za-z0-9.]*\b", text)
            if match:
                code = self._clean_account_code(match.group(0))
                if code:
                    return code

        code = self._clean_account_code(external_id or self._external_id(payload))
        if not code:
            raise UserError(_("Invalid account code received from Splendid API."))
        return code

    def _search_account_by_code_or_external(self, external_id=None, code=None):
        self.ensure_one()
        Account = self.env["account.account"].with_company(self.company_id).sudo()
        company_domain = self._account_company_domain()
        if external_id not in (False, None, ""):
            account = Account.search([("splendid_account_id", "=", str(external_id))] + company_domain, limit=1)
            if account:
                return account
            mapped = self._mapped_record("account", external_id, "account.account")
            if mapped:
                return mapped
        code = self._clean_account_code(code)
        if code:
            account = Account.search([("code", "=", code)] + company_domain, limit=1)
            if account:
                return account
        return Account

    def _resolve_splendid_account(self, payload, fallback_kind=False, required=False, id_keys=None, nested_keys=None, code_keys=None):
        """Resolve the exact Splendid account from transaction/product payload.

        Important: default/config accounts are used only when Splendid did not send any account reference.
        If Splendid sends accountId/account and force_splendid_accounts is enabled, missing mapping becomes an error.
        """
        self.ensure_one()
        if not isinstance(payload, dict):
            return self._default_account(fallback_kind) if fallback_kind else self.env["account.account"]

        id_keys = id_keys or ("accountId", "accountID", "account_id")
        nested_keys = nested_keys or ("account",)
        code_keys = code_keys or ("accountCode", "accountNumber", "accountNo")
        has_reference = self._payload_has_account_reference(payload, id_keys, nested_keys, code_keys)

        external_id = False
        nested_account = {}
        account_code = False

        for key in id_keys:
            value = self._find_value(payload, key)
            if isinstance(value, dict):
                nested_account = value
                external_id = self._external_id(value)
                break
            if value not in (False, None, ""):
                external_id = value
                break

        for key in nested_keys:
            value = self._find_value(payload, key)
            if isinstance(value, dict) and value:
                nested_account = value
                if not external_id:
                    external_id = self._external_id(value)
                account_code = self._find_value(value, "code", "number") or account_code
                break

        for key in code_keys:
            value = self._find_value(payload, key)
            if value not in (False, None, ""):
                account_code = value
                break

        account = self._search_account_by_code_or_external(external_id, account_code)
        if account:
            return account

        if nested_account:
            return self._import_chart_accounts(nested_account)

        if external_id and self.auto_fetch_missing_accounts:
            try:
                fetched = self._api_request("GET", "/Accounts/%s" % external_id)
                rows = self._extract_list(fetched)
                if rows:
                    return self._import_chart_accounts(rows[0])
                if isinstance(fetched, dict) and fetched:
                    return self._import_chart_accounts(fetched)
            except Exception as exc:  # pylint: disable=broad-except
                _logger.warning("Could not auto-fetch Splendid account %s: %s", external_id, exc)

        account = self._search_account_by_code_or_external(external_id, account_code)
        if account:
            return account

        if has_reference and (required or self.force_splendid_accounts):
            raise UserError(_("Splendid account could not be resolved. Account reference: %s / %s. Please run Sync Masters first or check account mapping.") % (external_id or "", account_code or ""))

        return self._default_account(fallback_kind) if fallback_kind else self.env["account.account"]

    def _resolve_named_account(self, payload, id_key, nested_key, fallback_kind=False, required=False):
        return self._resolve_splendid_account(
            payload,
            fallback_kind=fallback_kind,
            required=required,
            id_keys=(id_key,),
            nested_keys=(nested_key,),
            code_keys=("%sCode" % nested_key, "%sNumber" % nested_key),
        )

    def _apply_partner_control_account(self, partner, payload, move_type):
        if not partner or not payload:
            return False
        account = self._resolve_splendid_account(payload, fallback_kind=False, required=False)
        if not account:
            return False
        if move_type.startswith("out_") and account.account_type == "asset_receivable":
            partner.with_company(self.company_id).sudo().property_account_receivable_id = account.id
            return True
        if move_type.startswith("in_") and account.account_type == "liability_payable":
            partner.with_company(self.company_id).sudo().property_account_payable_id = account.id
            return True
        return False

    def _resolve_journal_for_payment(self, payload, payment_type):
        self.ensure_one()
        detail_keys = ("customerPaymentDetails", "vendorPaymentDetails", "paymentDetails", "details")
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

    def action_test_connection(self):
        for rec in self:
            rec = rec._with_target_company()
            data = rec._api_request("GET", "/Accounts", params={"page": 1, "size": 1})
            rec.message_post(body=_("Splendid connection successful. Response preview: %s") % json.dumps(data, default=str)[:500])
        return True

    def _action_sync_single(self, sync_type):
        for rec in self:
            rec._with_target_company()._sync_single_model(sync_type)
        return True

    def action_sync_chart_accounts(self):
        return self._action_sync_single("chart_accounts")

    def action_sync_customers(self):
        return self._action_sync_single("customers")

    def action_sync_vendors(self):
        return self._action_sync_single("vendors")

    def action_sync_products(self):
        return self._action_sync_single("products")

    def action_sync_warehouses(self):
        return self._action_sync_single("warehouses")

    def action_sync_inventory_snapshot(self):
        return self._action_sync_single("inventory_snapshot")

    def action_sync_inventory_adjustments(self):
        return self._action_sync_single("inventory_adjustments")

    def action_sync_stock_movements(self):
        return self._action_sync_single("stock_movements")

    def action_sync_boms(self):
        return self._action_sync_single("boms")

    def action_sync_manufacturing_orders(self):
        return self._action_sync_single("manufacturing_orders")

    def action_sync_sales(self):
        return self._action_sync_single("sales")

    def action_sync_sale_returns(self):
        return self._action_sync_single("sale_returns")

    def action_sync_purchases(self):
        return self._action_sync_single("purchases")

    def action_sync_purchase_returns(self):
        return self._action_sync_single("purchase_returns")

    def action_sync_customer_receipts(self):
        return self._action_sync_single("customer_receipts")

    def action_sync_vendor_payments(self):
        return self._action_sync_single("vendor_payments")

    def action_sync_journal_entries(self):
        return self._action_sync_single("journal_entries")

    def action_sync_expenses(self):
        return self._action_sync_single("expenses")

    def action_sync_masters(self):
        for rec in self:
            rec._with_target_company()._sync_masters()
        return True

    def action_sync_transactions(self):
        for rec in self:
            rec._with_target_company()._sync_transactions()
        return True

    def action_sync_inventory(self):
        for rec in self:
            rec._with_target_company()._sync_inventory()
        return True

    def action_sync_manufacturing(self):
        for rec in self:
            rec._with_target_company()._sync_manufacturing()
        return True

    def action_sync_all(self):
        for rec in self:
            rec = rec._with_target_company()
            rec._sync_masters()
            rec._sync_boms()
            rec._sync_inventory()
            rec._sync_manufacturing()
            rec._sync_transactions()
            rec.last_full_sync = fields.Datetime.now()
        return True

    @api.model
    def cron_sync_all_active(self):
        connections = self.search([("active", "=", True)])
        for connection in connections:
            try:
                connection._with_target_company().action_sync_all()
            except Exception as exc:  # pylint: disable=broad-except
                _logger.exception("Splendid cron failed for %s", connection.display_name)
                connection._log("cron", "error", str(exc))

    def _sync_masters(self):
        self.ensure_one()
        for sync_type in self.MASTER_ENDPOINTS:
            self._sync_single_model(sync_type)
        self.last_master_sync = fields.Datetime.now()

    def _sync_transactions(self):
        self.ensure_one()
        for sync_type in self.TRANSACTION_ENDPOINTS:
            self._sync_single_model(sync_type)
        self.last_transaction_sync = fields.Datetime.now()

    def _sync_inventory(self):
        self.ensure_one()
        if self.sync_inventory_snapshot:
            self._sync_single_model("inventory_snapshot")
        for sync_type in self.INVENTORY_ENDPOINTS:
            self._sync_single_model(sync_type)
        self.last_inventory_sync = fields.Datetime.now()

    def _sync_manufacturing(self):
        self.ensure_one()
        self._sync_single_model("boms")
        for sync_type in self.MANUFACTURING_ENDPOINTS:
            self._sync_single_model(sync_type)
        self.last_manufacturing_sync = fields.Datetime.now()

    def _sync_single_model(self, sync_type):
        self.ensure_one()
        if sync_type == "inventory_snapshot":
            self._sync_inventory_snapshot()
        elif sync_type == "boms":
            self._sync_boms()
        else:
            endpoint = self.SINGLE_SYNC_ENDPOINTS.get(sync_type)
            if not endpoint:
                raise UserError(_("No Splendid endpoint configured for %s") % sync_type)
            self._sync_endpoint(sync_type, endpoint)
        last_field = self.SINGLE_SYNC_LAST_FIELDS.get(sync_type)
        if last_field and last_field in self._fields:
            self.write({last_field: fields.Datetime.now()})
        self.env.cr.commit()
        return True

    def _fetch_detail_payload(self, endpoint, payload):
        """List endpoints may return summary rows without line/details.
        Fetch /{endpoint}/{id} so transaction accounts from detail lines are available.
        """
        if not isinstance(payload, dict):
            return payload
        external_id = self._external_id(payload)
        if not external_id:
            return payload
        try:
            detail = self._api_request("GET", "%s/%s" % (endpoint.rstrip("/"), external_id))
        except Exception as exc:  # pylint: disable=broad-except
            _logger.debug("Could not fetch detail payload for %s/%s: %s", endpoint, external_id, exc)
            return payload
        rows = self._extract_list(detail)
        if rows:
            return rows[0]
        if isinstance(detail, dict) and detail:
            return detail
        return payload

    def _sync_endpoint(self, sync_type, endpoint):
        self.ensure_one()
        rows = self._fetch_collection(endpoint)
        importer = getattr(self, "_import_%s" % sync_type, None)
        if not importer:
            raise UserError(_("No importer defined for %s") % sync_type)
        for payload in rows:
            external_id = self._external_id(payload)
            try:
                full_payload = self._fetch_detail_payload(endpoint, payload)
                record = importer(full_payload)
                self._log(sync_type, "success", "Imported", full_payload, external_id, record)
            except Exception as exc:  # pylint: disable=broad-except
                _logger.exception("Failed to import Splendid %s/%s", sync_type, external_id)
                self._log(sync_type, "error", str(exc), payload, external_id)

    def _import_chart_accounts(self, payload):
        external_id = self._external_id(payload)
        existing = self._mapped_record("account", external_id, "account.account")
        code = self._get_payload_account_code(payload, external_id)
        name = self._find_value(payload, "name", "displayName", "description") or code
        vals = {
            "code": code,
            "name": name,
            "account_type": self._map_account_type(payload),
            "splendid_account_id": external_id,
            "splendid_is_imported": True,
        }
        account_fields = self.env["account.account"]._fields
        if "company_id" in account_fields:
            vals["company_id"] = self.company_id.id
        elif "company_ids" in account_fields:
            vals["company_ids"] = [(4, self.company_id.id)]
        if existing:
            existing.write(vals)
            account = existing
        else:
            search_domain = [("code", "=", code)]
            account_fields = self.env["account.account"]._fields
            if "company_id" in account_fields:
                search_domain.append(("company_id", "=", self.company_id.id))
            elif "company_ids" in account_fields:
                search_domain.append(("company_ids", "in", self.company_id.id))
            account = self.env["account.account"].with_company(self.company_id).sudo().search(search_domain, limit=1)
            if account:
                account.write(vals)
            else:
                account = self.env["account.account"].with_company(self.company_id).sudo().create(vals)
        self._set_mapping("account", external_id, account, payload, name)
        return account

    def _map_account_type(self, payload):
        text = " ".join(
            str(x or "")
            for x in (
                self._find_value(payload, "accountType", "accountTypeId"),
                self._find_value(payload, "accountClass"),
                self._find_value(payload, "accountGroup"),
                self._find_value(payload, "name"),
                self._find_value(payload, "code"),
            )
        ).lower()
        if "receivable" in text or "customer" in text:
            return "asset_receivable"
        if "payable" in text or "vendor" in text or "supplier" in text:
            return "liability_payable"
        if "bank" in text or "cash" in text:
            return "asset_cash"
        if "fixed" in text and "asset" in text:
            return "asset_fixed"
        if "asset" in text:
            return "asset_current"
        if "liabil" in text:
            return "liability_current"
        if "equity" in text or "capital" in text:
            return "equity"
        if "cost" in text:
            return "expense_direct_cost"
        if "expense" in text:
            return "expense"
        if "income" in text or "revenue" in text or "sale" in text:
            return "income"
        return "expense"

    def _import_customers(self, payload):
        return self._import_partner(payload, "customer")

    def _import_vendors(self, payload):
        return self._import_partner(payload, "vendor")

    def _import_partner(self, payload, partner_type):
        external_id = self._external_id(payload)
        model_key = "customer" if partner_type == "customer" else "vendor"
        existing = self._mapped_record(model_key, external_id, "res.partner")
        name = self._find_value(payload, "name", "displayName", "printName", "contactPerson") or _("Splendid Contact %s") % external_id
        vals = {
            "name": name,
            "street": self._find_value(payload, "address1"),
            "street2": self._find_value(payload, "address2"),
            "city": self._find_value(payload, "city"),
            "zip": self._find_value(payload, "zip", "postalCode"),
            "email": self._find_value(payload, "email", "email1"),
            "phone": self._find_value(payload, "phone", "phone1"),
            "mobile": self._find_value(payload, "phone2", "mobile"),
            "ref": self._find_value(payload, "code", "number") or external_id,
            "splendid_is_imported": True,
            "company_type": "company",
        }
        if "company_id" in self.env["res.partner"]._fields:
            vals["company_id"] = self.company_id.id
        if partner_type == "customer":
            vals.update({"customer_rank": 1, "splendid_customer_id": external_id})
            if self.default_receivable_account_id:
                vals["property_account_receivable_id"] = self.default_receivable_account_id.id
        else:
            vals.update({"supplier_rank": 1, "splendid_vendor_id": external_id})
            if self.default_payable_account_id:
                vals["property_account_payable_id"] = self.default_payable_account_id.id
        vals = {k: v for k, v in vals.items() if v not in (False, None)}
        if existing:
            existing.write(vals)
            partner = existing
        else:
            domain = []
            if vals.get("email"):
                domain = [("email", "=", vals["email"])]
            elif vals.get("ref"):
                domain = [("ref", "=", vals["ref"])]
            if domain and "company_id" in self.env["res.partner"]._fields:
                domain = ["&"] + domain + ["|", ("company_id", "=", False), ("company_id", "=", self.company_id.id)]
            partner = self.env["res.partner"].with_company(self.company_id).sudo().search(domain, limit=1) if domain else self.env["res.partner"].with_company(self.company_id)
            if partner:
                partner.write(vals)
            else:
                partner = self.env["res.partner"].with_company(self.company_id).sudo().create(vals)
        self._set_mapping(model_key, external_id, partner, payload, name)
        return partner

    def _import_products(self, payload):
        external_id = self._external_id(payload)
        existing = self._mapped_record("product", external_id, "product.template")
        name = self._find_value(payload, "name", "displayName", "shortName", "sku") or _("Splendid Product %s") % external_id
        sku = self._find_value(payload, "sku", "code", "barcode", "number") or external_id
        vals = {
            "name": name,
            "default_code": str(sku),
            "barcode": self._find_value(payload, "barcode") or False,
            "list_price": float(self._find_value(payload, "salePrice", "maximumRetailPrice", default=0.0) or 0.0),
            "standard_price": float(self._find_value(payload, "purchasePrice", "averageCost", default=0.0) or 0.0),
            "sale_ok": bool(self._find_value(payload, "isForSale", default=True)),
            "purchase_ok": bool(self._find_value(payload, "isForPurchase", default=True)),
            "splendid_product_id": external_id,
            "splendid_is_imported": True,
        }
        if "company_id" in self.env["product.template"]._fields:
            vals["company_id"] = self.company_id.id
        income_account = self._resolve_named_account(payload, "salesAccountId", "salesAccount", fallback_kind=False, required=False)
        expense_account = self._resolve_named_account(payload, "expenseAccountId", "expenseAccount", fallback_kind=False, required=False)
        if income_account and "property_account_income_id" in self.env["product.template"]._fields:
            vals["property_account_income_id"] = income_account.id
        if expense_account and "property_account_expense_id" in self.env["product.template"]._fields:
            vals["property_account_expense_id"] = expense_account.id
        description = self._find_value(payload, "description")
        if description:
            vals["description_sale"] = description
            vals["description_purchase"] = description
        vals.update(self._product_type_vals(payload))
        vals = {k: v for k, v in vals.items() if v is not None}
        if existing:
            existing.write(vals)
            product = existing
        else:
            product_domain = [("default_code", "=", str(sku))]
            if "company_id" in self.env["product.template"]._fields:
                product_domain = ["&"] + product_domain + ["|", ("company_id", "=", False), ("company_id", "=", self.company_id.id)]
            product = self.env["product.template"].with_company(self.company_id).sudo().search(product_domain, limit=1)
            if product:
                product.write(vals)
            else:
                product = self.env["product.template"].with_company(self.company_id).sudo().create(vals)
        self._set_mapping("product", external_id, product, payload, name)
        return product

    def _import_warehouses(self, payload):
        external_id = self._external_id(payload)
        existing = self._mapped_record("warehouse", external_id, "stock.warehouse")
        name = self._find_value(payload, "name", "displayName", "code") or _("Splendid Warehouse %s") % external_id
        code_source = str(self._find_value(payload, "code", "number") or name or external_id).upper()
        code = "".join(ch for ch in code_source if ch.isalnum())[:5] or ("SP%s" % external_id)[-5:]
        Warehouse = self.env["stock.warehouse"].with_company(self.company_id).sudo()
        if not existing:
            existing = Warehouse.search([("company_id", "=", self.company_id.id), "|", ("name", "=", name), ("code", "=", code)], limit=1)
        if not existing:
            original_code = code
            seq = 1
            while Warehouse.search([("company_id", "=", self.company_id.id), ("code", "=", code)], limit=1):
                code = (original_code[:3] + str(seq))[:5]
                seq += 1
            vals = {"name": name, "code": code, "company_id": self.company_id.id}
            existing = Warehouse.create(vals)
        else:
            existing.write({"name": name})
        if "splendid_warehouse_id" in existing._fields:
            existing.write({"splendid_warehouse_id": external_id, "splendid_is_imported": True})
        self._set_mapping("warehouse", external_id, existing, payload, name)
        return existing

    def _resolve_warehouse(self, payload=None, warehouse_id=False, nested_key="warehouse"):
        self.ensure_one()
        payload = payload or {}
        external_id = warehouse_id or self._find_value(payload, "warehouseId", "warehouseID")
        warehouse = self._mapped_record("warehouse", external_id, "stock.warehouse") if external_id else self.env["stock.warehouse"]
        if warehouse:
            return warehouse
        nested = self._nested(payload, nested_key)
        if nested:
            return self._import_warehouses(nested)
        return self._default_warehouse()

    def _default_warehouse(self):
        warehouse = self.env["stock.warehouse"].with_company(self.company_id).sudo().search([("company_id", "=", self.company_id.id)], limit=1)
        if not warehouse:
            raise UserError(_("Please create/configure at least one Odoo warehouse for company %s.") % self.company_id.display_name)
        return warehouse

    def _warehouse_stock_location(self, warehouse=False):
        warehouse = warehouse or self._default_warehouse()
        if warehouse and warehouse.lot_stock_id:
            return warehouse.lot_stock_id
        location = self.env["stock.location"].sudo().search([("usage", "=", "internal"), ("company_id", "in", [False, self.company_id.id])], limit=1)
        if not location:
            raise UserError(_("No internal stock location found for company %s.") % self.company_id.display_name)
        return location

    def _inventory_location(self):
        location = self.env.ref("stock.stock_location_inventory", raise_if_not_found=False)
        if not location:
            location = self.env["stock.location"].sudo().search([("usage", "=", "inventory")], limit=1)
        if not location:
            raise UserError(_("No inventory adjustment location found."))
        return location

    def _default_internal_picking_type(self, warehouse=False):
        warehouse = warehouse or self._default_warehouse()
        if warehouse and warehouse.int_type_id:
            return warehouse.int_type_id
        picking_type = self.env["stock.picking.type"].with_company(self.company_id).sudo().search([
            ("code", "=", "internal"), ("company_id", "=", self.company_id.id)
        ], limit=1)
        if not picking_type:
            raise UserError(_("No internal picking type found for company %s.") % self.company_id.display_name)
        return picking_type

    def _stockable_product_variant(self, product_tmpl):
        if not product_tmpl:
            return self.env["product.product"]
        vals = {}
        if "detailed_type" in product_tmpl._fields and product_tmpl.detailed_type != "product":
            vals["detailed_type"] = "product"
        elif "type" in product_tmpl._fields and product_tmpl.type != "product":
            vals["type"] = "product"
        if "is_storable" in product_tmpl._fields and not product_tmpl.is_storable:
            vals["is_storable"] = True
        if vals:
            product_tmpl.sudo().write(vals)
        return product_tmpl.product_variant_id

    def _sync_inventory_snapshot(self):
        rows = self._fetch_collection("/Products/Inventory", use_paging=False)
        for payload in rows:
            external_id = self._external_id(payload)
            try:
                count = 0
                for line in self._inventory_snapshot_lines(payload):
                    product_tmpl = line.get("product_tmpl")
                    if not product_tmpl:
                        continue
                    product = self._stockable_product_variant(product_tmpl)
                    warehouse = line.get("warehouse") or self._default_warehouse()
                    location = self._warehouse_stock_location(warehouse)
                    target_qty = float(line.get("quantity") or 0.0)
                    Quant = self.env["stock.quant"].with_company(self.company_id).sudo()
                    current_qty = Quant._get_available_quantity(product, location)
                    diff = target_qty - current_qty
                    if abs(diff) >= 0.00001:
                        Quant._update_available_quantity(product, location, diff)
                    count += 1
                self._log("inventory_snapshot", "success", _("Applied %s inventory snapshot line(s).") % count, payload, external_id)
            except Exception as exc:  # pylint: disable=broad-except
                _logger.exception("Failed to apply inventory snapshot %s", external_id)
                self._log("inventory_snapshot", "error", str(exc), payload, external_id)

    def _inventory_snapshot_lines(self, payload):
        containers = []
        for key in ("inventoryDetails", "warehouseStock", "warehouseStocks", "productStockLevels", "stockLevels", "stocks", "inventory", "items", "details"):
            value = self._find_value(payload, key)
            if isinstance(value, list):
                containers.extend(value)
        if not containers:
            containers = [payload]
        result = []
        for item in containers:
            product_tmpl = self._resolve_product_from_line(item) or self._resolve_product_from_line(payload)
            warehouse = self._resolve_warehouse(item)
            quantity = self._find_value(
                item,
                "availableQuantity", "availableQty", "quantityOnHand", "onHandQuantity", "currentStock",
                "stockQty", "balanceQty", "closingQuantity", "closingQty", "quantity", "stock",
                default=0.0,
            )
            result.append({"product_tmpl": product_tmpl, "warehouse": warehouse, "quantity": quantity})
        return result

    def _import_inventory_adjustments(self, payload):
        external_id = self._external_id(payload)
        existing = self._mapped_record("inventory_adjustment", external_id, "stock.picking")
        if existing:
            return existing
        details = self._find_value(payload, "inventoryAdjustmentDetails", "details") or []
        if not isinstance(details, list):
            details = []
        negative = self._is_negative_adjustment(payload)
        warehouse = self._resolve_warehouse(payload)
        internal_location = self._warehouse_stock_location(warehouse)
        inventory_location = self._inventory_location()
        source_location = internal_location if negative else inventory_location
        dest_location = inventory_location if negative else internal_location
        move_cmds = []
        for line in details:
            product_tmpl = self._resolve_product_from_line(line)
            if not product_tmpl:
                continue
            product = self._stockable_product_variant(product_tmpl)
            qty = float(self._find_value(line, "quantity", default=0.0) or 0.0)
            if qty <= 0:
                continue
            move_cmds.append((0, 0, {
                "name": self._find_value(line, "description") or product.display_name,
                "product_id": product.id,
                "product_uom_qty": qty,
                "product_uom": product.uom_id.id,
                "location_id": source_location.id,
                "location_dest_id": dest_location.id,
                "company_id": self.company_id.id,
            }))
        if not move_cmds:
            raise UserError(_("No inventory adjustment lines found for Splendid adjustment %s.") % external_id)
        picking = self.env["stock.picking"].with_company(self.company_id).sudo().create({
            "picking_type_id": self._default_internal_picking_type(warehouse).id,
            "location_id": source_location.id,
            "location_dest_id": dest_location.id,
            "origin": self._find_value(payload, "number", "reference") or external_id,
            "scheduled_date": self._parse_datetime(self._find_value(payload, "date")),
            "company_id": self.company_id.id,
            "move_ids": move_cmds,
            "splendid_external_id": external_id,
            "splendid_source_model": "inventory_adjustment",
            "splendid_is_imported": True,
            "splendid_raw_payload": payload,
        })
        self._set_mapping("inventory_adjustment", external_id, picking, payload, picking.name)
        self._confirm_or_validate_picking(picking)
        return picking

    def _is_negative_adjustment(self, payload):
        text = " ".join(str(x or "") for x in (
            self._find_value(payload, "adjustmentType", "type", "status"),
            self._find_value(self._nested(payload, "adjustmentType"), "name", "code"),
            self._find_value(payload, "number", "reference", "comments", "narration"),
        )).lower()
        return any(word in text for word in ("decrease", "debit", "issue", "loss", "short", "out", "reduce", "negative", "damage"))

    def _import_stock_movements(self, payload):
        external_id = self._external_id(payload)
        existing = self._mapped_record("stock_movement", external_id, "stock.picking")
        if existing:
            return existing
        from_warehouse = self._resolve_warehouse(payload, warehouse_id=self._find_value(payload, "fromId"), nested_key="from")
        to_warehouse = self._resolve_warehouse(payload, warehouse_id=self._find_value(payload, "toId"), nested_key="to")
        source_location = self._warehouse_stock_location(from_warehouse)
        dest_location = self._warehouse_stock_location(to_warehouse)
        details = self._find_value(payload, "stockMovementDetails", "details") or []
        if not isinstance(details, list):
            details = []
        move_cmds = []
        for line in details:
            product_tmpl = self._resolve_product_from_line(line)
            if not product_tmpl:
                continue
            product = self._stockable_product_variant(product_tmpl)
            qty = float(self._find_value(line, "quantity", default=0.0) or 0.0)
            if qty <= 0:
                continue
            move_cmds.append((0, 0, {
                "name": self._find_value(line, "description") or product.display_name,
                "product_id": product.id,
                "product_uom_qty": qty,
                "product_uom": product.uom_id.id,
                "location_id": source_location.id,
                "location_dest_id": dest_location.id,
                "company_id": self.company_id.id,
            }))
        if not move_cmds:
            raise UserError(_("No stock movement lines found for Splendid movement %s.") % external_id)
        picking = self.env["stock.picking"].with_company(self.company_id).sudo().create({
            "picking_type_id": self._default_internal_picking_type(from_warehouse).id,
            "location_id": source_location.id,
            "location_dest_id": dest_location.id,
            "origin": self._find_value(payload, "number", "reference") or external_id,
            "scheduled_date": self._parse_datetime(self._find_value(payload, "date")),
            "company_id": self.company_id.id,
            "move_ids": move_cmds,
            "splendid_external_id": external_id,
            "splendid_source_model": "stock_movement",
            "splendid_is_imported": True,
            "splendid_raw_payload": payload,
        })
        self._set_mapping("stock_movement", external_id, picking, payload, picking.name)
        self._confirm_or_validate_picking(picking)
        return picking

    def _confirm_or_validate_picking(self, picking):
        if not picking:
            return False
        if picking.state == "draft":
            picking.action_confirm()
        if self.auto_validate_stock_pickings and picking.state not in ("done", "cancel"):
            picking.action_assign()
            for move in picking.move_ids:
                qty = move.product_uom_qty
                if "quantity" in move._fields:
                    move.quantity = qty
                elif "quantity_done" in move._fields:
                    move.quantity_done = qty
            picking.button_validate()
        return True

    def _parse_datetime(self, value):
        if not value:
            return fields.Datetime.now()
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            value = value.replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(value).replace(tzinfo=None)
            except ValueError:
                return fields.Datetime.now()
        return value

    def _selection_has_value(self, model, field_name, value):
        field = model._fields.get(field_name)
        if not field or not getattr(field, "selection", False):
            return False
        selection = field.selection
        if isinstance(selection, str):
            selection = getattr(model, selection)()
        elif callable(selection):
            selection = selection(model)
        return value in [item[0] for item in (selection or [])]

    def _product_type_vals(self, payload):
        track_inventory = bool(self._find_value(payload, "trackInventory", default=False))
        product_model = self.env["product.template"]
        vals = {}

        type_text = " ".join(
            str(x or "")
            for x in (
                self._find_value(payload, "type"),
                self._find_value(payload, "productType"),
                self._find_value(payload, "itemType"),
                self._find_value(payload, "category"),
            )
        ).lower()

        is_service = "service" in type_text
        odoo_type = "service" if is_service else "consu"

        # Odoo 18/19 product.template.type uses consu/service/combo.
        # Do not send "product" here; it causes:
        # Wrong value for product.template.type: 'product'
        if "type" in product_model._fields:
            if self._selection_has_value(product_model, "type", odoo_type):
                vals["type"] = odoo_type
            elif self._selection_has_value(product_model, "type", "product") and track_inventory and not is_service:
                vals["type"] = "product"
            elif self._selection_has_value(product_model, "type", "consu"):
                vals["type"] = "consu"

        if "detailed_type" in product_model._fields:
            if self._selection_has_value(product_model, "detailed_type", odoo_type):
                vals["detailed_type"] = odoo_type
            elif self._selection_has_value(product_model, "detailed_type", "product") and track_inventory and not is_service:
                vals["detailed_type"] = "product"
            elif self._selection_has_value(product_model, "detailed_type", "consu"):
                vals["detailed_type"] = "consu"

        if "is_storable" in product_model._fields:
            vals["is_storable"] = bool(track_inventory and not is_service)
        return vals

    def _import_sales(self, payload):
        return self._import_invoice(payload, "sale_invoice", "out_invoice", "customer", "saleInvoiceDetails")

    def _import_sale_returns(self, payload):
        return self._import_invoice(payload, "sale_return", "out_refund", "customer", "saleReturnDetails")

    def _import_purchases(self, payload):
        return self._import_invoice(payload, "purchase_invoice", "in_invoice", "vendor", "purchaseInvoiceDetails")

    def _import_purchase_returns(self, payload):
        return self._import_invoice(payload, "purchase_return", "in_refund", "vendor", "purchaseReturnDetails")

    def _import_invoice(self, payload, external_model, move_type, partner_kind, detail_key):
        external_id = self._external_id(payload)
        existing = self._mapped_record(external_model, external_id, "account.move")
        partner = self._resolve_partner_from_payload(payload, partner_kind)
        self._apply_partner_control_account(partner, payload, move_type)
        journal = self._default_journal("sale" if move_type.startswith("out_") else "purchase")
        line_cmds = self._invoice_line_cmds(payload, move_type, detail_key)
        if not line_cmds:
            amount = float(self._find_value(payload, "netAmount", "grossAmount", "totalAmount", default=0.0) or 0.0)
            account = self._resolve_splendid_account(payload, fallback_kind=("income" if move_type.startswith("out_") else "expense"), required=False)
            line_cmds = [(0, 0, {"name": self._find_value(payload, "narration", "comments", "number") or "Splendid line", "quantity": 1.0, "price_unit": amount, "account_id": account.id})]
        vals = {
            "move_type": move_type,
            "partner_id": partner.id if partner else False,
            "invoice_date": self._parse_date(self._find_value(payload, "date")),
            "invoice_date_due": self._parse_date(self._find_value(payload, "dueDate")) if self._find_value(payload, "dueDate") else False,
            "journal_id": journal.id,
            "ref": self._find_value(payload, "reference", "number", "paymentReference") or external_id,
            "invoice_line_ids": line_cmds,
            "splendid_external_id": external_id,
            "splendid_source_model": external_model,
            "splendid_is_imported": True,
            "splendid_raw_payload": payload,
            "company_id": self.company_id.id,
        }
        if existing:
            move = existing
            if self.update_existing_draft_records and move.state == "draft":
                write_vals = dict(vals)
                write_vals.pop("move_type", None)
                write_vals.pop("company_id", None)
                write_vals["invoice_line_ids"] = [(5, 0, 0)] + line_cmds
                move.with_context(check_move_validity=False).write(write_vals)
        else:
            move = self.env["account.move"].with_company(self.company_id).sudo().create(vals)
        self._set_mapping(external_model, external_id, move, payload, vals["ref"])
        if self.auto_post_moves and not self.import_as_draft and move.state == "draft":
            move.action_post()
        return move

    def _invoice_line_cmds(self, payload, move_type, detail_key):
        details = self._find_value(payload, detail_key) or []
        if not isinstance(details, list):
            details = []
        cmds = []
        for line in details:
            product = self._resolve_product_from_line(line)
            account = self._resolve_line_account(line, product, move_type)
            qty = float(self._find_value(line, "quantity", default=1.0) or 1.0)
            price = self._find_value(line, "price", "salePrice", "purchasePrice")
            if price in (False, None, ""):
                net = float(self._find_value(line, "netAmount", "grossAmount", default=0.0) or 0.0)
                price = net / qty if qty else net
            vals = {
                "name": self._find_value(line, "description") or (product.display_name if product else "Splendid line"),
                "quantity": qty,
                "price_unit": float(price or 0.0),
                "discount": float(self._find_value(line, "discountInPercent", default=0.0) or 0.0),
                "account_id": account.id,
            }
            if product:
                vals["product_id"] = product.product_variant_id.id
            cmds.append((0, 0, vals))
        return cmds

    def _resolve_line_account(self, line, product_tmpl, move_type):
        splendid_account = self._resolve_splendid_account(line, fallback_kind=False, required=True)
        if splendid_account:
            return splendid_account
        if product_tmpl:
            product = product_tmpl.product_variant_id
            if move_type.startswith("out_"):
                account = product.property_account_income_id or product.categ_id.property_account_income_categ_id
                if account:
                    return account
            account = product.property_account_expense_id or product.categ_id.property_account_expense_categ_id
            if account:
                return account
        return self._default_account("income" if move_type.startswith("out_") else "expense")

    def _resolve_partner_from_payload(self, payload, kind):
        key = "customerId" if kind == "customer" else "vendorId"
        nested_key = "customer" if kind == "customer" else "vendor"
        external_id = self._find_value(payload, key)
        partner = self._mapped_record(kind, external_id, "res.partner") if external_id else self.env["res.partner"]
        if partner:
            return partner
        nested = self._nested(payload, nested_key)
        if nested:
            return self._import_partner(nested, kind)
        return self.env["res.partner"]

    def _resolve_product_from_line(self, line):
        external_id = self._find_value(line, "productId")
        product = self._mapped_record("product", external_id, "product.template") if external_id else self.env["product.template"]
        if product:
            return product
        nested = self._nested(line, "product")
        if nested:
            return self._import_products(nested)
        return self.env["product.template"]

    def _import_customer_receipts(self, payload):
        return self._import_payment(payload, "customer_receipt", "inbound", "customer")

    def _import_vendor_payments(self, payload):
        return self._import_payment(payload, "vendor_payment", "outbound", "supplier")

    def _import_payment(self, payload, external_model, payment_type, partner_type):
        external_id = self._external_id(payload)
        existing = self._mapped_record(external_model, external_id, "account.payment")
        partner_kind = "customer" if partner_type == "customer" else "vendor"
        partner = self._resolve_partner_from_payload(payload, partner_kind)
        journal = self._resolve_journal_for_payment(payload, payment_type)
        pml = journal.inbound_payment_method_line_ids[:1] if payment_type == "inbound" else journal.outbound_payment_method_line_ids[:1]
        amount = float(self._find_value(payload, "totalAmount", "amount", "allocatedAmount", default=0.0) or 0.0)
        vals = {
            "payment_type": payment_type,
            "partner_type": partner_type,
            "partner_id": partner.id if partner else False,
            "amount": amount,
            "date": self._parse_date(self._find_value(payload, "date")),
            "journal_id": journal.id,
            "ref": self._find_value(payload, "reference", "number", "comments") or external_id,
            "splendid_external_id": external_id,
            "splendid_source_model": external_model,
            "splendid_is_imported": True,
            "splendid_raw_payload": payload,
            "company_id": self.company_id.id,
        }
        if pml:
            vals["payment_method_line_id"] = pml.id
        if existing:
            payment = existing
            if self.update_existing_draft_records and getattr(payment, "state", False) == "draft":
                payment.write(vals)
        else:
            payment = self.env["account.payment"].with_company(self.company_id).sudo().create(vals)
        self._set_mapping(external_model, external_id, payment, payload, vals["ref"])
        if self.auto_post_moves and not self.import_as_draft and getattr(payment, "state", False) == "draft":
            payment.action_post()
        return payment

    def _import_journal_entries(self, payload):
        external_id = self._external_id(payload)
        existing = self._mapped_record("journal_entry", external_id, "account.move")
        details = self._find_value(payload, "journalEntryDetails") or []
        line_cmds = []
        total_debit = 0.0
        total_credit = 0.0
        for line in details:
            account = self._resolve_splendid_account(line, fallback_kind="suspense", required=True)
            partner = self._resolve_generic_contact(line)
            debit = float(self._find_value(line, "debit", default=0.0) or 0.0)
            credit = float(self._find_value(line, "credit", default=0.0) or 0.0)
            total_debit += debit
            total_credit += credit
            vals = {
                "name": self._find_value(line, "description") or self._find_value(payload, "narration") or "Splendid journal line",
                "account_id": account.id,
                "debit": debit,
                "credit": credit,
            }
            if partner:
                vals["partner_id"] = partner.id
            line_cmds.append((0, 0, vals))
        if line_cmds and round(total_debit - total_credit, 2):
            diff = round(total_debit - total_credit, 2)
            suspense = self._default_account("suspense")
            line_cmds.append((0, 0, {
                "name": "Splendid auto-balance",
                "account_id": suspense.id,
                "debit": abs(diff) if diff < 0 else 0.0,
                "credit": diff if diff > 0 else 0.0,
            }))
        if not line_cmds:
            amount = float(self._find_value(payload, "amount", default=0.0) or 0.0)
            line_cmds = self._balanced_entry_lines("Splendid journal", self._default_account("expense"), self._default_account("suspense"), amount)
        vals = {
            "move_type": "entry",
            "date": self._parse_date(self._find_value(payload, "date")),
            "journal_id": self._default_journal("general").id,
            "ref": self._find_value(payload, "reference", "number", "narration") or external_id,
            "line_ids": line_cmds,
            "splendid_external_id": external_id,
            "splendid_source_model": "journal_entry",
            "splendid_is_imported": True,
            "splendid_raw_payload": payload,
            "company_id": self.company_id.id,
        }
        if existing:
            move = existing
            if self.update_existing_draft_records and move.state == "draft":
                write_vals = dict(vals)
                write_vals.pop("move_type", None)
                write_vals.pop("company_id", None)
                write_vals["line_ids"] = [(5, 0, 0)] + line_cmds
                move.with_context(check_move_validity=False).write(write_vals)
        else:
            move = self.env["account.move"].with_company(self.company_id).sudo().create(vals)
        self._set_mapping("journal_entry", external_id, move, payload, move.ref)
        if self.auto_post_moves and not self.import_as_draft:
            move.action_post()
        return move

    def _import_expenses(self, payload):
        external_id = self._external_id(payload)
        existing = self._mapped_record("expense", external_id, "account.move")
        details = self._find_value(payload, "expenseDetails") or []
        debit_cmds = []
        total = 0.0
        for line in details:
            account = self._resolve_splendid_account(line, fallback_kind="expense", required=True)
            amount = float(self._find_value(line, "netAmount", "grossAmount", default=0.0) or 0.0)
            total += amount
            debit_cmds.append((0, 0, {"name": self._find_value(line, "description") or "Splendid expense", "account_id": account.id, "debit": amount, "credit": 0.0}))
        if not debit_cmds:
            total = float(self._find_value(payload, "netAmount", "grossAmount", default=0.0) or 0.0)
            debit_cmds.append((0, 0, {"name": self._find_value(payload, "comments", "narration") or "Splendid expense", "account_id": self._default_account("expense").id, "debit": total, "credit": 0.0}))
        credit_account = self._resolve_splendid_account(payload, fallback_kind="suspense", required=True)
        debit_cmds.append((0, 0, {"name": self._find_value(payload, "reference", "number") or "Splendid expense payment", "account_id": credit_account.id, "debit": 0.0, "credit": total}))
        vals = {
            "move_type": "entry",
            "date": self._parse_date(self._find_value(payload, "date")),
            "journal_id": self._default_journal("general").id,
            "ref": self._find_value(payload, "reference", "number", "comments") or external_id,
            "line_ids": debit_cmds,
            "splendid_external_id": external_id,
            "splendid_source_model": "expense",
            "splendid_is_imported": True,
            "splendid_raw_payload": payload,
            "company_id": self.company_id.id,
        }
        if existing:
            move = existing
            if self.update_existing_draft_records and move.state == "draft":
                write_vals = dict(vals)
                write_vals.pop("move_type", None)
                write_vals.pop("company_id", None)
                write_vals["line_ids"] = [(5, 0, 0)] + debit_cmds
                move.with_context(check_move_validity=False).write(write_vals)
        else:
            move = self.env["account.move"].with_company(self.company_id).sudo().create(vals)
        self._set_mapping("expense", external_id, move, payload, move.ref)
        if self.auto_post_moves and not self.import_as_draft:
            move.action_post()
        return move

    def _import_manufacturing_orders(self, payload):
        external_id = self._external_id(payload)
        existing = self._mapped_record("manufacturing_order", external_id, "mrp.production")
        if existing:
            return existing
        product_tmpl = self._mapped_record("product", self._find_value(payload, "assemblyProductId"), "product.template")
        if not product_tmpl and self._nested(payload, "assemblyProduct"):
            product_tmpl = self._import_products(self._nested(payload, "assemblyProduct"))
        if not product_tmpl:
            raise UserError(_("Manufacturing product is missing for Splendid Job Order %s.") % external_id)
        product = self._stockable_product_variant(product_tmpl)
        qty = float(self._find_value(payload, "quantityToProduce", "actualQuantityProduced", default=1.0) or 1.0)
        warehouse = self._resolve_warehouse(payload)
        location = self._warehouse_stock_location(warehouse)
        bom = self.env["mrp.bom"].with_company(self.company_id).sudo().search([
            ("product_tmpl_id", "=", product_tmpl.id), ("company_id", "in", [False, self.company_id.id])
        ], limit=1)
        raw_move_cmds = self._manufacturing_raw_move_cmds(payload, location)
        vals = {
            "product_id": product.id,
            "product_qty": qty,
            "product_uom_id": product.uom_id.id,
            "origin": self._find_value(payload, "number", "reference") or external_id,
            "date_start": self._parse_datetime(self._find_value(payload, "date")),
            "company_id": self.company_id.id,
            "location_src_id": location.id,
            "location_dest_id": location.id,
            "splendid_external_id": external_id,
            "splendid_source_model": "manufacturing_order",
            "splendid_is_imported": True,
            "splendid_raw_payload": payload,
        }
        if bom:
            vals["bom_id"] = bom.id
        if raw_move_cmds:
            vals["move_raw_ids"] = raw_move_cmds
        production = self.env["mrp.production"].with_company(self.company_id).sudo().create(vals)
        self._set_mapping("manufacturing_order", external_id, production, payload, production.name)
        if self.auto_confirm_mrp and production.state == "draft":
            production.action_confirm()
        return production

    def _manufacturing_raw_move_cmds(self, payload, location):
        details = self._find_value(payload, "jobOrderDetails", "details") or []
        if not isinstance(details, list):
            details = []
        cmds = []
        for line in details:
            if self._find_value(line, "isParent", default=False):
                continue
            if self._find_value(line, "isInput", default=True) is False:
                continue
            product_tmpl = self._resolve_product_from_line(line)
            if not product_tmpl:
                continue
            product = self._stockable_product_variant(product_tmpl)
            qty = float(self._find_value(line, "quantity", "defaultQuantity", default=0.0) or 0.0)
            if qty <= 0:
                continue
            cmds.append((0, 0, {
                "name": self._find_value(line, "description") or product.display_name,
                "product_id": product.id,
                "product_uom_qty": qty,
                "product_uom": product.uom_id.id,
                "location_id": location.id,
                "location_dest_id": self.env.ref("stock.stock_location_production").id,
                "company_id": self.company_id.id,
            }))
        return cmds

    def _resolve_generic_contact(self, payload):
        contact_id = self._find_value(payload, "contactId")
        if not contact_id:
            return self.env["res.partner"]
        partner = self._mapped_record("customer", contact_id, "res.partner")
        if partner:
            return partner
        return self._mapped_record("vendor", contact_id, "res.partner")

    def _balanced_entry_lines(self, label, debit_account, credit_account, amount):
        return [
            (0, 0, {"name": label, "account_id": debit_account.id, "debit": amount, "credit": 0.0}),
            (0, 0, {"name": label, "account_id": credit_account.id, "debit": 0.0, "credit": amount}),
        ]

    def _sync_boms(self):
        self.ensure_one()
        try:
            parents = self._fetch_collection("/Products/AssemblyProducts")
        except Exception as exc:  # pylint: disable=broad-except
            self._log("boms", "error", _("Could not fetch assembly products: %s") % exc)
            return
        for parent_payload in parents:
            product_id = self._external_id(parent_payload)
            try:
                components = self._fetch_collection("/Products/%s/Assemblies" % product_id, use_paging=False)
                record = self._import_bom(parent_payload, components)
                self._log("boms", "success", "Imported BOM", parent_payload, product_id, record)
            except Exception as exc:  # pylint: disable=broad-except
                _logger.exception("Failed to import BOM for product %s", product_id)
                self._log("boms", "error", str(exc), parent_payload, product_id)

    def _import_bom(self, parent_payload, components):
        parent_external_id = self._external_id(parent_payload)
        parent_tmpl = self._mapped_record("product", parent_external_id, "product.template")
        if not parent_tmpl:
            parent_tmpl = self._import_products(parent_payload)
        Bom = self.env["mrp.bom"].with_company(self.company_id).sudo()
        bom = Bom.search([("product_tmpl_id", "=", parent_tmpl.id), ("company_id", "in", [False, self.company_id.id])], limit=1)
        line_cmds = [(5, 0, 0)]
        for comp in components:
            if self._find_value(comp, "isInput", default=True) is False:
                continue
            child_external_id = self._find_value(comp, "productId")
            if str(child_external_id) == str(parent_external_id):
                continue
            child_tmpl = self._mapped_record("product", child_external_id, "product.template")
            if not child_tmpl and self._nested(comp, "product"):
                child_tmpl = self._import_products(self._nested(comp, "product"))
            if not child_tmpl:
                continue
            line_cmds.append((0, 0, {"product_id": child_tmpl.product_variant_id.id, "product_qty": float(self._find_value(comp, "quantity", default=1.0) or 1.0)}))
        vals = {
            "product_tmpl_id": parent_tmpl.id,
            "type": "normal",
            "company_id": self.company_id.id,
            "bom_line_ids": line_cmds,
        }
        if bom:
            bom.write(vals)
        else:
            bom = Bom.create(vals)
        self._set_mapping("bom", parent_external_id, bom, parent_payload, parent_tmpl.display_name)
        return bom
