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

    last_master_sync = fields.Datetime(copy=False)
    last_chart_accounts_sync = fields.Datetime(copy=False, string="Last Chart of Accounts Sync")
    last_customers_sync = fields.Datetime(copy=False, string="Last Customers Sync")
    last_vendors_sync = fields.Datetime(copy=False, string="Last Vendors Sync")
    last_products_sync = fields.Datetime(copy=False, string="Last Products Sync")
    last_get_products_sync = fields.Datetime(copy=False, string="Last Get Products Sync")
    last_warehouses_sync = fields.Datetime(copy=False, string="Last Warehouses Sync")
    last_bank_accounts_sync = fields.Datetime(copy=False, string="Last Bank Accounts Sync")
    last_taxes_sync = fields.Datetime(copy=False, string="Last Taxes Sync")

    # Kept for backward compatibility with previous module versions/views/crons.
    last_transaction_sync = fields.Datetime(copy=False)
    last_inventory_sync = fields.Datetime(copy=False)
    last_manufacturing_sync = fields.Datetime(copy=False)
    last_full_sync = fields.Datetime(copy=False)

    chart_accounts_fetched_count = fields.Integer(copy=False, readonly=True)
    chart_accounts_imported_count = fields.Integer(copy=False, readonly=True)
    chart_accounts_failed_count = fields.Integer(copy=False, readonly=True)
    customers_fetched_count = fields.Integer(copy=False, readonly=True)
    customers_imported_count = fields.Integer(copy=False, readonly=True)
    customers_failed_count = fields.Integer(copy=False, readonly=True)
    vendors_fetched_count = fields.Integer(copy=False, readonly=True)
    vendors_imported_count = fields.Integer(copy=False, readonly=True)
    vendors_failed_count = fields.Integer(copy=False, readonly=True)
    products_fetched_count = fields.Integer(copy=False, readonly=True)
    products_imported_count = fields.Integer(copy=False, readonly=True)
    products_failed_count = fields.Integer(copy=False, readonly=True)
    warehouses_fetched_count = fields.Integer(copy=False, readonly=True)
    warehouses_imported_count = fields.Integer(copy=False, readonly=True)
    warehouses_failed_count = fields.Integer(copy=False, readonly=True)
    bank_accounts_fetched_count = fields.Integer(copy=False, readonly=True)
    bank_accounts_imported_count = fields.Integer(copy=False, readonly=True)
    bank_accounts_failed_count = fields.Integer(copy=False, readonly=True)
    taxes_fetched_count = fields.Integer(copy=False, readonly=True)
    taxes_imported_count = fields.Integer(copy=False, readonly=True)
    taxes_failed_count = fields.Integer(copy=False, readonly=True)

    sync_from_date = fields.Date(string="From Date")
    sync_to_date = fields.Date(string="To Date")
    auto_confirm_sale_orders = fields.Boolean(string="Confirm Sale Orders", default=True)
    auto_post_sale_invoices = fields.Boolean(string="Post Sale Invoices / Credit Notes", default=True)
    auto_create_sale_deliveries = fields.Boolean(string="Create Sale Deliveries", default=True)
    auto_validate_sale_deliveries = fields.Boolean(string="Validate Sale Deliveries", default=False)
    auto_create_return_transfers = fields.Boolean(string="Create Return Transfers", default=True)
    auto_validate_return_transfers = fields.Boolean(string="Validate Return Transfers", default=False)
    auto_post_customer_payments = fields.Boolean(string="Post Customer Payments", default=True)
    auto_reconcile_customer_payments = fields.Boolean(string="Reconcile Customer Payments", default=True)

    sale_journal_id = fields.Many2one("account.journal", domain="[('type','=','sale'), ('company_id','=',company_id)]")
    bank_journal_id = fields.Many2one("account.journal", domain="[('type','in',('bank','cash')), ('company_id','=',company_id)]")

    last_sales_process_sync = fields.Datetime(copy=False, string="Last Sales Process Sync")
    last_sale_invoices_sync = fields.Datetime(copy=False, string="Last Sale Invoices Sync")
    last_sale_returns_sync = fields.Datetime(copy=False, string="Last Sale Returns Sync")
    last_customer_payments_sync = fields.Datetime(copy=False, string="Last Customer Payments Sync")

    sale_invoices_fetched_count = fields.Integer(copy=False, readonly=True)
    sale_invoices_imported_count = fields.Integer(copy=False, readonly=True)
    sale_invoices_failed_count = fields.Integer(copy=False, readonly=True)
    sale_returns_fetched_count = fields.Integer(copy=False, readonly=True)
    sale_returns_imported_count = fields.Integer(copy=False, readonly=True)
    sale_returns_failed_count = fields.Integer(copy=False, readonly=True)
    customer_payments_fetched_count = fields.Integer(copy=False, readonly=True)
    customer_payments_imported_count = fields.Integer(copy=False, readonly=True)
    customer_payments_failed_count = fields.Integer(copy=False, readonly=True)

    default_receivable_account_id = fields.Many2one("account.account", domain="[('account_type','=','asset_receivable'), ('deprecated','=',False)]")
    default_payable_account_id = fields.Many2one("account.account", domain="[('account_type','=','liability_payable'), ('deprecated','=',False)]")
    default_income_account_id = fields.Many2one("account.account", domain="[('account_type','in',('income','income_other')), ('deprecated','=',False)]")
    default_expense_account_id = fields.Many2one("account.account", domain="[('account_type','in',('expense','expense_direct_cost')), ('deprecated','=',False)]")
    default_stock_account_id = fields.Many2one("account.account", domain="[('account_type','in',('asset_current','asset_fixed')), ('deprecated','=',False)]")

    log_ids = fields.One2many("splendid.sync.log", "connection_id")
    mapping_ids = fields.One2many("splendid.sync.map", "connection_id")

    MASTER_ENDPOINTS = {
        "chart_accounts": "/Accounts",
        "customers": "/Customers",
        "vendors": "/Vendors",
        "products": "/Products",
        "warehouses": "/api/{tenant}/{branch}/Entities/Warehouses",
        "bank_accounts": "/api/{tenant}/{branch}/BankAccounts",
        "taxes": "/api/{tenant}/Taxes",
    }

    def _with_target_company(self):
        self.ensure_one()
        return self.with_company(self.company_id).with_context(
            allowed_company_ids=[self.company_id.id],
            force_company=self.company_id.id,
        )

    @api.onchange("company_id")
    def _onchange_company_id(self):
        for rec in self:
            rec.default_receivable_account_id = False
            rec.default_payable_account_id = False
            rec.default_income_account_id = False
            rec.default_expense_account_id = False
            rec.default_stock_account_id = False
            rec.sale_journal_id = False
            rec.bank_journal_id = False

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
            lower_keys = {str(k).lower() for k in data.keys()}
            if any(k in lower_keys for k in ("id", "code", "number", "name")):
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

    def _company_partner(self):
        return self.company_id.partner_id

    def _account_company_domain(self):
        account_fields = self.env["account.account"]._fields
        if "company_id" in account_fields:
            return [("company_id", "=", self.company_id.id)]
        if "company_ids" in account_fields:
            return [("company_ids", "in", self.company_id.id)]
        return []

    def _clean_account_code(self, code):
        code = str(code or "").strip()
        code = re.sub(r"[\s\-_/]+", ".", code)
        code = re.sub(r"[^A-Za-z0-9.]", "", code)
        code = re.sub(r"\.+", ".", code).strip(".")
        return code[:64]

    def _clean_product_code(self, value, fallback=False):
        code = str(value or fallback or "").strip()
        if not code:
            return False
        return re.sub(r"\s+", " ", code)[:100]

    def _safe_float(self, value, default=0.0):
        if value in (False, None, ""):
            return default
        if isinstance(value, (int, float)):
            return float(value)
        text = re.sub(r"[^0-9.\-]", "", str(value).strip())
        if text in ("", ".", "-", "-."):
            return default
        try:
            return float(text)
        except ValueError:
            return default

    def _safe_bool(self, value, default=False):
        if value in (False, None, ""):
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        text = str(value).strip().lower()
        if text in ("true", "1", "yes", "y", "active"):
            return True
        if text in ("false", "0", "no", "n", "inactive"):
            return False
        return default

    def _map_search(self, external_model, external_id, odoo_model):
        return self.env["splendid.sync.map"].sudo().search([
            ("connection_id", "=", self.id),
            ("external_model", "=", external_model),
            ("external_id", "=", str(external_id)),
            ("odoo_model", "=", odoo_model),
        ], limit=1)

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
        self.env["splendid.sync.log"].with_company(self.company_id).sudo().create({
            "connection_id": self.id,
            "sync_type": sync_type,
            "state": state,
            "message": message,
            "payload": payload,
            "external_id": str(external_id or ""),
            "odoo_model": record._name if record else False,
            "res_id": record.id if record else False,
        })

    def _set_count(self, key, fetched, imported, failed):
        field_vals = {}
        for suffix, value in (("fetched_count", fetched), ("imported_count", imported), ("failed_count", failed)):
            field_name = "%s_%s" % (key, suffix)
            if field_name in self._fields:
                field_vals[field_name] = value
        if field_vals:
            self.write(field_vals)

    def _search_account_by_external_or_code(self, external_id=False, code=False):
        Account = self.env["account.account"].with_company(self.company_id).sudo()
        domain_company = self._account_company_domain()
        if external_id not in (False, None, ""):
            account = Account.search([("splendid_account_id", "=", str(external_id))] + domain_company, limit=1)
            if account:
                return account
            mapped = self._mapped_record("account", external_id, "account.account")
            if mapped:
                return mapped
        code = self._clean_account_code(code)
        if code:
            account = Account.search([("code", "=", code)] + domain_company, limit=1)
            if account:
                return account
        return Account

    def _resolve_account(self, external_id=False, code=False):
        account = self._search_account_by_external_or_code(external_id, code)
        if account:
            return account
        if external_id:
            try:
                payload = self._api_request("GET", "/Accounts/%s" % external_id)
                rows = self._extract_list(payload)
                if rows:
                    return self._import_chart_accounts(rows[0])
                if isinstance(payload, dict) and payload:
                    return self._import_chart_accounts(payload)
            except Exception as exc:  # pylint: disable=broad-except
                _logger.warning("Could not fetch Splendid account %s: %s", external_id, exc)
        return account

    def _default_account(self, kind):
        account = {
            "income": self.default_income_account_id,
            "expense": self.default_expense_account_id,
            "receivable": self.default_receivable_account_id,
            "payable": self.default_payable_account_id,
            "stock": self.default_stock_account_id,
        }.get(kind)
        if account:
            return account
        type_map = {
            "income": ("income", "income_other"),
            "expense": ("expense", "expense_direct_cost"),
            "receivable": ("asset_receivable",),
            "payable": ("liability_payable",),
            "stock": ("asset_current", "asset_fixed"),
        }
        domain = [("deprecated", "=", False), ("account_type", "in", type_map.get(kind, ("asset_current",)))] + self._account_company_domain()
        account = self.env["account.account"].with_company(self.company_id).sudo().search(domain, limit=1)
        return account

    def action_test_connection(self):
        for rec in self:
            rec = rec._with_target_company()
            data = rec._api_request("GET", "/Accounts", params={"page": 1, "size": 1})
            rec.message_post(body=_("Splendid connection successful. Response preview: %s") % json.dumps(data, default=str)[:500])
        return True

    def action_sync_masters(self):
        for rec in self:
            rec = rec._with_target_company()
            rec._sync_masters()
        return True

    def action_get_products(self):
        for rec in self:
            rec = rec._with_target_company()
            rec._sync_master_model("products")
            rec.last_get_products_sync = fields.Datetime.now()
        return True

    def action_sync_sales_process(self):
        for rec in self:
            rec = rec._with_target_company()
            rec._sync_sales_process()
        return True

    def action_sync_sale_invoices(self):
        for rec in self:
            rec = rec._with_target_company()
            rec._sync_sale_invoices()
        return True

    def action_sync_sale_returns(self):
        for rec in self:
            rec = rec._with_target_company()
            rec._sync_sale_returns()
        return True

    def action_sync_customer_payments(self):
        for rec in self:
            rec = rec._with_target_company()
            rec._sync_customer_payments()
        return True

    # Backward-compatible methods. These no longer sync transactions or inventory.
    def action_sync_transactions(self):
        raise UserError(_("Transaction sync has been removed from this master-data-only version. Use Sync Master Data."))

    def action_sync_inventory(self):
        raise UserError(_("Inventory sync has been removed from this master-data-only version. Use Sync Master Data."))

    def action_sync_manufacturing(self):
        raise UserError(_("Manufacturing sync has been removed from this master-data-only version. Use Sync Master Data."))

    def action_sync_all(self):
        return self.action_sync_masters()

    @api.model
    def cron_sync_all_active(self):
        for connection in self.search([("active", "=", True)]):
            try:
                connection._with_target_company()._sync_masters()
            except Exception as exc:  # pylint: disable=broad-except
                _logger.exception("Splendid cron failed for %s", connection.display_name)
                connection._log("cron", "error", str(exc))

    def _sync_masters(self):
        self.ensure_one()
        for key in ("chart_accounts", "customers", "vendors", "products", "warehouses", "bank_accounts", "taxes"):
            self._sync_master_model(key)
        self.last_master_sync = fields.Datetime.now()
        self.env.cr.commit()

    def _sync_master_model(self, key):
        self.ensure_one()
        endpoint = self.MASTER_ENDPOINTS.get(key)
        if not endpoint:
            raise UserError(_("No Splendid endpoint configured for %s") % key)
        importer = getattr(self, "_import_%s" % key, None)
        if not importer:
            raise UserError(_("No importer defined for %s") % key)
        params = self._params_for_master(key)
        rows = self._fetch_collection(endpoint, params=params, use_paging=True)
        imported = 0
        failed = 0
        for payload in rows:
            external_id = self._external_id(payload)
            try:
                record = importer(payload)
                imported += 1
                self._log(key, "success", "Imported/Updated", payload, external_id, record)
            except Exception as exc:  # pylint: disable=broad-except
                failed += 1
                _logger.exception("Failed to import Splendid %s/%s", key, external_id)
                self._log(key, "error", str(exc), payload, external_id)
        self._set_count(key, len(rows), imported, failed)
        last_field = "last_%s_sync" % key
        if last_field in self._fields:
            self.write({last_field: fields.Datetime.now()})
        if key == "products":
            self.last_get_products_sync = fields.Datetime.now()
        self.env.cr.commit()
        return True

    def _params_for_master(self, key):
        base = {"orderBy": "Id", "ascending": "true"}
        if key in ("products",):
            base["showOpening"] = "false"
        return base

    def _import_chart_accounts(self, payload):
        external_id = self._external_id(payload)
        raw_code = self._find_value(payload, "code", "number", "accountCode", "accountNumber", "accountNo")
        code = self._clean_account_code(raw_code or external_id)
        if not code:
            raise UserError(_("Missing account code for Splendid account %s") % external_id)
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
        account = self._mapped_record("account", external_id, "account.account")
        if not account:
            account = self._search_account_by_external_or_code(external_id, code)
        if account:
            account.write(vals)
        else:
            account = self.env["account.account"].with_company(self.company_id).sudo().create(vals)
        self._set_mapping("account", external_id, account, payload, name)
        return account

    def _map_account_type(self, payload):
        text = " ".join(str(x or "") for x in (
            self._find_value(payload, "accountType", "accountTypeId"),
            self._find_value(payload, "accountClass"),
            self._find_value(payload, "accountGroup"),
            self._find_value(payload, "name"),
            self._find_value(payload, "code"),
        )).lower()
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
        partner = self._mapped_record(model_key, external_id, "res.partner")
        name = self._find_value(payload, "name", "displayName", "printName", "contactPerson") or _("Splendid Contact %s") % external_id
        vals = {
            "name": name,
            "street": self._find_value(payload, "address1", "address"),
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
            account = self._resolve_account(self._find_value(payload, "accountId")) or self.default_receivable_account_id
            if account and account.account_type == "asset_receivable":
                vals["property_account_receivable_id"] = account.id
        else:
            vals.update({"supplier_rank": 1, "splendid_vendor_id": external_id})
            account = self._resolve_account(self._find_value(payload, "accountId")) or self.default_payable_account_id
            if account and account.account_type == "liability_payable":
                vals["property_account_payable_id"] = account.id
        vals = {k: v for k, v in vals.items() if v not in (False, None)}
        if not partner:
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

    def _product_external_id(self, payload):
        value = self._find_value(payload, "id", "Id", "productId", "ProductId", "productID", "externalId", "sourceId")
        if value in (False, None, ""):
            value = self._find_value(payload, "sku", "code", "number", "barcode", "name")
        return str(value or "")

    def _import_products(self, payload):
        external_id = self._product_external_id(payload)
        product = self._mapped_record("product", external_id, "product.template")
        name = self._find_value(payload, "name", "displayName", "shortName", "sku", "code") or _("Splendid Product %s") % external_id
        sku = self._clean_product_code(self._find_value(payload, "sku", "code", "number"), fallback=external_id)
        if not sku:
            sku = self._clean_product_code(name, fallback=external_id)
        vals = {
            "name": str(name)[:1000],
            "default_code": sku,
            "list_price": self._safe_float(self._find_value(payload, "salePrice", "maximumRetailPrice"), 0.0),
            "standard_price": self._safe_float(self._find_value(payload, "purchasePrice", "averageCost"), 0.0),
            "splendid_product_id": external_id,
            "splendid_is_imported": True,
        }
        if "sale_ok" in self.env["product.template"]._fields:
            vals["sale_ok"] = self._safe_bool(self._find_value(payload, "isForSale"), True)
        if "purchase_ok" in self.env["product.template"]._fields:
            vals["purchase_ok"] = self._safe_bool(self._find_value(payload, "isForPurchase"), True)
        if "company_id" in self.env["product.template"]._fields:
            vals["company_id"] = self.company_id.id
        vals.update(self._product_type_vals(payload))
        barcode = self._safe_barcode(self._find_value(payload, "barcode"), product=product)
        if barcode and "barcode" in self.env["product.template"]._fields:
            vals["barcode"] = barcode
        description = self._find_value(payload, "description", "shortDescription", "catalogContent")
        if description:
            vals["description_sale"] = description
            vals["description_purchase"] = description
        income_account = self._resolve_account(self._find_value(payload, "salesAccountId"))
        expense_account = self._resolve_account(self._find_value(payload, "expenseAccountId"))
        if income_account and "property_account_income_id" in self.env["product.template"]._fields:
            vals["property_account_income_id"] = income_account.id
        if expense_account and "property_account_expense_id" in self.env["product.template"]._fields:
            vals["property_account_expense_id"] = expense_account.id
        if not product:
            domain = [("default_code", "=", sku)]
            if "company_id" in self.env["product.template"]._fields:
                domain = ["&"] + domain + ["|", ("company_id", "=", False), ("company_id", "=", self.company_id.id)]
            product = self.env["product.template"].with_company(self.company_id).sudo().search(domain, limit=1)
        if product:
            product.write(vals)
        else:
            product = self.env["product.template"].with_company(self.company_id).sudo().create(vals)
        self._set_mapping("product", external_id, product, payload, name)
        return product

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
        product_model = self.env["product.template"]
        vals = {}
        text = " ".join(str(x or "") for x in (
            self._find_value(payload, "type"),
            self._find_value(payload, "productType"),
            self._find_value(payload, "itemType"),
            self._find_value(payload, "category"),
            self._find_value(payload, "productCategoryName"),
        )).lower()
        is_service = "service" in text
        is_combo = any(word in text for word in ("combo", "bundle", "kit", "assembly")) or self._safe_bool(self._find_value(payload, "hasProductBreakup"), False)
        track_inventory = self._safe_bool(self._find_value(payload, "trackInventory"), False)
        odoo_type = "service" if is_service else ("combo" if is_combo else "consu")
        if "type" in product_model._fields:
            if self._selection_has_value(product_model, "type", odoo_type):
                vals["type"] = odoo_type
            elif self._selection_has_value(product_model, "type", "consu"):
                vals["type"] = "consu"
        if "detailed_type" in product_model._fields:
            if self._selection_has_value(product_model, "detailed_type", odoo_type):
                vals["detailed_type"] = odoo_type
            elif self._selection_has_value(product_model, "detailed_type", "consu"):
                vals["detailed_type"] = "consu"
        if "is_storable" in product_model._fields:
            vals["is_storable"] = bool(track_inventory and not is_service)
        return vals

    def _safe_barcode(self, value, product=False):
        barcode = str(value or "").strip()
        if not barcode:
            return False
        barcode = barcode[:64]
        Product = self.env["product.template"].with_company(self.company_id).sudo()
        domain = [("barcode", "=", barcode)]
        if product:
            domain.append(("id", "!=", product.id))
        if Product.search(domain, limit=1):
            return False
        return barcode

    def _import_warehouses(self, payload):
        external_id = self._external_id(payload)
        warehouse = self._mapped_record("warehouse", external_id, "stock.warehouse")
        name = self._find_value(payload, "name", "displayName", "code") or _("Splendid Warehouse %s") % external_id
        code_source = str(self._find_value(payload, "code", "number") or name or external_id).upper()
        code = "".join(ch for ch in code_source if ch.isalnum())[:5] or ("SP%s" % external_id)[-5:]
        Warehouse = self.env["stock.warehouse"].with_company(self.company_id).sudo()
        if not warehouse:
            warehouse = Warehouse.search([("company_id", "=", self.company_id.id), "|", ("name", "=", name), ("code", "=", code)], limit=1)
        if not warehouse:
            original_code = code
            seq = 1
            while Warehouse.search([("company_id", "=", self.company_id.id), ("code", "=", code)], limit=1):
                code = (original_code[:3] + str(seq))[:5]
                seq += 1
            warehouse = Warehouse.create({"name": name, "code": code, "company_id": self.company_id.id})
        else:
            warehouse.write({"name": name})
        if "splendid_warehouse_id" in warehouse._fields:
            warehouse.write({"splendid_warehouse_id": external_id, "splendid_is_imported": True})
        self._set_mapping("warehouse", external_id, warehouse, payload, name)
        return warehouse

    def _import_bank_accounts(self, payload):
        external_id = self._external_id(payload)
        Journal = self.env["account.journal"].with_company(self.company_id).sudo()
        journal = Journal.search([("company_id", "=", self.company_id.id), ("splendid_bank_account_id", "=", external_id)], limit=1)
        bank_name = self._find_value(payload, "bankName") or "Bank"
        account_title = self._find_value(payload, "accountTitle") or bank_name
        account_number = self._find_value(payload, "accountNumber")
        display_name = "%s - %s" % (bank_name, account_title)
        default_account = self._resolve_account(self._find_value(payload, "accountId"), self._find_value(payload, "code"))
        if not journal and account_number:
            journal = Journal.search([("company_id", "=", self.company_id.id), ("bank_acc_number", "=", account_number)], limit=1)
        vals = {
            "name": display_name[:100],
            "type": "bank",
            "code": self._unique_journal_code(self._find_value(payload, "code") or bank_name, journal=journal),
            "company_id": self.company_id.id,
            "splendid_bank_account_id": external_id,
            "splendid_bank_account_account_id": str(self._find_value(payload, "accountId") or ""),
            "splendid_is_imported": True,
        }
        if default_account and "default_account_id" in Journal._fields:
            vals["default_account_id"] = default_account.id
        bank_account = self._get_or_create_partner_bank(payload)
        if bank_account and "bank_account_id" in Journal._fields:
            vals["bank_account_id"] = bank_account.id
        if journal:
            journal.write(vals)
        else:
            journal = Journal.create(vals)
        self._set_mapping("bank_account", external_id, journal, payload, display_name)
        return journal

    def _unique_journal_code(self, source, journal=False):
        base = "".join(ch for ch in str(source or "BNK").upper() if ch.isalnum())[:5] or "BNK"
        Journal = self.env["account.journal"].with_company(self.company_id).sudo()
        code = base
        seq = 1
        while Journal.search([("company_id", "=", self.company_id.id), ("code", "=", code), ("id", "!=", journal.id if journal else 0)], limit=1):
            suffix = str(seq)
            code = (base[: max(1, 5 - len(suffix))] + suffix)[:5]
            seq += 1
        return code

    def _get_or_create_partner_bank(self, payload):
        account_number = self._find_value(payload, "accountNumber")
        if not account_number:
            return self.env["res.partner.bank"]
        Bank = self.env["res.bank"].sudo()
        PartnerBank = self.env["res.partner.bank"].sudo()
        bank_name = self._find_value(payload, "bankName")
        bank = Bank.search([("name", "=", bank_name)], limit=1) if bank_name else Bank
        if not bank and bank_name:
            bank = Bank.create({"name": bank_name})
        bank_account = PartnerBank.search([("acc_number", "=", account_number)], limit=1)
        vals = {"acc_number": account_number, "partner_id": self._company_partner().id}
        if bank:
            vals["bank_id"] = bank.id
        if "company_id" in PartnerBank._fields:
            vals["company_id"] = self.company_id.id
        if bank_account:
            bank_account.write(vals)
        else:
            bank_account = PartnerBank.create(vals)
        return bank_account

    def _get_tax_country_id(self):
            self.ensure_one()
            country = self.company_id.account_fiscal_country_id or self.company_id.country_id
            if not country:
                raise UserError(_("Please set Country / Fiscal Country on company %s before syncing taxes.") % self.company_id.display_name)
            return country.id


    def _import_taxes(self, payload):
        self.ensure_one()

        external_id = self._external_id(payload)
        name = self._find_value(payload, "name", "abbreviation") or _("Splendid Tax %s") % external_id
        abbreviation = self._find_value(payload, "abbreviation")
        rate = self._safe_float(self._find_value(payload, "rate"), 0.0)
        active = self._safe_bool(self._find_value(payload, "isActive"), True)
        tax_country_id = self._get_tax_country_id()

        created_taxes = self.env["account.tax"].with_company(self.company_id).sudo()

        tax_defs = []

        if self._safe_bool(self._find_value(payload, "out"), False):
            tax_defs.append({
                "tax_use": "sale",
                "name": "%s (Sale)" % name,
                "account_id": self._find_value(payload, "accountOutId"),
            })

        if self._safe_bool(self._find_value(payload, "in"), False):
            tax_defs.append({
                "tax_use": "purchase",
                "name": "%s (Purchase)" % name,
                "account_id": self._find_value(payload, "accountInId"),
            })

        if not tax_defs:
            tax_defs.append({
                "tax_use": "none",
                "name": name,
                "account_id": False,
            })

        Tax = self.env["account.tax"].with_company(self.company_id).sudo()

        for tax_def in tax_defs:
            tax_use = tax_def["tax_use"]

            domain = [
                ("company_id", "=", self.company_id.id),
                ("splendid_tax_id", "=", str(external_id)),
                ("splendid_tax_use", "=", tax_use),
            ]

            tax = Tax.search(domain, limit=1)

            vals = {
                "name": tax_def["name"],
                "amount": rate,
                "amount_type": "percent",
                "type_tax_use": tax_use,
                "active": active,
                "company_id": self.company_id.id,
                "country_id": tax_country_id,
                "splendid_tax_id": str(external_id),
                "splendid_tax_use": tax_use,
                "splendid_tax_direction": tax_use if tax_use in ("sale", "purchase") else False,
                "splendid_is_imported": True,
            }

            if tax:
                tax.write(vals)
            else:
                tax = Tax.create(vals)

            self._set_mapping(
                "tax",
                "%s_%s" % (external_id, tax_use),
                tax,
                payload,
                tax_def["name"],
            )

            created_taxes |= tax

        return created_taxes[:1]
    def _upsert_tax(self, payload, direction):
        external_id = self._external_id(payload)
        Tax = self.env["account.tax"].with_company(self.company_id).sudo()
        tax = Tax.search([
            ("company_id", "=", self.company_id.id),
            ("splendid_tax_id", "=", external_id),
            ("splendid_tax_direction", "=", direction),
        ], limit=1)
        base_name = self._find_value(payload, "name", "abbreviation") or _("Splendid Tax %s") % external_id
        suffix = "Sale" if direction == "sale" else "Purchase"
        account_id = self._find_value(payload, "accountOutId" if direction == "sale" else "accountInId")
        account = self._resolve_account(account_id)
        vals = {
            "name": "%s (%s)" % (base_name, suffix),
            "amount": self._safe_float(self._find_value(payload, "rate"), 0.0),
            "amount_type": "percent",
            "type_tax_use": direction,
            "company_id": self.company_id.id,
            "active": self._safe_bool(self._find_value(payload, "isActive"), True),
            "splendid_tax_id": external_id,
            "splendid_tax_direction": direction,
            "splendid_is_imported": True,
        }
        if tax:
            tax.write(vals)
        else:
            tax = Tax.create(vals)
        if account:
            self._set_tax_account(tax, account)
        self._set_mapping("tax_%s" % direction, external_id, tax, payload, vals["name"])
        return tax

    def _set_tax_account(self, tax, account):
        for field_name in ("invoice_repartition_line_ids", "refund_repartition_line_ids"):
            lines = getattr(tax, field_name, False)
            if not lines:
                continue
            for line in lines.filtered(lambda l: getattr(l, "repartition_type", False) == "tax"):
                try:
                    line.account_id = account.id
                except Exception:  # pylint: disable=broad-except
                    _logger.debug("Could not set tax repartition account for %s", tax.display_name)
        return True

    # -------------------------------------------------------------------------
    # Sales process sync: Splendid sale invoices -> Sale Orders, Deliveries,
    # Customer Invoices, Returns, Credit Notes and Customer Payments.
    # -------------------------------------------------------------------------

    def _parse_date(self, value):
        if not value:
            return fields.Date.context_today(self)
        if isinstance(value, datetime):
            return value.date()
        text = str(value).replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(text).date()
        except ValueError:
            return text[:10]

    def _parse_datetime(self, value):
        if not value:
            return fields.Datetime.now()
        if isinstance(value, datetime):
            return value.replace(tzinfo=None)
        text = str(value).replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(text).replace(tzinfo=None)
        except ValueError:
            return fields.Datetime.now()

    def _default_sale_journal(self):
        self.ensure_one()
        journal = self.sale_journal_id
        if not journal:
            journal = self.env["account.journal"].with_company(self.company_id).sudo().search([
                ("company_id", "=", self.company_id.id),
                ("type", "=", "sale"),
            ], limit=1)
        if not journal:
            raise UserError(_("Please configure a Sales Journal for Splendid sales sync."))
        return journal

    def _default_bank_journal(self):
        self.ensure_one()
        journal = self.bank_journal_id
        if not journal:
            journal = self.env["account.journal"].with_company(self.company_id).sudo().search([
                ("company_id", "=", self.company_id.id),
                ("type", "in", ("bank", "cash")),
            ], limit=1)
        if not journal:
            raise UserError(_("Please configure a Bank/Cash Journal for Splendid customer payments."))
        return journal

    def _date_range_payload(self):
        self.ensure_one()
        payload = {}
        if self.sync_from_date or self.sync_to_date:
            date_filter = {}
            if self.sync_from_date:
                date_filter["from"] = "%sT00:00:00" % fields.Date.to_string(self.sync_from_date)
            if self.sync_to_date:
                date_filter["to"] = "%sT23:59:59" % fields.Date.to_string(self.sync_to_date)
            payload["date"] = date_filter
        return payload

    def _fetch_search_collection(self, endpoint, filter_payload=None, params=None):
        self.ensure_one()
        all_rows = []
        page = 1
        size = self.page_size or 100
        while True:
            request_params = {
                "page": page,
                "size": size,
                "orderBy": "Date",
                "ascending": "true",
            }
            request_params.update(params or {})
            data = self._api_request("POST", endpoint, params=request_params, payload=filter_payload or {})
            rows = self._extract_list(data)
            all_rows.extend(rows)
            if len(rows) < size or not rows:
                break
            page += 1
            if page > 10000:
                raise UserError(_("Paging stopped after 10,000 pages for endpoint %s") % endpoint)
        return all_rows

    def _fetch_sales_list(self, key):
        endpoints = {
            "sale_invoices": ("/SaleInvoices", "/SaleInvoices/Search"),
            "sale_returns": ("/SaleReturns", "/SaleReturns/Search"),
            "customer_payments": ("/CustomerPayments", "/CustomerPayments/Search"),
        }
        endpoint, search_endpoint = endpoints[key]
        date_payload = self._date_range_payload()
        if date_payload:
            return self._fetch_search_collection(search_endpoint, filter_payload=date_payload)
        return self._fetch_collection(endpoint, params={"orderBy": "Date", "ascending": "true"}, use_paging=True)

    def _fetch_detail_by_id(self, endpoint, external_id):
        data = self._api_request("GET", "%s/%s" % (endpoint.rstrip("/"), external_id))
        if isinstance(data, dict):
            return data
        rows = self._extract_list(data)
        return rows[0] if rows else {}

    def _sync_sales_process(self):
        self.ensure_one()
        self._sync_sale_invoices()
        self._sync_sale_returns()
        self._sync_customer_payments()
        self.last_sales_process_sync = fields.Datetime.now()
        self.env.cr.commit()
        return True

    def _sync_sale_invoices(self):
        self.ensure_one()
        rows = self._fetch_sales_list("sale_invoices")
        imported = failed = 0
        for row in rows:
            external_id = self._external_id(row)
            try:
                payload = self._fetch_detail_by_id("/SaleInvoices", external_id)
                record = self._import_sale_invoice_process(payload)
                imported += 1
                self._log("sale_invoices", "success", "Sale invoice process imported/updated", payload, external_id, record)
                self._sync_customer_payments_from_invoice(payload)
            except Exception as exc:  # pylint: disable=broad-except
                failed += 1
                _logger.exception("Failed to import Splendid sale invoice %s", external_id)
                self._log("sale_invoices", "error", str(exc), row, external_id)
        self._set_count("sale_invoices", len(rows), imported, failed)
        self.last_sale_invoices_sync = fields.Datetime.now()
        self.env.cr.commit()
        return True

    def _sync_sale_returns(self):
        self.ensure_one()
        rows = self._fetch_sales_list("sale_returns")
        imported = failed = 0
        for row in rows:
            external_id = self._external_id(row)
            try:
                payload = self._fetch_detail_by_id("/SaleReturns", external_id)
                record = self._import_sale_return_process(payload)
                imported += 1
                self._log("sale_returns", "success", "Sale return imported/updated", payload, external_id, record)
            except Exception as exc:  # pylint: disable=broad-except
                failed += 1
                _logger.exception("Failed to import Splendid sale return %s", external_id)
                self._log("sale_returns", "error", str(exc), row, external_id)
        self._set_count("sale_returns", len(rows), imported, failed)
        self.last_sale_returns_sync = fields.Datetime.now()
        self.env.cr.commit()
        return True

    def _sync_customer_payments(self):
        self.ensure_one()
        rows = self._fetch_sales_list("customer_payments")
        imported = failed = 0
        for row in rows:
            external_id = self._external_id(row)
            try:
                payload = self._fetch_detail_by_id("/CustomerPayments", external_id)
                record = self._import_customer_payment_process(payload)
                imported += 1
                self._log("customer_payments", "success", "Customer payment imported/updated", payload, external_id, record)
            except Exception as exc:  # pylint: disable=broad-except
                failed += 1
                _logger.exception("Failed to import Splendid customer payment %s", external_id)
                self._log("customer_payments", "error", str(exc), row, external_id)
        self._set_count("customer_payments", len(rows), imported, failed)
        self.last_customer_payments_sync = fields.Datetime.now()
        self.env.cr.commit()
        return True

    def _sync_customer_payments_from_invoice(self, invoice_payload):
        for item in self._find_value(invoice_payload, "customerSingleSettledEntryItems", default=[]) or []:
            if not isinstance(item, dict):
                continue
            if str(self._find_value(item, "source", default="")).lower() != "customerpayment":
                continue
            payment_id = self._find_value(item, "sourceId")
            if not payment_id:
                continue
            if self._mapped_record("customer_payment", payment_id, "account.payment"):
                continue
            try:
                payment_payload = self._fetch_detail_by_id("/CustomerPayments", payment_id)
                payment = self._import_customer_payment_process(payment_payload)
                self._log("customer_payments", "success", "Customer payment imported from sale invoice settlement", payment_payload, payment_id, payment)
            except Exception as exc:  # pylint: disable=broad-except
                self._log("customer_payments", "error", str(exc), item, payment_id)

    def _resolve_customer(self, payload):
        external_id = self._find_value(payload, "customerId")
        partner = self._mapped_record("customer", external_id, "res.partner") if external_id else self.env["res.partner"]
        if partner:
            return partner
        nested = self._nested(payload, "customer")
        if nested:
            return self._import_partner(nested, "customer")
        raise UserError(_("Customer could not be resolved for Splendid record %s") % self._external_id(payload))

    def _resolve_product_from_line(self, line):
        external_id = self._find_value(line, "productId", "ProductId", "itemId", "productID")
        product = self._mapped_record("product", external_id, "product.template") if external_id else self.env["product.template"]
        if product:
            return product
        nested = self._nested(line, "product") or self._nested(line, "item")
        if nested:
            return self._import_products(nested)
        sku = self._clean_product_code(self._find_value(line, "sku", "productCode", "code", "barcode"))
        if sku:
            domain = [("default_code", "=", sku)]
            if "company_id" in self.env["product.template"]._fields:
                domain = ["&"] + domain + ["|", ("company_id", "=", False), ("company_id", "=", self.company_id.id)]
            product = self.env["product.template"].with_company(self.company_id).sudo().search(domain, limit=1)
            if product:
                return product
        raise UserError(_("Product could not be resolved for Splendid line %s") % (self._find_value(line, "id") or ""))

    def _resolve_warehouse(self, payload=None, warehouse_id=False):
        payload = payload or {}
        external_id = warehouse_id or self._find_value(payload, "warehouseId", "warehouseID")
        warehouse = self._mapped_record("warehouse", external_id, "stock.warehouse") if external_id else self.env["stock.warehouse"]
        if warehouse:
            return warehouse
        nested = self._nested(payload, "warehouse")
        if nested:
            return self._import_warehouses(nested)
        warehouse = self.env["stock.warehouse"].with_company(self.company_id).sudo().search([
            ("company_id", "=", self.company_id.id)
        ], limit=1)
        if not warehouse:
            raise UserError(_("Please configure at least one warehouse for company %s") % self.company_id.display_name)
        return warehouse

    def _warehouse_customer_location(self):
        loc = self.env.ref("stock.stock_location_customers", raise_if_not_found=False)
        if not loc:
            loc = self.env["stock.location"].sudo().search([("usage", "=", "customer")], limit=1)
        if not loc:
            raise UserError(_("Customer stock location was not found."))
        return loc

    def _line_discount_percent(self, line):
        discount = self._find_value(line, "discountInPercent")
        if discount not in (False, None, ""):
            return self._safe_float(discount)
        qty = self._safe_float(self._find_value(line, "quantity"), 1.0) or 1.0
        price = self._safe_float(self._find_value(line, "price", "tagPrice"), 0.0)
        gross = self._safe_float(self._find_value(line, "grossAmount"), 0.0)
        disc_amt = self._safe_float(self._find_value(line, "discountAmount"), 0.0)
        base = gross or qty * price
        return (disc_amt / base * 100.0) if base and disc_amt else 0.0

    def _resolve_taxes_from_line(self, line, direction="sale"):
        taxes = self.env["account.tax"].with_company(self.company_id).sudo()
        raw_taxes = self._find_value(line, "taxes", default=[]) or []
        for item in raw_taxes:
            tax_id = self._find_value(item, "taxId", "id") if isinstance(item, dict) else item
            if not tax_id:
                continue
            tax = self._mapped_record("tax", "%s_%s" % (tax_id, direction), "account.tax")
            if not tax:
                tax = self.env["account.tax"].with_company(self.company_id).sudo().search([
                    ("company_id", "=", self.company_id.id),
                    ("splendid_tax_id", "=", str(tax_id)),
                    ("type_tax_use", "=", direction),
                ], limit=1)
            taxes |= tax
        return taxes

    def _resolve_line_account(self, line, product_tmpl, fallback_kind="income"):
        account_id = self._find_value(line, "accountId")
        account_code = self._find_value(self._nested(line, "account"), "code")
        account = self._resolve_account(account_id, account_code)
        if account:
            return account
        if product_tmpl:
            product = product_tmpl.product_variant_id
            if fallback_kind == "income":
                account = product.property_account_income_id or product.categ_id.property_account_income_categ_id
            else:
                account = product.property_account_expense_id or product.categ_id.property_account_expense_categ_id
            if account:
                return account
        account = self._default_account(fallback_kind)
        if not account:
            raise UserError(_("No %s account found/configured for Splendid transaction line.") % fallback_kind)
        return account

    def _sale_order_line_vals(self, line):
        product_tmpl = self._resolve_product_from_line(line)
        product = product_tmpl.product_variant_id
        taxes = self._resolve_taxes_from_line(line, "sale")
        vals = {
            "product_id": product.id,
            "name": self._find_value(line, "description") or product.display_name,
            "product_uom_qty": self._safe_float(self._find_value(line, "quantity"), 1.0),
            "price_unit": self._safe_float(self._find_value(line, "price", "tagPrice"), 0.0),
            "discount": self._line_discount_percent(line),
            "product_uom": product.uom_id.id,
        }
        if taxes:
            vals["tax_id"] = [(6, 0, taxes.ids)]
        return vals

    def _invoice_line_vals_from_sale_line(self, line, sale_line=False, move_type="out_invoice"):
        product_tmpl = self._resolve_product_from_line(line)
        product = product_tmpl.product_variant_id
        taxes = self._resolve_taxes_from_line(line, "sale")
        account = self._resolve_line_account(line, product_tmpl, "income")
        vals = {
            "product_id": product.id,
            "name": self._find_value(line, "description") or product.display_name,
            "quantity": self._safe_float(self._find_value(line, "quantity"), 1.0),
            "price_unit": self._safe_float(self._find_value(line, "price", "tagPrice"), 0.0),
            "discount": self._line_discount_percent(line),
            "account_id": account.id,
        }
        if taxes:
            vals["tax_ids"] = [(6, 0, taxes.ids)]
        if sale_line and "sale_line_ids" in self.env["account.move.line"]._fields:
            vals["sale_line_ids"] = [(6, 0, [sale_line.id])]
        return vals

    def _sale_invoice_details(self, payload):
        details = self._find_value(payload, "saleInvoiceDetails", default=[]) or []
        return details if isinstance(details, list) else []

    def _sale_return_details(self, payload):
        details = self._find_value(payload, "saleReturnDetails", default=[]) or []
        return details if isinstance(details, list) else []

    def _prepare_sale_order(self, payload):
        external_id = self._external_id(payload)
        order = self._mapped_record("sale_invoice_order", external_id, "sale.order")
        if order:
            return order
        partner = self._resolve_customer(payload)
        details = self._sale_invoice_details(payload)
        if not details:
            raise UserError(_("No sale invoice lines found for Splendid invoice %s") % external_id)
        first_warehouse = self._resolve_warehouse(details[0]) if details else False
        order_vals = {
            "partner_id": partner.id,
            "date_order": self._parse_datetime(self._find_value(payload, "date")),
            "origin": self._find_value(payload, "number") or external_id,
            "client_order_ref": self._find_value(payload, "reference") or self._find_value(payload, "number") or external_id,
            "company_id": self.company_id.id,
            "order_line": [(0, 0, self._sale_order_line_vals(line)) for line in details],
            "splendid_sale_invoice_id": external_id,
            "splendid_sale_invoice_number": self._find_value(payload, "number"),
            "splendid_is_imported": True,
        }
        if first_warehouse and "warehouse_id" in self.env["sale.order"]._fields:
            order_vals["warehouse_id"] = first_warehouse.id
        order = self.env["sale.order"].with_company(self.company_id).sudo().create(order_vals)
        self._set_mapping("sale_invoice_order", external_id, order, payload, order.name)
        if self.auto_confirm_sale_orders and order.state in ("draft", "sent"):
            order.action_confirm()
        if self.auto_create_sale_deliveries:
            self._mark_sale_delivery_from_order(order, payload)
        return order

    def _mark_sale_delivery_from_order(self, order, payload):
        external_id = self._external_id(payload)
        pickings = order.picking_ids.filtered(lambda p: p.state != "cancel") if "picking_ids" in order._fields else self.env["stock.picking"]
        for picking in pickings:
            vals = {
                "splendid_sale_invoice_id": external_id,
                "splendid_source_model": "sale_invoice_delivery",
                "splendid_is_imported": True,
            }
            if "splendid_raw_payload" in picking._fields:
                vals["splendid_raw_payload"] = payload
            picking.sudo().write(vals)
            self._set_mapping("sale_invoice_delivery", "%s_%s" % (external_id, picking.id), picking, payload, picking.name)
            if self.auto_validate_sale_deliveries:
                self._validate_picking(picking)
        return pickings

    def _validate_picking(self, picking):
        if not picking or picking.state in ("done", "cancel"):
            return False
        if picking.state == "draft":
            picking.action_confirm()
        try:
            picking.action_assign()
        except Exception:  # pylint: disable=broad-except
            pass
        for move in picking.move_ids.filtered(lambda m: m.state not in ("done", "cancel")):
            qty = move.product_uom_qty
            if "quantity" in move._fields:
                move.quantity = qty
            elif "quantity_done" in move._fields:
                move.quantity_done = qty
        picking.button_validate()
        return True

    def _get_or_create_discount_product(self):
        self.ensure_one()

        Product = self.env["product.template"].with_company(self.company_id).sudo()

        # Pehle existing Discount product find karo.
        domain = [
            "|",
            ("default_code", "=", "DISCOUNT"),
            ("name", "=", "Discount"),
        ]

        if "company_id" in Product._fields:
            domain = [
                "&",
                "|",
                ("company_id", "=", False),
                ("company_id", "=", self.company_id.id),
            ] + domain

        product_tmpl = Product.search(domain, limit=1)
        if product_tmpl:
            vals = {}

            # Ensure product is service type.
            if "type" in Product._fields:
                vals["type"] = "service"

            if "detailed_type" in Product._fields:
                vals["detailed_type"] = "service"

            if "sale_ok" in Product._fields:
                vals["sale_ok"] = True

            if "purchase_ok" in Product._fields:
                vals["purchase_ok"] = False

            if vals:
                product_tmpl.write(vals)

            return product_tmpl

        vals = {
            "name": "Discount",
            "default_code": "DISCOUNT",
            "list_price": 0.0,
            "standard_price": 0.0,
        }

        if "sale_ok" in Product._fields:
            vals["sale_ok"] = True

        if "purchase_ok" in Product._fields:
            vals["purchase_ok"] = False

        if "type" in Product._fields:
            vals["type"] = "service"

        if "detailed_type" in Product._fields:
            vals["detailed_type"] = "service"

        if "company_id" in Product._fields:
            vals["company_id"] = self.company_id.id

        income_account = self.default_income_account_id or self._default_account("income")
        if income_account and "property_account_income_id" in Product._fields:
            vals["property_account_income_id"] = income_account.id

        product_tmpl = Product.create(vals)
        return product_tmpl


    def _sale_invoice_discount_line_cmd(self, payload):
        self.ensure_one()

        discount_amount = self._safe_float(
            self._find_value(payload, "discountAmount"),
            0.0,
        )

        if discount_amount <= 0:
            return False

        discount_product_tmpl = self._get_or_create_discount_product()
        discount_product = discount_product_tmpl.product_variant_id

        account = (
            discount_product.property_account_income_id
            or discount_product.categ_id.property_account_income_categ_id
            or self.default_income_account_id
            or self._default_account("income")
        )

        if not account:
            raise UserError(_("Income account is required for Discount product."))

        return (0, 0, {
            "product_id": discount_product.id,
            "name": "Discount",
            "quantity": 1.0,
            "price_unit": -discount_amount,
            "discount": 0.0,
            "account_id": account.id,
            "tax_ids": [(6, 0, [])],
        })



    def _get_or_create_tax_amount_product(self):
        self.ensure_one()

        Product = self.env["product.template"].with_company(self.company_id).sudo()

        domain = [
            "|",
            ("default_code", "=", "TAX_AMOUNT"),
            ("name", "=", "Tax Amount"),
        ]

        if "company_id" in Product._fields:
            domain = [
                "&",
                "|",
                ("company_id", "=", False),
                ("company_id", "=", self.company_id.id),
            ] + domain

        product_tmpl = Product.search(domain, limit=1)

        if product_tmpl:
            vals = {}

            if "type" in Product._fields:
                vals["type"] = "service"

            if "detailed_type" in Product._fields:
                vals["detailed_type"] = "service"

            if "sale_ok" in Product._fields:
                vals["sale_ok"] = True

            if "purchase_ok" in Product._fields:
                vals["purchase_ok"] = False

            if vals:
                product_tmpl.write(vals)

            return product_tmpl

        vals = {
            "name": "Tax Amount",
            "default_code": "TAX_AMOUNT",
            "list_price": 0.0,
            "standard_price": 0.0,
        }

        if "sale_ok" in Product._fields:
            vals["sale_ok"] = True

        if "purchase_ok" in Product._fields:
            vals["purchase_ok"] = False

        if "type" in Product._fields:
            vals["type"] = "service"

        if "detailed_type" in Product._fields:
            vals["detailed_type"] = "service"

        if "company_id" in Product._fields:
            vals["company_id"] = self.company_id.id

        income_account = self.default_income_account_id or self._default_account("income")
        if income_account and "property_account_income_id" in Product._fields:
            vals["property_account_income_id"] = income_account.id

        product_tmpl = Product.create(vals)
        return product_tmpl


    def _sale_invoice_tax_amount_line_cmd(self, payload):
        self.ensure_one()

        tax_amount = self._safe_float(
            self._find_value(payload, "taxAmount"),
            0.0,
        )

        if tax_amount <= 0:
            return False

        tax_product_tmpl = self._get_or_create_tax_amount_product()
        tax_product = tax_product_tmpl.product_variant_id

        account = (
            tax_product.property_account_income_id
            or tax_product.categ_id.property_account_income_categ_id
            or self.default_income_account_id
            or self._default_account("income")
        )

        if not account:
            raise UserError(_("Income account is required for Tax Amount product."))

        return (0, 0, {
            "product_id": tax_product.id,
            "name": "Tax Amount",
            "quantity": 1.0,
            "price_unit": tax_amount,
            "discount": 0.0,
            "account_id": account.id,
            "tax_ids": [(6, 0, [])],
        })

    def _import_sale_invoice_process(self, payload):
        external_id = self._external_id(payload)

        existing_invoice = self._mapped_record("sale_invoice", external_id, "account.move")
        sale_order = self._prepare_sale_order(payload)

        if existing_invoice:
            return existing_invoice

        details = self._sale_invoice_details(payload)
        if not details:
            raise UserError(_("No sale invoice lines found for Splendid invoice %s") % external_id)

        sale_lines_by_product = {}
        for sol in sale_order.order_line:
            if sol.product_id:
                sale_lines_by_product.setdefault(sol.product_id.id, sol)

        invoice_lines = []

        for line in details:
            product_tmpl = self._resolve_product_from_line(line)
            product = product_tmpl.product_variant_id
            sale_line = sale_lines_by_product.get(product.id)

            invoice_lines.append((0, 0, self._invoice_line_vals_from_sale_line(
                line,
                sale_line=sale_line,
                move_type="out_invoice",
            )))

        # Header-level Splendid discountAmount.
        # Agar discountAmount > 0 ho to Discount service product ki negative line add hogi.
        discount_line = self._sale_invoice_discount_line_cmd(payload)
        if discount_line:
            invoice_lines.append(discount_line)

        # Header-level Splendid taxAmount.
        # Agar taxAmount > 0 ho to Tax Amount service product ki positive line add hogi.
        tax_amount_line = self._sale_invoice_tax_amount_line_cmd(payload)
        if tax_amount_line:
            invoice_lines.append(tax_amount_line)

        journal = self._default_sale_journal()

        move_vals = {
            "move_type": "out_invoice",
            "partner_id": sale_order.partner_id.id,
            "invoice_date": self._parse_date(self._find_value(payload, "date")),
            "invoice_date_due": self._parse_date(self._find_value(payload, "dueDate")) if self._find_value(payload, "dueDate") else False,
            "journal_id": journal.id,
            "invoice_origin": sale_order.name,
            "ref": self._find_value(payload, "number", "reference") or external_id,
            "invoice_line_ids": invoice_lines,
            "company_id": self.company_id.id,
            "splendid_sale_invoice_id": external_id,
            "splendid_source_model": "sale_invoice",
            "splendid_is_imported": True,
        }

        if "splendid_raw_payload" in self.env["account.move"]._fields:
            move_vals["splendid_raw_payload"] = payload

        invoice = self.env["account.move"].with_company(self.company_id).sudo().with_context(
            default_move_type="out_invoice"
        ).create(move_vals)

        self._set_mapping(
            "sale_invoice",
            external_id,
            invoice,
            payload,
            move_vals["ref"],
        )

        if self.auto_post_sale_invoices and invoice.state == "draft":
            invoice.action_post()

        return invoice
    
    def _get_original_sale_invoice(self, payload):
        for item in self._find_value(payload, "saleReturnSettlementDetails", default=[]) or []:
            if not isinstance(item, dict):
                continue
            if str(self._find_value(item, "source", default="")).lower() == "saleinvoice":
                source_id = self._find_value(item, "sourceId")
                move = self._mapped_record("sale_invoice", source_id, "account.move") if source_id else self.env["account.move"]
                if move:
                    return move
        source_id = self._find_value(payload, "saleInvoiceId")
        return self._mapped_record("sale_invoice", source_id, "account.move") if source_id else self.env["account.move"]

    def _import_sale_return_process(self, payload):
        external_id = self._external_id(payload)
        credit_note = self._mapped_record("sale_return", external_id, "account.move")
        if not credit_note:
            credit_note = self._create_sale_return_credit_note(payload)
        if self.auto_create_return_transfers:
            self._create_sale_return_transfer(payload)
        return credit_note

    def _create_sale_return_credit_note(self, payload):
        external_id = self._external_id(payload)
        partner = self._resolve_customer(payload)
        original_invoice = self._get_original_sale_invoice(payload)
        invoice_lines = []
        for line in self._sale_return_details(payload):
            invoice_lines.append((0, 0, self._invoice_line_vals_from_sale_line(line, sale_line=False, move_type="out_refund")))
        if not invoice_lines:
            raise UserError(_("No sale return lines found for Splendid return %s") % external_id)
        vals = {
            "move_type": "out_refund",
            "partner_id": partner.id,
            "invoice_date": self._parse_date(self._find_value(payload, "date")),
            "journal_id": self._default_sale_journal().id,
            "invoice_origin": original_invoice.name if original_invoice else self._find_value(payload, "saleInvoiceNumber"),
            "ref": self._find_value(payload, "number", "reference") or external_id,
            "invoice_line_ids": invoice_lines,
            "company_id": self.company_id.id,
            "splendid_sale_return_id": external_id,
            "splendid_source_model": "sale_return",
            "splendid_is_imported": True,
        }
        if original_invoice and "reversed_entry_id" in self.env["account.move"]._fields:
            vals["reversed_entry_id"] = original_invoice.id
        if "splendid_raw_payload" in self.env["account.move"]._fields:
            vals["splendid_raw_payload"] = payload
        credit_note = self.env["account.move"].with_company(self.company_id).sudo().with_context(default_move_type="out_refund").create(vals)
        self._set_mapping("sale_return", external_id, credit_note, payload, vals["ref"])
        if self.auto_post_sale_invoices and credit_note.state == "draft":
            credit_note.action_post()
        if original_invoice and credit_note.state == "posted" and self.auto_reconcile_customer_payments:
            self._reconcile_moves([original_invoice, credit_note])
        return credit_note

    def _create_sale_return_transfer(self, payload):
        external_id = self._external_id(payload)
        existing = self._mapped_record("sale_return_transfer", external_id, "stock.picking")
        if existing:
            return existing
        details = self._sale_return_details(payload)
        if not details:
            return self.env["stock.picking"]
        warehouse = self._resolve_warehouse(details[0])
        picking_type = warehouse.in_type_id or self.env["stock.picking.type"].with_company(self.company_id).sudo().search([
            ("code", "=", "incoming"),
            ("company_id", "=", self.company_id.id),
        ], limit=1)
        source_location = self._warehouse_customer_location()
        dest_location = warehouse.lot_stock_id
        move_cmds = []
        for line in details:
            product_tmpl = self._resolve_product_from_line(line)
            product = product_tmpl.product_variant_id
            qty = self._safe_float(self._find_value(line, "quantity"), 0.0)
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
            return self.env["stock.picking"]
        picking_vals = {
            "picking_type_id": picking_type.id,
            "partner_id": self._resolve_customer(payload).id,
            "location_id": source_location.id,
            "location_dest_id": dest_location.id,
            "origin": self._find_value(payload, "number") or external_id,
            "scheduled_date": self._parse_datetime(self._find_value(payload, "date")),
            "company_id": self.company_id.id,
            "move_ids": move_cmds,
            "splendid_sale_return_id": external_id,
            "splendid_source_model": "sale_return_transfer",
            "splendid_is_imported": True,
        }
        if "splendid_raw_payload" in self.env["stock.picking"]._fields:
            picking_vals["splendid_raw_payload"] = payload
        picking = self.env["stock.picking"].with_company(self.company_id).sudo().create(picking_vals)
        self._set_mapping("sale_return_transfer", external_id, picking, payload, picking.name)
        if picking.state == "draft":
            picking.action_confirm()
        if self.auto_validate_return_transfers:
            self._validate_picking(picking)
        return picking

    def _resolve_journal_for_customer_payment(self, payload):
        account_id = False
        account_code = False
        for line in self._find_value(payload, "customerPaymentDetails", default=[]) or []:
            if isinstance(line, dict):
                account_id = self._find_value(line, "accountId")
                account_code = self._find_value(self._nested(line, "account"), "code")
                break
        account = self._resolve_account(account_id, account_code)
        Journal = self.env["account.journal"].with_company(self.company_id).sudo()
        if account:
            journal = Journal.search([
                ("company_id", "=", self.company_id.id),
                ("type", "in", ("bank", "cash")),
                ("default_account_id", "=", account.id),
            ], limit=1)
            if journal:
                return journal
            journal = Journal.search([
                ("company_id", "=", self.company_id.id),
                ("splendid_bank_account_account_id", "=", str(account_id or "")),
            ], limit=1)
            if journal:
                return journal
        return self._default_bank_journal()

    def _import_customer_payment_process(self, payload):
        external_id = self._external_id(payload)

        payment = self._mapped_record("customer_payment", external_id, "account.payment")
        if payment:
            # Existing payment ko bhi post/reconcile karo.
            if self.auto_post_customer_payments and getattr(payment, "state", False) == "draft":
                payment.action_post()
            if self.auto_reconcile_customer_payments:
                self._reconcile_customer_payment(payment, payload)
            return payment

        partner = self._resolve_customer(payload)
        journal = self._resolve_journal_for_customer_payment(payload)

        amount = self._safe_float(
            self._find_value(payload, "totalAmount", "allocatedAmount", "amount"),
            0.0,
        )

        payment_ref = self._find_value(payload, "number", "reference", "comments") or external_id

        vals = {
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": partner.id,
            "amount": amount,
            "date": self._parse_date(self._find_value(payload, "date")),
            "journal_id": journal.id,
            "company_id": self.company_id.id,
            "payment_reference": payment_ref,
            "splendid_customer_payment_id": external_id,
            "splendid_is_imported": True,
        }

        methods = journal.inbound_payment_method_line_ids
        if methods:
            vals["payment_method_line_id"] = methods[0].id

        if "splendid_raw_payload" in self.env["account.payment"]._fields:
            vals["splendid_raw_payload"] = payload

        payment = self.env["account.payment"].with_company(self.company_id).sudo().create(vals)

        self._set_mapping(
            "customer_payment",
            external_id,
            payment,
            payload,
            payment_ref,
        )

        if self.auto_post_customer_payments and getattr(payment, "state", False) == "draft":
            payment.action_post()

        if self.auto_reconcile_customer_payments:
            self._reconcile_customer_payment(payment, payload)

        return payment
    def _find_sale_invoice_for_payment_settlement(self, source_id=False, source_number=False):
        Move = self.env["account.move"].with_company(self.company_id).sudo()

        if source_id:
            move = self._mapped_record("sale_invoice", source_id, "account.move")
            if move:
                return move

            if "splendid_sale_invoice_id" in Move._fields:
                move = Move.search([
                    ("company_id", "=", self.company_id.id),
                    ("move_type", "=", "out_invoice"),
                    ("splendid_sale_invoice_id", "=", str(source_id)),
                ], limit=1)
                if move:
                    return move

        if source_number:
            move = Move.search([
                ("company_id", "=", self.company_id.id),
                ("move_type", "=", "out_invoice"),
                "|",
                ("ref", "=", source_number),
                ("name", "=", source_number),
            ], limit=1)
            if move:
                return move

        return Move

    def _get_customer_payment_outstanding_lines(self, payment):
        if not payment or not payment.move_id:
            return self.env["account.move.line"]

        return payment.move_id.line_ids.filtered(
            lambda line:
                not line.reconciled
                and line.partner_id == payment.partner_id
                and abs(line.amount_residual) > 0.00001
                and line.credit > 0
        )

    def _reconcile_customer_payment(self, payment, payload):
        if not payment:
            return False

        if getattr(payment, "state", False) == "draft":
            payment.action_post()

        if not payment.move_id:
            return False

        settlement_lines = []
        settlement_lines += self._find_value(payload, "customerPaymentSettlementDetails", default=[]) or []
        settlement_lines += self._find_value(payload, "customerSingleSettledEntryItems", default=[]) or []

        invoice_moves = self.env["account.move"].with_company(self.company_id).sudo()

        for item in settlement_lines:
            if not isinstance(item, dict):
                continue

            if str(self._find_value(item, "source", default="")).lower() != "saleinvoice":
                continue

            source_id = self._find_value(item, "sourceId")
            source_number = self._find_value(item, "sourceNumber", "number")

            invoice = self._find_sale_invoice_for_payment_settlement(
                source_id=source_id,
                source_number=source_number,
            )

            if invoice:
                invoice_moves |= invoice

        if not invoice_moves:
            self._log(
                "customer_payments",
                "error",
                "Payment imported but matching sale invoice was not found. Check sale_invoice mapping/splendid_sale_invoice_id.",
                payload,
                self._external_id(payload),
                payment,
            )
            return False

        for invoice in invoice_moves:
            if invoice.state == "draft":
                invoice.action_post()

        outstanding_lines = self._get_customer_payment_outstanding_lines(payment)

        if not outstanding_lines:
            self._log(
                "customer_payments",
                "error",
                "Payment posted but no outstanding payment line found to assign on invoice.",
                payload,
                self._external_id(payload),
                payment,
            )
            return False

        for invoice in invoice_moves:
            if invoice.payment_state == "paid":
                continue

            # Prefer same partner lines.
            lines = outstanding_lines.filtered(lambda l: l.partner_id == invoice.partner_id)
            if not lines:
                lines = outstanding_lines

            for line in lines:
                if invoice.payment_state == "paid":
                    break

                try:
                    invoice.js_assign_outstanding_line(line.id)
                except Exception as exc:
                    _logger.warning(
                        "Could not assign Splendid payment %s to invoice %s using line %s: %s",
                        payment.display_name,
                        invoice.display_name,
                        line.id,
                        exc,
                    )

        if any(inv.payment_state != "paid" for inv in invoice_moves):
            self._log(
                "customer_payments",
                "error",
                "Payment imported but invoice is still not fully paid. Check amount, partner, currency, and residual.",
                payload,
                self._external_id(payload),
                payment,
            )

    def _reconcile_moves(self, moves):
        if not moves:
            return False

        lines = moves.mapped("line_ids").filtered(
            lambda l:
                not l.reconciled
                and not l.blocked
                and l.account_id.account_type == "asset_receivable"
                and abs(l.amount_residual) > 0.00001
        )

        for account in lines.mapped("account_id"):
            account_lines = lines.filtered(lambda l, acc=account: l.account_id == acc)
            debit_lines = account_lines.filtered(lambda l: l.amount_residual > 0)
            credit_lines = account_lines.filtered(lambda l: l.amount_residual < 0)

            if debit_lines and credit_lines:
                try:
                    account_lines.reconcile()
                except Exception as exc:
                    _logger.warning("Could not reconcile Splendid receivable lines: %s", exc)

        return True