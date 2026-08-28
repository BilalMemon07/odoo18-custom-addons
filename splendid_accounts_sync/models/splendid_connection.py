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

    # Manufacturing / Splendid Job Orders
    job_orders_fetched_count = fields.Integer(copy=False, readonly=True)
    job_orders_imported_count = fields.Integer(copy=False, readonly=True)
    job_orders_failed_count = fields.Integer(copy=False, readonly=True)
    auto_confirm_job_orders = fields.Boolean(
        string="Confirm Manufacturing Orders",
        default=False,
        help="Optionally confirm imported Odoo Manufacturing Orders after creating their job-specific BoM. Disabled by default so the first sync does not reserve manufacturing components. This never marks production as done.",
    )
    # Legacy Job Order expense accounting switches are retained only so older
    # databases can upgrade without dropping columns. v29 no longer uses them:
    # jobOrderExpenses are represented by native Manufacturing Work Orders.
    auto_create_job_order_expense_bills = fields.Boolean(
        string="Legacy: Create Vendor Bills for Job Order Expenses",
        default=False,
        help="Deprecated. Job Order expenses now create Journal Entries and do not require a Vendor.",
    )
    auto_post_job_order_expense_bills = fields.Boolean(
        string="Legacy: Post Job Order Expense Vendor Bills",
        default=False,
        help="Deprecated. Job Order expenses now create Journal Entries and do not require a Vendor.",
    )
    auto_create_job_order_expense_entries = fields.Boolean(
        string="Legacy: Create Job Order Expense Journal Entries",
        default=True,
        help="Deprecated and ignored. v29 applies Splendid jobOrderExpenses through Manufacturing Work Orders instead of separate Journal Entries.",
    )
    auto_post_job_order_expense_entries = fields.Boolean(
        string="Legacy: Post Job Order Expense Journal Entries",
        default=True,
        help="Deprecated and ignored. Standard Odoo Manufacturing/Work Center accounting is used instead.",
    )

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
    auto_post_customer_refunds = fields.Boolean(string="Post Customer Refunds", default=True)
    auto_reconcile_customer_refunds = fields.Boolean(string="Reconcile Customer Refunds", default=True)

    sale_journal_id = fields.Many2one("account.journal", domain="[('type','=','sale'), ('company_id','=',company_id)]")
    bank_journal_id = fields.Many2one("account.journal", domain="[('type','in',('bank','cash')), ('company_id','=',company_id)]")

    last_sales_process_sync = fields.Datetime(copy=False, string="Last Sales Process Sync")
    last_sale_invoices_sync = fields.Datetime(copy=False, string="Last Sale Invoices Sync")
    last_sale_returns_sync = fields.Datetime(copy=False, string="Last Sale Returns Sync")
    last_customer_payments_sync = fields.Datetime(copy=False, string="Last Customer Payments Sync")
    last_customer_refunds_sync = fields.Datetime(copy=False, string="Last Customer Refunds Sync")

    sale_invoices_fetched_count = fields.Integer(copy=False, readonly=True)
    sale_invoices_imported_count = fields.Integer(copy=False, readonly=True)
    sale_invoices_failed_count = fields.Integer(copy=False, readonly=True)
    sale_returns_fetched_count = fields.Integer(copy=False, readonly=True)
    sale_returns_imported_count = fields.Integer(copy=False, readonly=True)
    sale_returns_failed_count = fields.Integer(copy=False, readonly=True)
    customer_payments_fetched_count = fields.Integer(copy=False, readonly=True)
    customer_payments_imported_count = fields.Integer(copy=False, readonly=True)
    customer_payments_failed_count = fields.Integer(copy=False, readonly=True)
    customer_refunds_fetched_count = fields.Integer(copy=False, readonly=True)
    customer_refunds_imported_count = fields.Integer(copy=False, readonly=True)
    customer_refunds_failed_count = fields.Integer(copy=False, readonly=True)

    # Accounting migration / Splendid Journal Entries
    last_journal_entries_sync = fields.Datetime(copy=False, string="Last Journal Entries Sync")
    journal_entries_fetched_count = fields.Integer(copy=False, readonly=True)
    journal_entries_imported_count = fields.Integer(copy=False, readonly=True)
    journal_entries_failed_count = fields.Integer(copy=False, readonly=True)
    journal_entry_journal_id = fields.Many2one(
        "account.journal",
        string="Journal Entries Journal",
        domain="[('type','=','general'), ('company_id','=',company_id)]",
        help="General journal used for Splendid JournalEntries migration. If empty, the integration creates/reuses 'Splendid Journal Entries'.",
    )
    journal_entry_external_id = fields.Char(
        string="Journal Entry ID",
        help="Optional Splendid JournalEntries ID for one-by-one GET/import testing.",
    )
    auto_post_journal_entries = fields.Boolean(
        string="Post Imported Journal Entries",
        default=False,
        help="When enabled, balanced non-void Splendid JournalEntries are posted after import. Disabled by default so migration can be reviewed in Draft first.",
    )

    # Accounting migration / Splendid Expenses -> Odoo Journal Entries
    last_expenses_sync = fields.Datetime(copy=False, string="Last Expenses Sync")
    expenses_fetched_count = fields.Integer(copy=False, readonly=True)
    expenses_imported_count = fields.Integer(copy=False, readonly=True)
    expenses_failed_count = fields.Integer(copy=False, readonly=True)
    expense_journal_id = fields.Many2one(
        "account.journal",
        string="Expenses Journal",
        domain="[('type','=','general'), ('company_id','=',company_id)]",
        help="General journal used for Splendid Expenses migration. If empty, the integration creates/reuses 'Splendid Expenses'.",
    )
    expense_external_id = fields.Char(
        string="Expense ID",
        help="Optional Splendid Expenses ID for one-by-one GET/import testing.",
    )
    auto_post_expenses = fields.Boolean(
        string="Post Imported Expenses",
        default=False,
        help="When enabled, balanced non-void Splendid Expenses are posted after import. Disabled by default so migration can be reviewed in Draft first.",
    )

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
            rec.journal_entry_journal_id = False
            rec.expense_journal_id = False

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

    def action_sync_customer_refunds(self):
        for rec in self:
            rec = rec._with_target_company()
            rec._sync_customer_refunds()
        return True

    def action_reconcile_customer_settlements(self):
        """Reconcile existing Odoo sales documents from Splendid allocations.

        CustomerSettlements is the source of truth. This action does not create
        write-offs and does not invent missing customer payments/refunds. Draft
        referenced invoices/credit notes/payments are posted before applying the
        exact adjustedAmount from customerSettlementDetails.
        """
        summaries = []
        for rec in self:
            rec = rec._with_target_company()
            summaries.append(rec._reconcile_all_customer_settlements_from_splendid())

        total_new = sum(item.get("newly_reconciled", 0.0) for item in summaries)
        total_existing = sum(item.get("already_reconciled", 0.0) for item in summaries)
        total_review = sum(item.get("review_count", 0) for item in summaries)
        total_allocations = sum(item.get("allocation_count", 0) for item in summaries)

        message = _(
            "Splendid CustomerSettlements reconciliation complete. Allocations checked: %(allocations)s; "
            "newly reconciled: %(new).2f; already matched: %(existing).2f; review items: %(review)s."
        ) % {
            "allocations": total_allocations,
            "new": total_new,
            "existing": total_existing,
            "review": total_review,
        }
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Splendid Customer Reconciliation"),
                "message": message,
                "type": "warning" if total_review else "success",
                "sticky": bool(total_review),
            },
        }

    # Backward-compatible methods. These no longer sync transactions or inventory.
    def action_sync_transactions(self):
        raise UserError(_("Transaction sync has been removed from this master-data-only version. Use Sync Master Data."))

    def action_sync_inventory(self):
        raise UserError(_("Inventory sync has been removed from this master-data-only version. Use Sync Master Data."))

    def action_sync_manufacturing(self):
        # Backward-compatible name from older module versions.
        return self.action_sync_job_orders()

    def action_sync_job_orders(self):
        for rec in self:
            rec = rec._with_target_company()
            rec._sync_job_orders()
        return True

    def action_sync_journal_entries(self):
        for rec in self:
            rec = rec._with_target_company()
            rec._sync_journal_entries()
        return True

    def action_sync_journal_entry_by_id(self):
        self.ensure_one()
        rec = self._with_target_company()
        external_id = str(rec.journal_entry_external_id or "").strip()
        if not external_id:
            raise UserError(_("Enter a Splendid Journal Entry ID first."))
        try:
            with rec.env.cr.savepoint():
                payload = rec._fetch_detail_by_id("/JournalEntries", external_id)
                if not payload:
                    raise UserError(_("Splendid JournalEntries/%s returned no record.") % external_id)
                if rec._journal_entry_is_status_30(payload):
                    rec._log(
                        "journal_entries",
                        "skipped",
                        "Journal entry fetched by ID but skipped because Splendid status is 30.",
                        payload,
                        external_id,
                    )
                    rec.last_journal_entries_sync = fields.Datetime.now()
                    rec.env.cr.commit()
                    return {
                        "type": "ir.actions.client",
                        "tag": "display_notification",
                        "params": {
                            "title": _("Splendid Journal Entry"),
                            "message": _("JournalEntries/%s has status 30 and was not imported.") % external_id,
                            "type": "warning",
                            "sticky": True,
                        },
                    }
                if rec._journal_entry_is_void(payload):
                    rec._log(
                        "journal_entries",
                        "skipped",
                        "Journal entry fetched by ID but skipped because Splendid marks it void.",
                        payload,
                        external_id,
                    )
                    rec.last_journal_entries_sync = fields.Datetime.now()
                    rec.env.cr.commit()
                    return {
                        "type": "ir.actions.client",
                        "tag": "display_notification",
                        "params": {
                            "title": _("Splendid Journal Entry"),
                            "message": _("JournalEntries/%s is void and was not imported.") % external_id,
                            "type": "warning",
                            "sticky": True,
                        },
                    }
                record = rec._import_journal_entry_process(payload)
                rec._log(
                    "journal_entries",
                    "success",
                    "Journal entry imported/updated by ID",
                    payload,
                    external_id,
                    record,
                )
        except Exception as exc:  # pylint: disable=broad-except
            rec._log("journal_entries", "error", str(exc), {"requested_id": external_id}, external_id)
            raise
        rec.last_journal_entries_sync = fields.Datetime.now()
        rec.env.cr.commit()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Splendid Journal Entry"),
                "message": _("JournalEntries/%s imported successfully.") % external_id,
                "type": "success",
                "sticky": False,
            },
        }

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
                # The /Products list response may omit product-level fields such as
                # `symbol`.  When that happens, fetch /Products/{id} before import so
                # Master Data, Sales and Purchase all use the same complete product
                # payload and therefore the same UoM/inventory settings.
                if key == "products":
                    payload = self._complete_splendid_product_payload(payload, external_id=external_id)
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

    def _splendid_uom_id_from_symbol(self, symbol):
        """Return the exact Odoo UoM ID configured for Splendid product symbols.

        Current target database mapping confirmed by the customer:
        - pc / unit aliases -> Units (uom.uom ID 1)
        - kg aliases        -> kg    (uom.uom ID 13)
        """
        key = self._normalize_splendid_uom_key(symbol)
        if key in ("pc", "pcs", "piece", "pieces", "unit", "units", "ea", "each"):
            return 1
        if key in ("kg", "kgs", "kilogram", "kilograms"):
            return 13
        return False

    def _complete_splendid_product_payload(self, payload=None, external_id=False, force_detail=False):
        """Return a complete Splendid product payload.

        Product list/transaction lines can contain only productId and may omit the
        product-level `symbol`.  In that case fetch /Products/{id}.  This helper is
        shared by Master Data and transaction product resolution.
        """
        self.ensure_one()
        payload = dict(payload or {}) if isinstance(payload, dict) else {}
        product_id = external_id or self._product_external_id(payload)

        # Transaction nested product objects sometimes have code/name/symbol but
        # no product id. Preserve the line's productId as the authoritative ID so
        # mapping and future updates use the same Splendid product record.
        if external_id and not self._find_value(
            payload, "id", "Id", "productId", "ProductId", "productID", "externalId", "sourceId"
        ):
            payload["id"] = external_id

        symbol = str(self._find_value(payload, "symbol") or "").strip()

        if product_id and (force_detail or not symbol):
            detail = self._fetch_detail_by_id("/Products", product_id)
            if isinstance(detail, dict) and detail:
                # Detail payload is authoritative; keep any summary-only keys only
                # when Splendid did not return them in the detail response.
                merged = dict(payload)
                merged.update(detail)
                payload = merged

        return payload

    def _import_products(self, payload):
        self.ensure_one()

        external_id = self._product_external_id(payload)
        Product = self.env["product.template"].with_company(self.company_id).sudo()

        # Existing product find
        product = self._mapped_record(
            "product",
            external_id,
            "product.template",
        )

        if not product and external_id and "splendid_product_id" in Product._fields:
            domain = [
                ("splendid_product_id", "=", str(external_id)),
            ]
            if "company_id" in Product._fields:
                domain = ["&"] + domain + [
                    "|",
                    ("company_id", "=", False),
                    ("company_id", "=", self.company_id.id),
                ]
            product = Product.search(domain, limit=1)

        name = (
            self._find_value(
                payload,
                "name",
                "displayName",
                "shortName",
                "sku",
                "code",
            )
            or _("Splendid Product %s") % external_id
        )

        sku = self._clean_product_code(
            self._find_value(payload, "sku", "code", "number"),
            fallback=external_id,
        )

        if not sku:
            sku = self._clean_product_code(
                name,
                fallback=external_id,
            )

        # ---------------------------------------------------------
        # BASE PRODUCT VALUES
        # ---------------------------------------------------------
        vals = {
            "name": str(name)[:1000],
            "default_code": sku,
            "list_price": self._safe_float(
                self._find_value(
                    payload,
                    "salePrice",
                    "maximumRetailPrice",
                ),
                0.0,
            ),
            "standard_price": self._safe_float(
                self._find_value(
                    payload,
                    "purchasePrice",
                    "averageCost",
                ),
                0.0,
            ),
            "splendid_product_id": external_id,
            "splendid_is_imported": True,

            # All Splendid products should track inventory
            "type": "consu",
            "is_storable": True,
        }

        if (
            "detailed_type" in Product._fields
            and self._selection_has_value(
                Product,
                "detailed_type",
                "consu",
            )
        ):
            vals["detailed_type"] = "consu"

        if "splendid_track_inventory" in Product._fields:
            vals["splendid_track_inventory"] = True

        if "sale_ok" in Product._fields:
            vals["sale_ok"] = self._safe_bool(
                self._find_value(payload, "isForSale"),
                True,
            )

        if "purchase_ok" in Product._fields:
            vals["purchase_ok"] = self._safe_bool(
                self._find_value(payload, "isForPurchase"),
                True,
            )

        if "company_id" in Product._fields:
            vals["company_id"] = self.company_id.id

        # ---------------------------------------------------------
        # SPLENDID UOM
        # ---------------------------------------------------------
        # IMPORTANT:
        # We read ONLY Splendid's "symbol" field here.
        #
        # pc -> Odoo Units ID 1
        # kg -> Odoo kg ID 13
        # ---------------------------------------------------------
        symbol = str(self._find_value(payload, "symbol") or "").strip()

        # Always preserve exactly what Splendid sent for debugging/audit.
        if "splendid_uom_symbol" in Product._fields:
            vals["splendid_uom_symbol"] = symbol or False

        uom_id = self._splendid_uom_id_from_symbol(symbol)
        if uom_id:
            uom = self.env["uom.uom"].sudo().browse(uom_id).exists()
            if not uom:
                raise UserError(_(
                    "Configured Odoo UoM ID %s does not exist for Splendid symbol '%s'."
                ) % (uom_id, symbol))
            vals["uom_id"] = uom.id
            vals["uom_po_id"] = uom.id
        elif symbol:
            # Keep support for other existing Splendid symbols by exact Odoo UoM
            # name, but never silently replace pc/kg with a default UoM.
            uom = self.env["uom.uom"].sudo().search([("name", "=ilike", symbol)], limit=1)
            if uom:
                vals["uom_id"] = uom.id
                vals["uom_po_id"] = uom.id
            else:
                raise UserError(_(
                    "Splendid UoM symbol '%s' could not be mapped for product %s."
                ) % (symbol, sku))
        else:
            raise UserError(_(
                "Splendid product %s has no UoM symbol. Product import was stopped so Odoo does not use a wrong default UoM."
            ) % sku)

        # ---------------------------------------------------------
        # BARCODE
        # ---------------------------------------------------------
        barcode = self._safe_barcode(
            self._find_value(payload, "barcode"),
            product=product,
        )

        if barcode and "barcode" in Product._fields:
            vals["barcode"] = barcode

        # ---------------------------------------------------------
        # DESCRIPTION
        # ---------------------------------------------------------
        description = self._find_value(
            payload,
            "description",
            "shortDescription",
            "catalogContent",
        )

        if description:
            vals["description_sale"] = description
            vals["description_purchase"] = description

        # ---------------------------------------------------------
        # ACCOUNTS
        # ---------------------------------------------------------
        income_account = self._resolve_account(
            self._find_value(payload, "salesAccountId")
        )

        expense_account = self._resolve_account(
            self._find_value(payload, "expenseAccountId")
        )

        if (
            income_account
            and "property_account_income_id" in Product._fields
        ):
            vals["property_account_income_id"] = income_account.id

        if (
            expense_account
            and "property_account_expense_id" in Product._fields
        ):
            vals["property_account_expense_id"] = expense_account.id

        # Search by SKU if no mapped product
        if not product and sku:
            domain = [
                ("default_code", "=", sku),
            ]

            if "company_id" in Product._fields:
                domain = ["&"] + domain + [
                    "|",
                    ("company_id", "=", False),
                    ("company_id", "=", self.company_id.id),
                ]

            product = Product.search(domain, limit=1)

        # ---------------------------------------------------------
        # DEBUG
        # ---------------------------------------------------------
        _logger.warning(
            "SPLENDID PRODUCT BEFORE SAVE >>> "
            "code=%s symbol=%s "
            "uom_id=%s uom_po_id=%s "
            "is_storable=%s",
            payload.get("code"),
            payload.get("symbol"),
            vals.get("uom_id"),
            vals.get("uom_po_id"),
            vals.get("is_storable"),
        )

        # ---------------------------------------------------------
        # CREATE / UPDATE
        # ---------------------------------------------------------
        if product:
            product.with_company(
                self.company_id
            ).sudo().write(vals)

        else:
            product = Product.create(vals)

        # Reload actual DB values
        product.invalidate_recordset()

        _logger.warning(
            "SPLENDID PRODUCT AFTER SAVE >>> "
            "code=%s "
            "splendid_symbol=%s "
            "actual_uom_id=%s "
            "actual_uom=%s "
            "actual_is_storable=%s",
            payload.get("code"),
            (
                product.splendid_uom_symbol
                if "splendid_uom_symbol" in product._fields
                else False
            ),
            product.uom_id.id,
            product.uom_id.display_name,
            product.is_storable,
        )

        self._set_mapping(
            "product",
            external_id,
            product,
            payload,
            name,
        )

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

    def _payload_has_any_key(self, payload, *keys):
        if not isinstance(payload, dict):
            return False
        lower_keys = {str(k).lower(): True for k in payload.keys()}
        return any(str(key).lower() in lower_keys for key in keys)

    def _splendid_track_inventory_value(self, payload, default=False):
        if not isinstance(payload, dict):
            return default
        if not self._payload_has_any_key(payload, "trackInventory", "track_inventory", "trackinventory"):
            return default
        return self._safe_bool(self._find_value(payload, "trackInventory", "track_inventory", "trackinventory"), default)

    def _product_template_stock_type_value(self, track_inventory=False, is_service=False, is_combo=False):
        """Return the product.template type for this DB.

        Odoo 18/19 uses type='consu' for Goods and is_storable=True for
        Track Inventory. Older DBs may still use type='product'. Since this
        module is for Odoo 18, prefer consu whenever is_storable exists.
        """
        Product = self.env["product.template"]
        has_is_storable = "is_storable" in Product._fields
        if track_inventory:
            if has_is_storable and self._selection_has_value(Product, "type", "consu"):
                return "consu"
            if self._selection_has_value(Product, "type", "product"):
                return "product"
            return "consu"
        if is_service:
            return "service"
        if is_combo and self._selection_has_value(Product, "type", "combo"):
            return "combo"
        return "consu"

    def _product_detailed_type_value(self, track_inventory=False, is_service=False, is_combo=False):
        Product = self.env["product.template"]
        has_is_storable = "is_storable" in Product._fields
        if track_inventory:
            if has_is_storable and self._selection_has_value(Product, "detailed_type", "consu"):
                return "consu"
            if self._selection_has_value(Product, "detailed_type", "product"):
                return "product"
            return "consu"
        if is_service:
            return "service"
        if is_combo and self._selection_has_value(Product, "detailed_type", "combo"):
            return "combo"
        return "consu"

    def _product_type_vals(self, payload):
        """Return the forced Odoo 18 inventory settings for Splendid products.

        Do not depend on Splendid trackInventory here. The requested integration
        rule is that every imported product is inventory tracked in Odoo.
        """
        Product = self.env["product.template"]
        vals = {}

        if "type" in Product._fields:
            if self._selection_has_value(Product, "type", "consu"):
                vals["type"] = "consu"
            else:
                raise UserError(_("Odoo Goods product type 'consu' is not available."))

        if "detailed_type" in Product._fields and self._selection_has_value(Product, "detailed_type", "consu"):
            vals["detailed_type"] = "consu"

        if "is_storable" in Product._fields:
            vals["is_storable"] = True
        else:
            raise UserError(_(
                "Odoo product.template.is_storable field is missing. "
                "Install/enable the Inventory module before syncing products."
            ))

        if "splendid_track_inventory" in Product._fields:
            vals["splendid_track_inventory"] = True

        return vals

    def _normalize_splendid_uom_key(self, value):
        value = str(value or "").strip().lower()
        return re.sub(r"[^a-z0-9]+", "", value)

    def _get_splendid_uom_symbol(self, payload_or_symbol=False):
        if isinstance(payload_or_symbol, dict):
            return self._find_value(
                payload_or_symbol,
                "symbol",
                "uom",
                "uomSymbol",
                "unit",
                "unitSymbol",
                "unitOfMeasure",
                "uomName",
            )
        return payload_or_symbol

    def _resolve_splendid_uom(self, payload_or_symbol=False):
        self.ensure_one()

        original_symbol = str(
            self._get_splendid_uom_symbol(payload_or_symbol) or ""
        ).strip()

        key = self._normalize_splendid_uom_key(original_symbol)

        if not key:
            return self.env["uom.uom"]

        Uom = self.env["uom.uom"].sudo()

        # Exact target-DB mapping is centralized so Master/Sale/Purchase cannot
        # diverge: pc -> Units (1), kg -> kg (13).
        uom_id = self._splendid_uom_id_from_symbol(key)

        if uom_id:
            uom = Uom.browse(uom_id).exists()

            if not uom:
                raise UserError(
                    _("Odoo UoM ID %s not found for Splendid symbol '%s'.")
                    % (uom_id, original_symbol)
                )

            _logger.info(
                "Splendid UoM resolved: symbol=%s key=%s -> Odoo UoM id=%s name=%s",
                original_symbol,
                key,
                uom.id,
                uom.display_name,
            )

            return uom

        # Other Splendid symbols:
        # first try exact name from existing Odoo UoMs.
        uom = Uom.search(
            [("name", "=ilike", original_symbol)],
            limit=1,
        )

        if uom:
            return uom

        self._log(
            "products",
            "error",
            "Splendid UoM symbol '%s' was not found in Odoo."
            % original_symbol,
            payload_or_symbol
            if isinstance(payload_or_symbol, dict)
            else {"symbol": original_symbol},
            self._product_external_id(payload_or_symbol)
            if isinstance(payload_or_symbol, dict)
            else original_symbol,
        )

        return self.env["uom.uom"]

    def _product_uom_vals(self, payload):
        Product = self.env["product.template"]
        vals = {}

        if not isinstance(payload, dict):
            return vals

        symbol = str(self._get_splendid_uom_symbol(payload) or "").strip()

        # Save the raw Splendid symbol even before UoM resolution.
        if "splendid_uom_symbol" in Product._fields:
            vals["splendid_uom_symbol"] = symbol[:64] or False

        if not symbol:
            return vals

        uom = self._resolve_splendid_uom(symbol)

        if not uom:
            return vals

        if "uom_id" in Product._fields:
            vals["uom_id"] = uom.id

        if "uom_po_id" in Product._fields:
            vals["uom_po_id"] = uom.id

        _logger.info(
            "Splendid product UoM vals: product=%s symbol=%s uom_id=%s uom_name=%s",
            self._find_value(payload, "code"),
            symbol,
            uom.id,
            uom.display_name,
        )

        return vals

   
    def _force_product_inventory_uom(self, product_tmpl, payload=None, external_id=False, raise_on_mismatch=False):
        """Force and verify inventory + UoM settings on product.template.

        Odoo 18 stock defines Track Inventory on product.template.is_storable.
        It is valid only for type='consu', so both fields are written together.
        UoM comes from Splendid's product-level symbol field.
        """
        self.ensure_one()
        if not product_tmpl or not isinstance(payload, dict):
            return product_tmpl

        ProductTemplate = self.env["product.template"]
        messages = []
        symbol = str(self._get_splendid_uom_symbol(payload) or "").strip()
        expected_uom = self._resolve_splendid_uom(symbol) if symbol else self.env["uom.uom"]

        desired_vals = {
            "type": "consu",
            "is_storable": True,
        }
        if "detailed_type" in ProductTemplate._fields and self._selection_has_value(ProductTemplate, "detailed_type", "consu"):
            desired_vals["detailed_type"] = "consu"
        if "splendid_track_inventory" in ProductTemplate._fields:
            desired_vals["splendid_track_inventory"] = True

        if expected_uom:
            desired_vals["uom_id"] = expected_uom.id
            desired_vals["uom_po_id"] = expected_uom.id
        if symbol and "splendid_uom_symbol" in ProductTemplate._fields:
            desired_vals["splendid_uom_symbol"] = str(symbol)[:64]

        desired_vals = {k: v for k, v in desired_vals.items() if k in ProductTemplate._fields}

        try:
            product_tmpl.with_company(self.company_id).sudo().write(desired_vals)
        except Exception as exc:  # pylint: disable=broad-except
            messages.append("product.template write failed for %s: %s" % (desired_vals, exc))

        try:
            product_tmpl.flush_recordset()
            product_tmpl.invalidate_recordset()
        except Exception:  # pylint: disable=broad-except
            pass

        # Verify Track Inventory unconditionally.
        if "is_storable" not in ProductTemplate._fields:
            messages.append("product.template.is_storable field does not exist")
        elif not bool(product_tmpl.is_storable):
            messages.append("expected product.template.is_storable=True but actual=False")

        if "type" in ProductTemplate._fields and product_tmpl.type != "consu":
            messages.append("expected product.template.type='consu' but actual='%s'" % product_tmpl.type)

        # Verify UoM whenever Splendid sent a symbol.
        if symbol:
            if not expected_uom:
                messages.append("Splendid symbol '%s' could not be mapped to an Odoo UoM" % symbol)
            else:
                if "uom_id" in ProductTemplate._fields and product_tmpl.uom_id.id != expected_uom.id:
                    messages.append(
                        "expected uom_id='%s' from Splendid symbol '%s' but actual='%s'" % (
                            expected_uom.display_name,
                            symbol,
                            product_tmpl.uom_id.display_name,
                        )
                    )
                if "uom_po_id" in ProductTemplate._fields and product_tmpl.uom_po_id.id != expected_uom.id:
                    messages.append(
                        "expected uom_po_id='%s' from Splendid symbol '%s' but actual='%s'" % (
                            expected_uom.display_name,
                            symbol,
                            product_tmpl.uom_po_id.display_name,
                        )
                    )

        if messages:
            message = "Product settings not applied for %s: %s" % (
                product_tmpl.display_name,
                "; ".join(messages),
            )
            self._log(
                "products",
                "error",
                message,
                payload,
                external_id or self._product_external_id(payload),
                product_tmpl,
            )
            if raise_on_mismatch:
                raise UserError(_(message))

        return product_tmpl

    def _write_product_vals_safely(self, product_tmpl, vals, payload=None, external_id=False):
        self.ensure_one()
        if not product_tmpl:
            return product_tmpl

        vals = dict(vals or {})

        # For existing products, write ordinary fields first. Inventory/UoM are
        # applied together by _force_product_inventory_uom so Odoo 18 cannot
        # recompute is_storable back to False due to an incompatible type.
        controlled_fields = {
            "type",
            "detailed_type",
            "is_storable",
            "uom_id",
            "uom_po_id",
            "splendid_track_inventory",
            "splendid_uom_symbol",
        }
        general_vals = {k: v for k, v in vals.items() if k not in controlled_fields}
        if general_vals:
            product_tmpl.with_company(self.company_id).sudo().write(general_vals)

        self._force_product_inventory_uom(
            product_tmpl,
            payload=payload,
            external_id=external_id,
            raise_on_mismatch=True,
        )
        return product_tmpl

    def _verify_splendid_product_settings(self, product_tmpl, payload=None, external_id=False):
        # Backward-compatible wrapper for older calls.
        self._force_product_inventory_uom(product_tmpl, payload=payload, external_id=external_id, raise_on_mismatch=False)
        return True

    def _apply_product_inventory_uom_from_payload(self, product_tmpl, payload):
        self.ensure_one()
        return self._force_product_inventory_uom(
            product_tmpl,
            payload=payload,
            external_id=self._product_external_id(payload) if isinstance(payload, dict) else False,
            raise_on_mismatch=False,
        )

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
            "splendid_payment_account_id": str(self._find_value(payload, "accountId") or ""),
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
            "customer_refunds": ("/CustomerRefunds", "/CustomerRefunds/Search"),
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

    def action_sync_expenses(self):
        for rec in self:
            rec = rec._with_target_company()
            rec._sync_expenses()
        return True

    def action_sync_expense_by_id(self):
        self.ensure_one()
        rec = self._with_target_company()
        external_id = str(rec.expense_external_id or "").strip()
        if not external_id:
            raise UserError(_("Enter a Splendid Expense ID first."))
        try:
            with rec.env.cr.savepoint():
                payload = rec._fetch_detail_by_id("/Expenses", external_id)
                if not payload:
                    raise UserError(_("Splendid Expenses/%s returned no record.") % external_id)
                if rec._expense_is_status_30(payload):
                    rec._log("expenses", "skipped", "Expense fetched by ID but skipped because Splendid status is 30.", payload, external_id)
                    rec.last_expenses_sync = fields.Datetime.now()
                    rec.env.cr.commit()
                    return {
                        "type": "ir.actions.client",
                        "tag": "display_notification",
                        "params": {
                            "title": _("Splendid Expense"),
                            "message": _("Expenses/%s has status 30 and was not imported.") % external_id,
                            "type": "warning",
                            "sticky": True,
                        },
                    }
                if rec._expense_is_void(payload):
                    rec._log("expenses", "skipped", "Expense fetched by ID but skipped because Splendid marks it void.", payload, external_id)
                    rec.last_expenses_sync = fields.Datetime.now()
                    rec.env.cr.commit()
                    return {
                        "type": "ir.actions.client",
                        "tag": "display_notification",
                        "params": {
                            "title": _("Splendid Expense"),
                            "message": _("Expenses/%s is void and was not imported.") % external_id,
                            "type": "warning",
                            "sticky": True,
                        },
                    }
                record = rec._import_expense_process(payload)
                rec._log("expenses", "success", "Expense imported/updated as an Odoo journal entry.", payload, external_id, record)
        except Exception as exc:  # pylint: disable=broad-except
            rec._log("expenses", "error", str(exc), {"requested_id": external_id}, external_id)
            raise
        rec.last_expenses_sync = fields.Datetime.now()
        rec.env.cr.commit()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Splendid Expense"),
                "message": _("Expenses/%s imported successfully.") % external_id,
                "type": "success",
                "sticky": False,
            },
        }

    def _fetch_journal_entries_list(self):
        """Discover JournalEntry IDs from the base GET endpoint.

        JournalEntries follows the same two-step migration pattern as the
        sale/purchase processes: first GET the paged collection only to
        discover source IDs, then every row is refreshed from
        ``GET /JournalEntries/{id}`` before any accounting values are used.

        The base JournalEntries GET endpoint does not expose the structured
        date-range body used by ``/Search``.  To keep the connection's date
        controls without changing the discovery endpoint, the returned list
        rows are filtered locally by their summary ``date`` field.
        """
        self.ensure_one()
        rows = self._fetch_collection(
            "/JournalEntries",
            params={"orderBy": "Date", "ascending": "true"},
            use_paging=True,
        )
        if not (self.sync_from_date or self.sync_to_date):
            return rows

        filtered = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            row_date = self._parse_date(self._find_value(row, "date"))
            if not row_date:
                # Keep undated summaries so the authoritative ID GET can
                # decide whether the source record is usable.
                filtered.append(row)
                continue
            if self.sync_from_date and row_date < self.sync_from_date:
                continue
            if self.sync_to_date and row_date > self.sync_to_date:
                continue
            filtered.append(row)
        return filtered

    def _journal_entry_is_void(self, payload):
        return bool(isinstance(payload, dict) and self._safe_bool(self._find_value(payload, "isVoid"), False))

    def _journal_entry_is_status_30(self, payload):
        """Return True for Splendid JournalEntries with status=30.
        
        Status 30 JournalEntries are intentionally excluded from migration.
        For collection rows this check is performed before the ID-detail GET so
        ``GET /JournalEntries/{id}`` is not called for those records.
        """
        if not isinstance(payload, dict):
            return False
        try:
            return int(self._find_value(payload, "status") or 0) == 30
        except (TypeError, ValueError):
            return False

    def _get_or_create_journal_entry_journal(self):
        self.ensure_one()
        Journal = self.env["account.journal"].with_company(self.company_id).sudo()
        journal = self.journal_entry_journal_id
        if journal:
            return journal
        journal = Journal.search([
            ("company_id", "=", self.company_id.id),
            ("type", "=", "general"),
            ("name", "=", "Splendid Journal Entries"),
        ], limit=1)
        if not journal:
            journal = Journal.create({
                "name": "Splendid Journal Entries",
                "type": "general",
                "code": self._unique_journal_code("SPJE"),
                "company_id": self.company_id.id,
                "splendid_is_imported": True,
            })
        self.journal_entry_journal_id = journal.id
        return journal

    def _resolve_journal_entry_partner(self, detail):
        """Use an already-known Splendid customer/vendor as partner when possible.

        JournalEntry details can also reference employees (contactType=30). Those
        are intentionally not invented as res.partner records merely to post a
        GL entry; their source identity stays in line name/raw payload.
        """
        contact_id = self._find_value(detail, "contactId")
        contact = self._find_value(detail, "contact", default={}) or {}
        if not contact_id and isinstance(contact, dict):
            contact_id = self._find_value(contact, "id")
        if not contact_id:
            return self.env["res.partner"].with_company(self.company_id)
        for key in ("customer", "vendor"):
            partner = self._mapped_record(key, contact_id, "res.partner")
            if partner:
                return partner
        # Do not infer a customer/vendor role from a generic Contact payload.
        # If the contact was not already mapped by a dedicated customer/vendor
        # sync, leave partner_id empty and preserve the contact in line name/raw payload.
        return self.env["res.partner"].with_company(self.company_id)

    def _journal_entry_line_name(self, payload, detail, account):
        description = self._find_value(detail, "description")
        contact = self._find_value(detail, "contact", default={}) or {}
        contact_name = self._find_value(contact, "name", "displayName") if isinstance(contact, dict) else False
        contact_code = self._find_value(contact, "code") if isinstance(contact, dict) else False
        pieces = [description]
        if contact_name:
            pieces.append("[%s] %s" % (contact_code, contact_name) if contact_code else str(contact_name))
        if not any(pieces):
            pieces.append(self._find_value(payload, "number") or account.display_name)
        return " - ".join(str(x) for x in pieces if x)[:1000]

    def _prepare_journal_entry_lines(self, payload):
        details = self._find_value(payload, "journalEntryDetails", default=[]) or []
        if not isinstance(details, list) or not details:
            raise UserError(_("Splendid Journal Entry %s has no journalEntryDetails.") % (self._find_value(payload, "number") or self._external_id(payload)))

        company_currency = self.company_id.currency_id
        source_currency = self._find_value(payload, "currency", default={}) or {}
        source_code = self._find_value(source_currency, "code") if isinstance(source_currency, dict) else False
        exchange_rate = self._safe_float(self._find_value(payload, "exchangeRate"), 1.0)
        if source_code and company_currency and str(source_code).upper() != str(company_currency.name).upper():
            raise UserError(_(
                "Splendid Journal Entry %(number)s is in %(source)s while Odoo company currency is %(company)s. "
                "Foreign-currency JournalEntry migration is not guessed; review is required."
            ) % {
                "number": self._find_value(payload, "number") or self._external_id(payload),
                "source": source_code,
                "company": company_currency.name,
            })
        if source_code and abs(exchange_rate - 1.0) > 0.000001 and source_code == company_currency.name:
            # Same currency with a non-1 exchange rate is inconsistent source data.
            raise UserError(_("Splendid Journal Entry %s has exchangeRate=%s for company currency %s.") % (
                self._find_value(payload, "number") or self._external_id(payload), exchange_rate, source_code
            ))

        commands = []
        total_debit = 0.0
        total_credit = 0.0
        for detail in details:
            if not isinstance(detail, dict):
                continue
            debit = self._safe_float(self._find_value(detail, "debit"), 0.0)
            credit = self._safe_float(self._find_value(detail, "credit"), 0.0)
            if debit < 0 or credit < 0:
                raise UserError(_("Negative debit/credit is not supported in Splendid JournalEntry detail %s.") % (self._find_value(detail, "id") or ""))
            if debit and credit:
                raise UserError(_("Splendid JournalEntry detail %s has both debit and credit amounts.") % (self._find_value(detail, "id") or ""))
            if company_currency.is_zero(debit) and company_currency.is_zero(credit):
                continue

            account_payload = self._find_value(detail, "account", default={}) or {}
            account_id = self._find_value(detail, "accountId")
            account_code = self._find_value(account_payload, "code") if isinstance(account_payload, dict) else False
            account = self._resolve_account(account_id, account_code)
            if not account:
                raise UserError(_(
                    "Splendid JournalEntry %(je)s line %(line)s could not map accountId=%(account_id)s code=%(code)s. "
                    "The account was not guessed."
                ) % {
                    "je": self._find_value(payload, "number") or self._external_id(payload),
                    "line": self._find_value(detail, "id") or "",
                    "account_id": account_id or "",
                    "code": account_code or "",
                })

            partner = self._resolve_journal_entry_partner(detail)
            vals = {
                "name": self._journal_entry_line_name(payload, detail, account),
                "account_id": account.id,
                "debit": debit,
                "credit": credit,
            }
            if partner:
                vals["partner_id"] = partner.id
            commands.append((0, 0, vals))
            total_debit += debit
            total_credit += credit

        if not commands:
            raise UserError(_("Splendid Journal Entry %s has no non-zero accounting lines.") % (self._find_value(payload, "number") or self._external_id(payload)))
        if not company_currency.is_zero(total_debit - total_credit):
            raise UserError(_(
                "Splendid Journal Entry %(number)s is not balanced: debit=%(debit).2f credit=%(credit).2f."
            ) % {
                "number": self._find_value(payload, "number") or self._external_id(payload),
                "debit": total_debit,
                "credit": total_credit,
            })
        return commands, total_debit, total_credit

    def _import_journal_entry_process(self, payload):
        self.ensure_one()
        if not isinstance(payload, dict) or not payload:
            raise UserError(_("Empty Splendid JournalEntry payload."))
        external_id = self._external_id(payload)
        number = self._find_value(payload, "number") or ("JE-%s" % external_id)
        if not external_id:
            raise UserError(_("Splendid JournalEntry has no ID."))
        if self._journal_entry_is_status_30(payload):
            raise UserError(_("Splendid Journal Entry %s has status 30 and is excluded from migration.") % number)
        if self._journal_entry_is_void(payload):
            existing = self._mapped_record("journal_entry", external_id, "account.move")
            if existing:
                raise UserError(_(
                    "Splendid Journal Entry %(number)s is void but Odoo move %(move)s already exists. "
                    "No automatic delete/reversal was performed."
                ) % {"number": number, "move": existing.display_name})
            return self.env["account.move"].with_company(self.company_id)

        lines, total_debit, total_credit = self._prepare_journal_entry_lines(payload)
        journal = self._get_or_create_journal_entry_journal()
        Move = self.env["account.move"].with_company(self.company_id).sudo()
        mapping = self._map_search("journal_entry", external_id, "account.move")
        move = self._mapped_record("journal_entry", external_id, "account.move")
        if not move and "splendid_journal_entry_id" in Move._fields:
            move = Move.search([
                ("company_id", "=", self.company_id.id),
                ("splendid_journal_entry_id", "=", str(external_id)),
            ], limit=1)

        payload_hash = self._payload_hash(payload)
        if move and move.state == "posted":
            old_hash = mapping.last_payload_hash if mapping else self._payload_hash(move.splendid_raw_payload or {})
            if old_hash and old_hash != payload_hash:
                raise UserError(_(
                    "Splendid Journal Entry %(number)s changed after the Odoo journal entry was posted. "
                    "Posted accounting was not rewritten automatically."
                ) % {"number": number})
            self._set_mapping("journal_entry", external_id, move, payload, number)
            return move

        date_value = self._parse_date(self._find_value(payload, "date"))
        source_ref = self._find_value(payload, "reference")
        narration = self._find_value(payload, "narration")
        ref = str(number)
        if source_ref:
            ref = "%s | %s" % (number, source_ref)
        vals = {
            "move_type": "entry",
            "journal_id": journal.id,
            "date": date_value,
            "ref": ref[:2000],
            "line_ids": lines,
            "splendid_journal_entry_id": str(external_id),
            "splendid_source_model": "JournalEntry",
            "splendid_is_imported": True,
            "splendid_raw_payload": payload,
        }
        if narration and "narration" in Move._fields:
            vals["narration"] = narration

        if move:
            if move.state != "draft":
                raise UserError(_("Existing Odoo journal entry %s is not Draft and cannot be safely replaced.") % move.display_name)
            move.line_ids.unlink()
            move.write(vals)
        else:
            move = Move.create(vals)

        self._set_mapping("journal_entry", external_id, move, payload, number)
        if self.auto_post_journal_entries and move.state == "draft":
            move.action_post()
        return move

    def _sync_journal_entries(self):
        self.ensure_one()
        rows = self._fetch_journal_entries_list()
        imported = 0
        failed = 0
        skipped_void = 0
        skipped_status_30 = 0
        for row in rows:
            external_id = self._external_id(row)
            # IMPORTANT: status 30 is checked on the base GET row before the
            # detail request. This intentionally avoids GET /JournalEntries/{id}
            # for JournalEntries that Splendid marks with status 30.
            if self._journal_entry_is_status_30(row):
                skipped_status_30 += 1
                self._log(
                    "journal_entries",
                    "skipped",
                    "Skipped Splendid JournalEntry with status 30 before ID detail GET.",
                    row,
                    external_id,
                )
                continue
            if self._journal_entry_is_void(row):
                skipped_void += 1
                self._log("journal_entries", "skipped", "Skipped void Splendid JournalEntry.", row, external_id)
                continue
            try:
                with self.env.cr.savepoint():
                    payload = self._fetch_detail_by_id("/JournalEntries", external_id)
                    # Defensive re-check in case the summary row did not carry
                    # status or the source changed between list and detail GET.
                    if self._journal_entry_is_status_30(payload):
                        skipped_status_30 += 1
                        self._log("journal_entries", "skipped", "Skipped Splendid JournalEntry detail with status 30.", payload, external_id)
                        continue
                    if self._journal_entry_is_void(payload):
                        skipped_void += 1
                        self._log("journal_entries", "skipped", "Skipped void Splendid JournalEntry detail.", payload, external_id)
                        continue
                    record = self._import_journal_entry_process(payload)
                    imported += 1
                    self._log(
                        "journal_entries",
                        "success",
                        "Journal entry imported/updated%s; debit=%.2f credit=%.2f" % (
                            " and posted" if record and record.state == "posted" else " as Draft",
                            sum(record.line_ids.mapped("debit")) if record else 0.0,
                            sum(record.line_ids.mapped("credit")) if record else 0.0,
                        ),
                        payload,
                        external_id,
                        record,
                    )
            except Exception as exc:  # pylint: disable=broad-except
                failed += 1
                _logger.exception("Failed to import Splendid JournalEntry %s", external_id)
                self._log("journal_entries", "error", str(exc), row, external_id)
        self._set_count("journal_entries", len(rows), imported, failed)
        self.last_journal_entries_sync = fields.Datetime.now()
        self._log(
            "journal_entries",
            "success" if not failed else "error",
            "JournalEntries sync summary: fetched=%s imported=%s skipped_status_30=%s skipped_void=%s failed=%s" % (
                len(rows), imported, skipped_status_30, skipped_void, failed
            ),
            {
                "fetched": len(rows),
                "imported": imported,
                "skipped_status_30": skipped_status_30,
                "skipped_void": skipped_void,
                "failed": failed,
            },
        )
        self.env.cr.commit()
        return True

    def _fetch_expenses_list(self):
        """Discover Expense IDs from GET /Expenses, then import by ID.

        This intentionally mirrors Sale/Purchase/JournalEntries migration:
        collection GET is discovery only; accounting values are read only from
        GET /Expenses/{id}. Rows with status=30 are skipped before the ID GET.
        """
        self.ensure_one()
        rows = self._fetch_collection(
            "/Expenses",
            params={"orderBy": "Date", "ascending": "true"},
            use_paging=True,
        )
        if not (self.sync_from_date or self.sync_to_date):
            return rows
        filtered = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            row_date = self._parse_date(self._find_value(row, "date"))
            if not row_date:
                filtered.append(row)
                continue
            if self.sync_from_date and row_date < self.sync_from_date:
                continue
            if self.sync_to_date and row_date > self.sync_to_date:
                continue
            filtered.append(row)
        return filtered

    def _expense_is_void(self, payload):
        return bool(isinstance(payload, dict) and self._safe_bool(self._find_value(payload, "isVoid"), False))

    def _expense_is_status_30(self, payload):
        """Defensive business rule requested for Expenses: never import status 30."""
        if not isinstance(payload, dict):
            return False
        try:
            return int(self._find_value(payload, "status") or 0) == 30
        except (TypeError, ValueError):
            return False

    def _get_or_create_expense_journal(self):
        self.ensure_one()
        Journal = self.env["account.journal"].with_company(self.company_id).sudo()
        journal = self.expense_journal_id
        if journal:
            return journal
        journal = Journal.search([
            ("company_id", "=", self.company_id.id),
            ("type", "=", "general"),
            ("name", "=", "Splendid Expenses"),
        ], limit=1)
        if not journal:
            code = "SPEX"
            # Avoid a code collision without guessing another accounting journal.
            if Journal.search_count([("company_id", "=", self.company_id.id), ("code", "=", code)]):
                code = "SPX"
            journal = Journal.create({
                "name": "Splendid Expenses",
                "code": code,
                "type": "general",
                "company_id": self.company_id.id,
                "splendid_is_imported": True,
            })
        self.expense_journal_id = journal.id
        return journal

    def _resolve_expense_partner(self, payload):
        contact_id = self._find_value(payload, "contactId")
        contact = self._find_value(payload, "contact", default={}) or {}
        if not contact_id and isinstance(contact, dict):
            contact_id = self._find_value(contact, "id")
        if not contact_id:
            return self.env["res.partner"].with_company(self.company_id)
        for key in ("vendor", "customer"):
            partner = self._mapped_record(key, contact_id, "res.partner")
            if partner:
                return partner
        if isinstance(contact, dict) and contact:
            contact_type = self._find_value(contact, "contactType")
            code = str(self._find_value(contact, "code") or "").upper()
            try:
                if int(contact_type or 0) == 20 or code.startswith("V-"):
                    return self._import_vendors(contact)
                if int(contact_type or 0) == 10 or code.startswith("C-"):
                    return self._import_customers(contact)
            except (TypeError, ValueError):
                pass
        return self.env["res.partner"].with_company(self.company_id)

    def _expense_tax_account(self, tax_item, expense_number):
        tax_payload = self._find_value(tax_item, "tax", default={}) or {}
        account_id = self._find_value(tax_payload, "accountInId") if isinstance(tax_payload, dict) else False
        account_obj = self._find_value(tax_payload, "accountIn", default={}) if isinstance(tax_payload, dict) else {}
        account_code = self._find_value(account_obj, "code") if isinstance(account_obj, dict) else False
        account = self._resolve_account(account_id, account_code)
        if account:
            return account

        tax_id = self._find_value(tax_item, "taxId")
        if tax_id:
            Tax = self.env["account.tax"].with_company(self.company_id).sudo()
            tax = Tax.search([
                ("company_id", "=", self.company_id.id),
                ("splendid_tax_id", "=", str(tax_id)),
                ("type_tax_use", "=", "purchase"),
            ], limit=1)
            if tax:
                tax_lines = tax.invoice_repartition_line_ids.filtered(
                    lambda line: getattr(line, "repartition_type", False) == "tax" and line.account_id
                )
                if len(tax_lines) == 1:
                    return tax_lines.account_id
        raise UserError(_(
            "Splendid Expense %(expense)s tax %(tax)s has no exact purchase/input tax account. "
            "The integration did not guess an account."
        ) % {"expense": expense_number, "tax": tax_id or ""})

    def _prepare_expense_lines(self, payload):
        details = self._find_value(payload, "expenseDetails", default=[]) or []
        number = self._find_value(payload, "number") or self._external_id(payload)
        if not isinstance(details, list) or not details:
            raise UserError(_("Splendid Expense %s has no expenseDetails.") % number)

        company_currency = self.company_id.currency_id
        source_currency = self._find_value(payload, "currency", default={}) or {}
        source_code = self._find_value(source_currency, "code") if isinstance(source_currency, dict) else False
        exchange_rate = self._safe_float(self._find_value(payload, "exchangeRate"), 1.0)
        if source_code and company_currency and str(source_code).upper() != str(company_currency.name).upper():
            raise UserError(_(
                "Splendid Expense %(number)s is in %(source)s while Odoo company currency is %(company)s. "
                "Foreign-currency Expense migration is not guessed."
            ) % {"number": number, "source": source_code, "company": company_currency.name})
        if source_code and abs(exchange_rate - 1.0) > 0.000001 and source_code == company_currency.name:
            raise UserError(_("Splendid Expense %s has exchangeRate=%s for company currency %s.") % (number, exchange_rate, source_code))

        partner = self._resolve_expense_partner(payload)
        commands = []
        total_debit = 0.0
        total_credit = 0.0

        for detail in details:
            if not isinstance(detail, dict):
                continue
            account_payload = self._find_value(detail, "account", default={}) or {}
            account_id = self._find_value(detail, "accountId")
            account_code = self._find_value(account_payload, "code") if isinstance(account_payload, dict) else False
            expense_account = self._resolve_account(account_id, account_code)
            if not expense_account:
                raise UserError(_(
                    "Splendid Expense %(expense)s line %(line)s could not map expense accountId=%(account_id)s code=%(code)s. "
                    "The account was not guessed."
                ) % {
                    "expense": number,
                    "line": self._find_value(detail, "id") or "",
                    "account_id": account_id or "",
                    "code": account_code or "",
                })

            gross = self._safe_float(self._find_value(detail, "grossAmount"), 0.0)
            tax_amount = self._safe_float(self._find_value(detail, "taxAmount"), 0.0)
            net = self._safe_float(self._find_value(detail, "netAmount"), gross + tax_amount)
            if gross < 0 or tax_amount < 0 or net < 0:
                raise UserError(_("Negative Expense amounts are not supported for %s.") % number)
            description = self._find_value(detail, "description") or expense_account.display_name

            if company_currency.is_zero(tax_amount):
                debit_amount = net
                if company_currency.is_zero(debit_amount):
                    continue
                vals = {
                    "name": str(description)[:1000],
                    "account_id": expense_account.id,
                    "debit": debit_amount,
                    "credit": 0.0,
                }
                if partner:
                    vals["partner_id"] = partner.id
                commands.append((0, 0, vals))
                total_debit += debit_amount
                continue

            taxes = self._find_value(detail, "taxes", default=[]) or []
            if not isinstance(taxes, list) or not taxes:
                raise UserError(_(
                    "Splendid Expense %(expense)s line %(line)s has taxAmount=%(tax).2f but no tax detail/account payload."
                ) % {"expense": number, "line": self._find_value(detail, "id") or "", "tax": tax_amount})
            tax_sum = sum(self._safe_float(self._find_value(item, "taxAmount"), 0.0) for item in taxes if isinstance(item, dict))
            if not company_currency.is_zero(tax_sum - tax_amount):
                raise UserError(_(
                    "Splendid Expense %(expense)s tax details do not match line taxAmount: detail taxes=%(detail).2f line tax=%(line).2f."
                ) % {"expense": number, "detail": tax_sum, "line": tax_amount})

            # Normal input tax: net = gross + tax. Withholding-style tax:
            # net = gross - tax. Any other relationship is stopped for review.
            is_input_tax = company_currency.is_zero(net - (gross + tax_amount))
            is_withholding = company_currency.is_zero(net - (gross - tax_amount))
            if not (is_input_tax or is_withholding):
                raise UserError(_(
                    "Splendid Expense %(expense)s line %(line)s has ambiguous tax arithmetic: gross=%(gross).2f tax=%(tax).2f net=%(net).2f."
                ) % {
                    "expense": number,
                    "line": self._find_value(detail, "id") or "",
                    "gross": gross,
                    "tax": tax_amount,
                    "net": net,
                })

            if not company_currency.is_zero(gross):
                vals = {
                    "name": str(description)[:1000],
                    "account_id": expense_account.id,
                    "debit": gross,
                    "credit": 0.0,
                }
                if partner:
                    vals["partner_id"] = partner.id
                commands.append((0, 0, vals))
                total_debit += gross

            for tax_item in taxes:
                if not isinstance(tax_item, dict):
                    continue
                amount = self._safe_float(self._find_value(tax_item, "taxAmount"), 0.0)
                if company_currency.is_zero(amount):
                    continue
                tax_account = self._expense_tax_account(tax_item, number)
                tax_payload = self._find_value(tax_item, "tax", default={}) or {}
                tax_name = self._find_value(tax_payload, "name", "abbreviation") if isinstance(tax_payload, dict) else False
                vals = {
                    "name": ("%s - %s" % (description, tax_name or "Tax"))[:1000],
                    "account_id": tax_account.id,
                    "debit": amount if is_input_tax else 0.0,
                    "credit": amount if is_withholding else 0.0,
                }
                if partner:
                    vals["partner_id"] = partner.id
                commands.append((0, 0, vals))
                total_debit += vals["debit"]
                total_credit += vals["credit"]

        source_account_payload = self._find_value(payload, "account", default={}) or {}
        source_account_id = self._find_value(payload, "accountId")
        source_account_code = self._find_value(source_account_payload, "code") if isinstance(source_account_payload, dict) else False
        source_account = self._resolve_account(source_account_id, source_account_code)
        if not source_account:
            raise UserError(_(
                "Splendid Expense %(expense)s could not map payment/source accountId=%(account_id)s code=%(code)s. "
                "The account was not guessed."
            ) % {"expense": number, "account_id": source_account_id or "", "code": source_account_code or ""})

        source_net = self._safe_float(self._find_value(payload, "netAmount"), 0.0)
        if source_net < 0:
            raise UserError(_("Splendid Expense %s has a negative netAmount.") % number)
        if company_currency.is_zero(source_net):
            raise UserError(_("Splendid Expense %s has zero netAmount.") % number)

        source_vals = {
            "name": ("%s - %s" % (number, source_account.display_name))[:1000],
            "account_id": source_account.id,
            "debit": 0.0,
            "credit": source_net,
        }
        if partner:
            source_vals["partner_id"] = partner.id
        commands.append((0, 0, source_vals))
        total_credit += source_net

        if not commands:
            raise UserError(_("Splendid Expense %s has no accounting lines.") % number)
        if not company_currency.is_zero(total_debit - total_credit):
            raise UserError(_(
                "Splendid Expense %(number)s is not balanced from source payload: debit=%(debit).2f credit=%(credit).2f. "
                "No balancing/write-off line was created."
            ) % {"number": number, "debit": total_debit, "credit": total_credit})
        return commands, total_debit, total_credit

    def _import_expense_process(self, payload):
        self.ensure_one()
        if not isinstance(payload, dict) or not payload:
            raise UserError(_("Empty Splendid Expense payload."))
        external_id = self._external_id(payload)
        number = self._find_value(payload, "number") or ("E-%s" % external_id)
        if not external_id:
            raise UserError(_("Splendid Expense has no ID."))
        if self._expense_is_status_30(payload):
            raise UserError(_("Splendid Expense %s has status 30 and is excluded from migration.") % number)
        if self._expense_is_void(payload):
            existing = self._mapped_record("expense", external_id, "account.move")
            if existing:
                raise UserError(_(
                    "Splendid Expense %(number)s is void but Odoo move %(move)s already exists. "
                    "No automatic delete/reversal was performed."
                ) % {"number": number, "move": existing.display_name})
            return self.env["account.move"].with_company(self.company_id)

        lines, total_debit, total_credit = self._prepare_expense_lines(payload)
        journal = self._get_or_create_expense_journal()
        Move = self.env["account.move"].with_company(self.company_id).sudo()
        mapping = self._map_search("expense", external_id, "account.move")
        move = self._mapped_record("expense", external_id, "account.move")
        if not move and "splendid_expense_id" in Move._fields:
            move = Move.search([
                ("company_id", "=", self.company_id.id),
                ("splendid_expense_id", "=", str(external_id)),
            ], limit=1)

        payload_hash = self._payload_hash(payload)
        if move and move.state == "posted":
            old_hash = mapping.last_payload_hash if mapping else self._payload_hash(move.splendid_raw_payload or {})
            if old_hash and old_hash != payload_hash:
                raise UserError(_(
                    "Splendid Expense %(number)s changed after the Odoo journal entry was posted. "
                    "Posted accounting was not rewritten automatically."
                ) % {"number": number})
            self._set_mapping("expense", external_id, move, payload, number)
            return move

        date_value = self._parse_date(self._find_value(payload, "date"))
        source_ref = self._find_value(payload, "reference")
        narration = self._find_value(payload, "narration") or self._find_value(payload, "comments")
        ref = str(number)
        if source_ref:
            ref = "%s | %s" % (number, source_ref)
        vals = {
            "move_type": "entry",
            "journal_id": journal.id,
            "date": date_value,
            "ref": ref[:2000],
            "line_ids": lines,
            "splendid_expense_id": str(external_id),
            "splendid_source_model": "Expense",
            "splendid_is_imported": True,
            "splendid_raw_payload": payload,
        }
        if narration and "narration" in Move._fields:
            vals["narration"] = narration

        if move:
            if move.state != "draft":
                raise UserError(_("Existing Odoo expense journal entry %s is not Draft and cannot be safely replaced.") % move.display_name)
            move.line_ids.unlink()
            move.write(vals)
        else:
            move = Move.create(vals)

        self._set_mapping("expense", external_id, move, payload, number)
        if self.auto_post_expenses and move.state == "draft":
            move.action_post()
        return move

    def _sync_expenses(self):
        self.ensure_one()
        rows = self._fetch_expenses_list()
        imported = 0
        failed = 0
        skipped_void = 0
        skipped_status_30 = 0
        for row in rows:
            external_id = self._external_id(row)
            # User-requested rule: status 30 is filtered at collection level so
            # Expenses/{id} is not called for those source records.
            if self._expense_is_status_30(row):
                skipped_status_30 += 1
                self._log("expenses", "skipped", "Skipped Splendid Expense with status 30 before ID detail GET.", row, external_id)
                continue
            if self._expense_is_void(row):
                skipped_void += 1
                self._log("expenses", "skipped", "Skipped void Splendid Expense before ID detail GET.", row, external_id)
                continue
            try:
                with self.env.cr.savepoint():
                    payload = self._fetch_detail_by_id("/Expenses", external_id)
                    if not payload:
                        raise UserError(_("Splendid Expenses/%s returned no record.") % external_id)
                    if self._expense_is_status_30(payload):
                        skipped_status_30 += 1
                        self._log("expenses", "skipped", "Skipped Splendid Expense detail with status 30.", payload, external_id)
                        continue
                    if self._expense_is_void(payload):
                        skipped_void += 1
                        self._log("expenses", "skipped", "Skipped void Splendid Expense detail.", payload, external_id)
                        continue
                    record = self._import_expense_process(payload)
                    imported += 1
                    self._log(
                        "expenses",
                        "success",
                        "Expense imported/updated%s; debit=%.2f credit=%.2f" % (
                            " and posted" if record and record.state == "posted" else " as Draft",
                            sum(record.line_ids.mapped("debit")) if record else 0.0,
                            sum(record.line_ids.mapped("credit")) if record else 0.0,
                        ),
                        payload,
                        external_id,
                        record,
                    )
            except Exception as exc:  # pylint: disable=broad-except
                failed += 1
                _logger.exception("Failed to import Splendid Expense %s", external_id)
                self._log("expenses", "error", str(exc), row, external_id)
        self._set_count("expenses", len(rows), imported, failed)
        self.last_expenses_sync = fields.Datetime.now()
        self._log(
            "expenses",
            "success" if not failed else "error",
            "Expenses sync summary: fetched=%s imported=%s skipped_status_30=%s skipped_void=%s failed=%s" % (
                len(rows), imported, skipped_status_30, skipped_void, failed
            ),
            {
                "fetched": len(rows),
                "imported": imported,
                "skipped_status_30": skipped_status_30,
                "skipped_void": skipped_void,
                "failed": failed,
            },
        )
        self.env.cr.commit()
        return True

    def _sync_sales_process(self):
        self.ensure_one()
        self._sync_sale_invoices()
        self._sync_sale_returns()
        self._sync_customer_refunds()
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
                with self.env.cr.savepoint():
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
                with self.env.cr.savepoint():
                    payload = self._fetch_detail_by_id("/SaleReturns", external_id)
                    record = self._import_sale_return_process(payload)
                    imported += 1
                    self._log("sale_returns", "success", "Sale return imported/updated", payload, external_id, record)
                    self._sync_customer_refunds_from_sale_return(payload)
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
                with self.env.cr.savepoint():
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
                with self.env.cr.savepoint():
                    payment_payload = self._fetch_detail_by_id("/CustomerPayments", payment_id)
                    payment = self._import_customer_payment_process(payment_payload)
                    self._log("customer_payments", "success", "Customer payment imported from sale invoice settlement", payment_payload, payment_id, payment)
            except Exception as exc:  # pylint: disable=broad-except
                self._log("customer_payments", "error", str(exc), item, payment_id)

    def _sync_customer_refunds(self):
        self.ensure_one()
        rows = self._fetch_sales_list("customer_refunds")
        imported = failed = 0
        for row in rows:
            external_id = self._external_id(row)
            try:
                with self.env.cr.savepoint():
                    payload = self._fetch_detail_by_id("/CustomerRefunds", external_id)
                    record = self._import_customer_refund_process(payload)
                    imported += 1
                    self._log("customer_refunds", "success", "Customer refund imported/updated", payload, external_id, record)
            except Exception as exc:  # pylint: disable=broad-except
                failed += 1
                _logger.exception("Failed to import Splendid customer refund %s", external_id)
                self._log("customer_refunds", "error", str(exc), row, external_id)
        self._set_count("customer_refunds", len(rows), imported, failed)
        self.last_customer_refunds_sync = fields.Datetime.now()
        self.env.cr.commit()
        return True

    def _sync_customer_refunds_from_sale_return(self, sale_return_payload):
        for item in self._find_value(sale_return_payload, "customerSingleSettledEntryItems", default=[]) or []:
            if not isinstance(item, dict):
                continue
            if str(self._find_value(item, "source", default="")).lower() != "customerrefund":
                continue
            refund_id = self._find_value(item, "sourceId")
            if not refund_id:
                continue
            try:
                with self.env.cr.savepoint():
                    refund_payload = self._fetch_detail_by_id("/CustomerRefunds", refund_id)
                    refund = self._import_customer_refund_process(refund_payload)
                    self._log("customer_refunds", "success", "Customer refund imported from sale return settlement", refund_payload, refund_id, refund)
            except Exception as exc:  # pylint: disable=broad-except
                self._log("customer_refunds", "error", str(exc), item, refund_id)

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
        """Resolve/create a product for Sale/Purchase transaction lines.

        Critical rule: a transaction line may only contain productId.  If the
        embedded product payload is missing (or has no symbol), fetch
        /Products/{productId} and run the normal _import_products() path.  That
        guarantees Track Inventory + UoM are identical whether the product was
        first seen in Master Data, Sales, or Purchase.
        """
        self.ensure_one()
        Product = self.env["product.template"].with_company(self.company_id).sudo()
        external_id = self._find_value(line, "productId", "ProductId", "itemId", "productID")
        nested = self._nested(line, "product") or self._nested(line, "item")

        product = self._mapped_record("product", external_id, "product.template") if external_id else Product

        # Build a complete product payload whenever an external product ID exists.
        # If the line already contains a nested symbol no API call is needed; if
        # symbol is missing, /Products/{id} supplies it.
        product_payload = {}
        if external_id:
            product_payload = self._complete_splendid_product_payload(
                nested,
                external_id=external_id,
                force_detail=not bool(str(self._find_value(nested, "symbol") or "").strip()),
            )
        elif nested:
            product_payload = nested

        if product:
            # Existing mapped product: still apply current Splendid inventory/UoM
            # data so a product first created by an older module is repaired.
            if product_payload:
                return self._import_products(product_payload)
            return product

        if product_payload:
            return self._import_products(product_payload)

        # Last fallback when Splendid omitted productId but supplied a SKU.
        sku = self._clean_product_code(self._find_value(line, "sku", "productCode", "code", "barcode"))
        if sku:
            domain = [("default_code", "=", sku)]
            if "company_id" in Product._fields:
                domain = ["&"] + domain + ["|", ("company_id", "=", False), ("company_id", "=", self.company_id.id)]
            product = Product.search(domain, limit=1)
            if product:
                return product

        raise UserError(_(
            "Product could not be resolved for Splendid line %s (productId=%s)."
        ) % (self._find_value(line, "id") or "", external_id or ""))

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
        # Splendid is the tax source of truth for imported sales.  Always
        # assign the M2M explicitly, including an empty list, so Odoo product
        # Customer Taxes are never injected when Splendid sent no line tax.
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
        # Never inherit/default Odoo product Customer Taxes on Splendid
        # invoices/credit notes.  Use exactly the Splendid line taxes; when
        # Splendid has none, tax_ids must be explicitly empty.
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
        if (
            original_invoice
            and credit_note.state == "posted"
            and self.auto_reconcile_customer_payments
            and not self.env.context.get("skip_splendid_customer_auto_reconcile")
        ):
            # _reconcile_moves expects an Odoo recordset because it uses mapped()/filtered().
            # Passing a Python list here caused Sale Return sync to fail and roll back.
            self._reconcile_moves(original_invoice | credit_note)
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

    def _customer_payment_account_detail(self, payload, detail_field, label):
        """Return the single Splendid liquidity-account detail for a customer payment/refund.

        Odoo account.payment can only use one journal. If Splendid splits one
        payment/refund across multiple liquidity accounts, do not guess a journal.
        """
        details = [
            line for line in (self._find_value(payload, detail_field, default=[]) or [])
            if isinstance(line, dict)
            and self._safe_float(self._find_value(line, "amount"), 0.0) > 0.0
        ]
        if not details:
            return {}

        account_keys = []
        account_detail = False
        for line in details:
            account_id = self._find_value(line, "accountId")
            account_code = self._find_value(self._nested(line, "account"), "code")
            key = str(account_id or account_code or "").strip()
            if key and key not in account_keys:
                account_keys.append(key)
            if key and not account_detail:
                account_detail = line
        if len(account_keys) > 1:
            raise UserError(_(
                "Splendid %s %s uses multiple payment accounts (%s). "
                "One Odoo payment cannot safely map to more than one Bank/Cash journal."
            ) % (
                label,
                self._find_value(payload, "number") or self._external_id(payload),
                ", ".join(account_keys),
            ))
        # If any positive detail carries the exact account mapping, prefer that
        # detail instead of blindly using the first instrument row.
        return account_detail or details[0]

    def _customer_payment_mode(self, payload, detail_field, label):
        """Return the single positive-detail paymentMode, or False when absent/mixed.

        Splendid paymentMode 20 is treated as cheque only when every positive
        payment detail uses that same mode. Mixed payment modes remain on the
        existing exact-account / bank-name resolution path because one Odoo
        account.payment can only use one liquidity journal.
        """
        details = [
            line for line in (self._find_value(payload, detail_field, default=[]) or [])
            if isinstance(line, dict)
            and self._safe_float(self._find_value(line, "amount"), 0.0) > 0.0
        ]
        modes = set()
        for line in details:
            raw_mode = self._find_value(line, "paymentMode")
            if raw_mode in (None, False, ""):
                instrument = self._nested(line, "instrument")
                raw_mode = self._find_value(instrument, "paymentMode")
            if raw_mode in (None, False, ""):
                continue
            try:
                modes.add(int(float(raw_mode)))
            except (TypeError, ValueError):
                modes.add(str(raw_mode).strip())

        if len(modes) == 1:
            return next(iter(modes))
        return False

    def _cheque_account_company_domain(self):
        Account = self.env["account.account"]
        if "company_id" in Account._fields:
            return [("company_id", "=", self.company_id.id)]
        if "company_ids" in Account._fields:
            return [("company_ids", "in", self.company_id.id)]
        return []

    def _get_or_create_cheque_clearing_account(self):
        """Return a dedicated asset_cash account for received/issued cheques."""
        self.ensure_one()
        Account = self.env["account.account"].with_company(self.company_id).sudo()
        domain = [("splendid_is_cheque_clearing", "=", True)] + self._cheque_account_company_domain()
        account = Account.search(domain, limit=1)
        if account:
            return account

        # Reuse only an exact liquidity account previously created for this
        # purpose; do not point the Cheque journal at BAHL Petty Cash / Store.
        exact_domain = [
            ("name", "=", "Cheques in Hand"),
            ("account_type", "=", "asset_cash"),
        ] + self._cheque_account_company_domain()
        account = Account.search(exact_domain, limit=1)
        if account:
            account.write({"splendid_is_cheque_clearing": True})
            return account

        code = "CHQ"
        search_new_code = getattr(Account, "_search_new_account_code", None)
        if search_new_code:
            try:
                code = search_new_code(code, cache={})
            except Exception:
                code = "CHQ"
        # Defensive fallback for installations where _search_new_account_code
        # is unavailable or localization constraints make CHQ already occupied.
        if Account.search([("code", "=", code)] + self._cheque_account_company_domain(), limit=1):
            seq = 1
            while True:
                candidate = "CHQ%s" % seq
                if not Account.search([("code", "=", candidate)] + self._cheque_account_company_domain(), limit=1):
                    code = candidate
                    break
                seq += 1

        vals = {
            "name": "Cheques in Hand",
            "code": code,
            "account_type": "asset_cash",
            "splendid_is_imported": True,
            "splendid_is_cheque_clearing": True,
        }
        if "company_id" in Account._fields:
            vals["company_id"] = self.company_id.id
        elif "company_ids" in Account._fields:
            vals["company_ids"] = [(4, self.company_id.id)]
        return Account.create(vals)

    def _ensure_cheque_journal_payment_methods(self, journal, account):
        """Ensure the Cheque journal has inbound/outbound manual methods using its clearing account."""
        PaymentMethod = self.env["account.payment.method"].sudo()
        MethodLine = self.env["account.payment.method.line"].with_company(self.company_id).sudo()
        for payment_type in ("inbound", "outbound"):
            method = PaymentMethod.search([
                ("code", "=", "manual"),
                ("payment_type", "=", payment_type),
            ], limit=1)
            if not method:
                continue
            line = MethodLine.search([
                ("journal_id", "=", journal.id),
                ("payment_method_id", "=", method.id),
            ], limit=1)
            if not line:
                line = MethodLine.create({
                    "name": method.name,
                    "journal_id": journal.id,
                    "payment_method_id": method.id,
                    "payment_account_id": account.id,
                })
            elif line.payment_account_id != account:
                line.write({"payment_account_id": account.id})
        journal.invalidate_recordset(["inbound_payment_method_line_ids", "outbound_payment_method_line_ids"])
        return journal

    def _get_or_create_cheque_journal(self):
        """Return one company-specific Cheque Bank journal for Splendid paymentMode 20."""
        self.ensure_one()
        Journal = self.env["account.journal"].with_company(self.company_id).sudo()
        account = self._get_or_create_cheque_clearing_account()
        journal = Journal.search([
            ("company_id", "=", self.company_id.id),
            ("splendid_is_cheque_journal", "=", True),
        ], limit=1)
        if not journal:
            journal = Journal.create({
                "name": "Cheque",
                "type": "bank",
                "code": self._unique_journal_code("CHQ"),
                "company_id": self.company_id.id,
                "default_account_id": account.id,
                "splendid_is_imported": True,
                "splendid_is_cheque_journal": True,
            })
        else:
            vals = {}
            if journal.type != "bank":
                vals["type"] = "bank"
            if journal.default_account_id != account:
                vals["default_account_id"] = account.id
            if vals:
                journal.write(vals)
        self._ensure_cheque_journal_payment_methods(journal, account)
        return journal

    def _customer_payment_bank_name(self, payload, detail_field, label):
        """Return one unambiguous bankName from Splendid payment instrument lines."""
        details = [
            line for line in (self._find_value(payload, detail_field, default=[]) or [])
            if isinstance(line, dict)
            and self._safe_float(self._find_value(line, "amount"), 0.0) > 0.0
        ]
        bank_names = {}
        for line in details:
            instrument = self._nested(line, "instrument")
            bank_name = (
                self._find_value(line, "bankName")
                or self._find_value(instrument, "bankName")
                or self._find_value(self._nested(line, "bank"), "name")
            )
            bank_name = str(bank_name or "").strip()
            if bank_name:
                bank_names.setdefault(bank_name.casefold(), bank_name)

        if len(bank_names) > 1:
            raise UserError(_(
                "Splendid %s %s uses multiple banks (%s) while payment accountId/account code is missing. "
                "One Odoo payment can only use one Bank journal, so the journal was not guessed."
            ) % (
                label,
                self._find_value(payload, "number") or self._external_id(payload),
                ", ".join(sorted(bank_names.values())),
            ))
        return next(iter(bank_names.values()), False)

    def _find_customer_payment_journal_by_bank_name(self, bank_name, payload, label):
        """Resolve an existing Odoo Bank journal from Splendid instrument bankName.

        This fallback is only used when Splendid payment details do not contain
        accountId/account code. It never falls back to an unrelated default bank.
        """
        self.ensure_one()
        target = str(bank_name or "").strip().casefold()
        Journal = self.env["account.journal"].with_company(self.company_id).sudo()
        journals = Journal.search([
            ("company_id", "=", self.company_id.id),
            ("type", "=", "bank"),
        ])

        def _norm(value):
            return str(value or "").strip().casefold()

        # Best match: the journal's linked bank account belongs to the exact
        # res.bank named by Splendid (e.g. BAHL).
        linked = journals.filtered(
            lambda j: j.bank_account_id
            and j.bank_account_id.bank_id
            and _norm(j.bank_account_id.bank_id.name) == target
        )
        if len(linked) == 1:
            return linked
        if len(linked) > 1:
            raise UserError(_(
                "Splendid %s %s uses bank '%s', but Odoo has multiple Bank journals linked to that bank: %s. "
                "The integration cannot choose an account by bank name alone."
            ) % (
                label,
                self._find_value(payload, "number") or self._external_id(payload),
                bank_name,
                ", ".join(linked.mapped("display_name")),
            ))

        # Compatibility fallback for journals that were created manually and
        # have no bank_id relation filled in: accept an exact journal name/code.
        exact = journals.filtered(
            lambda j: _norm(j.name) == target or _norm(j.code) == target
        )
        if len(exact) == 1:
            return exact
        if len(exact) > 1:
            raise UserError(_(
                "Splendid %s %s uses bank '%s', but multiple Odoo Bank journals have that exact name/code: %s."
            ) % (
                label,
                self._find_value(payload, "number") or self._external_id(payload),
                bank_name,
                ", ".join(exact.mapped("display_name")),
            ))

        # Imported bank journals are commonly named 'BANK - Account Title'.
        # Only use this textual fallback when it produces exactly one journal.
        prefixes = (target + " -", target + " ", target + "(")
        prefixed = journals.filtered(
            lambda j: any(_norm(j.name).startswith(prefix) for prefix in prefixes)
        )
        if len(prefixed) == 1:
            return prefixed
        if len(prefixed) > 1:
            raise UserError(_(
                "Splendid %s %s uses bank '%s', but multiple Odoo Bank journals match that bank name: %s. "
                "Link the intended journal to the correct Odoo Bank Account."
            ) % (
                label,
                self._find_value(payload, "number") or self._external_id(payload),
                bank_name,
                ", ".join(prefixed.mapped("display_name")),
            ))

        bank = self.env["res.bank"].sudo().search([]).filtered(
            lambda b: _norm(b.name) == target
        )[:1]
        if bank:
            raise UserError(_(
                "Splendid %s %s uses bank '%s'. The Odoo Bank master exists, but no unique Bank journal is linked to it. "
                "Configure/link a Bank journal for '%s' and retry."
            ) % (
                label,
                self._find_value(payload, "number") or self._external_id(payload),
                bank_name,
                bank.display_name,
            ))
        raise UserError(_(
            "Splendid %s %s has no payment accountId/account code and reports bankName '%s', "
            "but no matching Odoo Bank journal was found."
        ) % (
            label,
            self._find_value(payload, "number") or self._external_id(payload),
            bank_name,
        ))

    def _get_or_create_customer_payment_journal(self, account_id, account, account_payload):
        """Reuse/create the exact Bank/Cash journal for a Splendid customer liquidity account."""
        self.ensure_one()
        Journal = self.env["account.journal"].with_company(self.company_id).sudo()
        account_id_text = str(account_id or "").strip()

        journal = Journal.search([
            ("company_id", "=", self.company_id.id),
            ("type", "in", ("bank", "cash")),
            ("default_account_id", "=", account.id),
        ], limit=1)
        if journal:
            if "splendid_payment_account_id" in Journal._fields and account_id_text and journal.splendid_payment_account_id != account_id_text:
                journal.write({"splendid_payment_account_id": account_id_text})
            return journal

        if account_id_text and "splendid_payment_account_id" in Journal._fields:
            journal = Journal.search([
                ("company_id", "=", self.company_id.id),
                ("type", "in", ("bank", "cash")),
                ("splendid_payment_account_id", "=", account_id_text),
            ], limit=1)
            if journal:
                if journal.default_account_id != account:
                    journal.write({"default_account_id": account.id})
                return journal

        if account_id_text:
            journal = Journal.search([
                ("company_id", "=", self.company_id.id),
                ("type", "in", ("bank", "cash")),
                ("splendid_bank_account_account_id", "=", account_id_text),
            ], limit=1)
            if journal:
                vals = {"default_account_id": account.id}
                if "splendid_payment_account_id" in Journal._fields:
                    vals["splendid_payment_account_id"] = account_id_text
                journal.write(vals)
                return journal

        if account.account_type != "asset_cash":
            raise UserError(_(
                "Splendid customer payment/refund account %s [%s] mapped to Odoo account '%s' "
                "with type '%s', not a Bank and Cash liquidity account. Journal mapping was not guessed."
            ) % (
                account_id_text or "?",
                self._find_value(account_payload, "code") or account.code or "",
                account.display_name,
                account.account_type,
            ))

        journal_type = self._payment_journal_type_from_account_payload(account, account_payload)
        account_name = self._find_value(account_payload, "name") or account.name or account.display_name
        account_code = self._find_value(account_payload, "code") or account.code or account_id_text
        vals = {
            "name": ("Splendid - %s" % account_name)[:100],
            "type": journal_type,
            "code": self._unique_journal_code(account_code or account_name),
            "company_id": self.company_id.id,
            "default_account_id": account.id,
            "splendid_is_imported": True,
        }
        if "splendid_payment_account_id" in Journal._fields:
            vals["splendid_payment_account_id"] = account_id_text
        return Journal.create(vals)

    def _resolve_customer_liquidity_journal(self, payload, detail_field, label):
        detail = self._customer_payment_account_detail(payload, detail_field, label)
        if not detail:
            return self._default_bank_journal()

        account_payload = self._nested(detail, "account")
        account_id = self._find_value(detail, "accountId") or self._find_value(account_payload, "id")
        account_code = self._find_value(account_payload, "code")
        if not account_id and not account_code:
            payment_mode = self._customer_payment_mode(payload, detail_field, label)
            if payment_mode == 20:
                # Splendid paymentMode 20 = cheque.  Do not choose between BAHL
                # operating journals by bankName; route the payment through one
                # dedicated Cheque clearing journal instead.
                return self._get_or_create_cheque_journal()

            bank_name = self._customer_payment_bank_name(payload, detail_field, label)
            if bank_name:
                return self._find_customer_payment_journal_by_bank_name(bank_name, payload, label)
            raise UserError(_(
                "Splendid %s %s has payment details but no accountId/account code and no bankName. Journal mapping was not guessed."
            ) % (label, self._find_value(payload, "number") or self._external_id(payload)))

        account = self._resolve_account(account_id, account_code)
        if not account:
            raise UserError(_(
                "Could not resolve Splendid %s account %s [%s] in Odoo."
            ) % (label, account_id or "?", account_code or ""))
        return self._get_or_create_customer_payment_journal(account_id, account, account_payload)

    def _resolve_journal_for_customer_payment(self, payload):
        # Latest rule: Splendid paymentMode 20 always represents a cheque payment.
        # Route it to the dedicated Cheque clearing journal before looking at
        # accountId/account code or bankName, so BAHL/other multiple bank journals
        # can never make cheque imports ambiguous.
        payment_mode = self._customer_payment_mode(
            payload, "customerPaymentDetails", "customer payment"
        )
        if payment_mode == 20:
            return self._get_or_create_cheque_journal()
        return self._resolve_customer_liquidity_journal(
            payload, "customerPaymentDetails", "customer payment"
        )

    def _prepare_customer_payment_accounts(self, journal, partner, payment_type):
        """Return a valid method line + customer receivable account for Odoo 18 payments."""
        self.ensure_one()
        if payment_type == "inbound":
            methods = journal.inbound_payment_method_line_ids
            direction = _("inbound")
        else:
            methods = journal.outbound_payment_method_line_ids
            direction = _("outbound")

        if not methods:
            raise UserError(_(
                "Bank/Cash journal '%s' has no %s payment method. Configure a Manual payment method before importing customer payments/refunds."
            ) % (journal.display_name, direction))

        method = methods.filtered(lambda m: m.payment_account_id and m.code == "manual")[:1]
        if not method:
            method = methods.filtered(lambda m: m.payment_account_id)[:1]
        if not method:
            method = methods.filtered(lambda m: m.code == "manual")[:1] or methods[:1]

        if not method.payment_account_id:
            fallback_payment_account = journal.default_account_id
            if not fallback_payment_account:
                raise UserError(_(
                    "Customer payment/refund journal '%s' has no Outstanding account and no Default Account."
                ) % journal.display_name)
            method.sudo().write({"payment_account_id": fallback_payment_account.id})

        receivable = partner.with_company(self.company_id).property_account_receivable_id
        if not receivable:
            receivable = self.default_receivable_account_id or self._default_account("receivable")
            if not receivable or receivable.account_type != "asset_receivable":
                raise UserError(_(
                    "Customer '%s' has no receivable account and no valid default receivable account is configured."
                ) % partner.display_name)
            partner.with_company(self.company_id).sudo().write({
                "property_account_receivable_id": receivable.id,
            })
        return method, receivable

    def _validate_customer_payment_accounts(self, payment):
        """Raise a readable error before Odoo reaches the SQL account_id=NULL constraint."""
        payment.invalidate_recordset()
        if not payment.payment_method_line_id:
            raise UserError(_("Customer payment/refund has no payment method line."))
        if not payment.outstanding_account_id:
            raise UserError(_(
                "Customer payment/refund method '%s' on journal '%s' has no Outstanding account."
            ) % (payment.payment_method_line_id.display_name, payment.journal_id.display_name))
        if not payment.destination_account_id:
            raise UserError(_(
                "Customer '%s' has no receivable account for company '%s'."
            ) % (payment.partner_id.display_name, payment.company_id.display_name))
        return True

    def _import_customer_payment_process(self, payload):
        external_id = self._external_id(payload)
        payment = self._mapped_record("customer_payment", external_id, "account.payment")

        partner = self._resolve_customer(payload)
        journal = self._resolve_journal_for_customer_payment(payload)
        method, receivable = self._prepare_customer_payment_accounts(journal, partner, "inbound")

        if payment:
            state = getattr(payment, "state", False)
            if payment.journal_id != journal and state != "draft":
                raise UserError(_(
                    "Existing Odoo customer payment %s is already posted in journal '%s', but Splendid now maps it to '%s'. "
                    "Reset/delete that payment before re-syncing; the integration will not silently move a posted payment between liquidity journals."
                ) % (payment.display_name, payment.journal_id.display_name, journal.display_name))
            vals = {}
            if payment.journal_id != journal and state == "draft":
                vals["journal_id"] = journal.id
            if payment.payment_method_line_id != method and state == "draft":
                vals["payment_method_line_id"] = method.id
            if payment.destination_account_id != receivable and state == "draft":
                vals["destination_account_id"] = receivable.id
            if vals:
                payment.sudo().write(vals)
            self._validate_customer_payment_accounts(payment)
            if self.auto_post_customer_payments and getattr(payment, "state", False) == "draft":
                payment.action_post()
            if self.auto_reconcile_customer_payments and not self.env.context.get("skip_splendid_customer_auto_reconcile"):
                self._reconcile_customer_payment(payment, payload)
            return payment

        amount = self._safe_float(
            self._find_value(payload, "totalAmount", "allocatedAmount", "amount"),
            0.0,
        )
        if amount <= 0:
            raise UserError(_("Customer payment %s has no positive amount to import.") % external_id)
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
            "payment_method_line_id": method.id,
            "destination_account_id": receivable.id,
            "splendid_customer_payment_id": external_id,
            "splendid_is_imported": True,
        }
        if "splendid_raw_payload" in self.env["account.payment"]._fields:
            vals["splendid_raw_payload"] = payload

        payment = self.env["account.payment"].with_company(self.company_id).sudo().create(vals)
        self._validate_customer_payment_accounts(payment)
        if self.auto_post_customer_payments and getattr(payment, "state", False) == "draft":
            payment.action_post()
        self._set_mapping("customer_payment", external_id, payment, payload, payment_ref)
        if self.auto_reconcile_customer_payments and not self.env.context.get("skip_splendid_customer_auto_reconcile"):
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

    def _fetch_customer_settlement_list(self):
        """Fetch CustomerSettlements using the connection date range.

        The list/search response is only used to discover settlement IDs. Every
        settlement is refreshed with GET /CustomerSettlements/{id} before Odoo
        reconciliation so accountSide/sourceId/adjustedAmount come from the
        authoritative detail payload.
        """
        self.ensure_one()
        date_payload = self._date_range_payload()
        if date_payload:
            return self._fetch_search_collection(
                "/CustomerSettlements/Search",
                filter_payload=date_payload,
            )
        return self._fetch_collection(
            "/CustomerSettlements",
            params={"orderBy": "Date", "ascending": "true"},
            use_paging=True,
        )

    def _normalize_customer_settlement_source(self, value):
        return re.sub(r"[^a-z0-9]", "", str(value or "").strip().lower())

    def _customer_settlement_ids_from_source_payload(self, payload):
        """Return unique CustomerSettlement IDs referenced by a source payload."""
        ids = []
        direct_id = self._find_value(payload, "customerSettlementId")
        if direct_id not in (False, None, ""):
            ids.append(direct_id)
        for item in self._find_value(payload, "customerSingleSettledEntryItems", default=[]) or []:
            if not isinstance(item, dict):
                continue
            settlement_id = self._find_value(item, "customerSettlementId")
            if settlement_id not in (False, None, "") and settlement_id not in ids:
                ids.append(settlement_id)
        return ids

    def _reconcile_customer_settlements_referenced_by_payload(self, payload, log_missing=False):
        """Reconcile only CustomerSettlements explicitly referenced by a payload."""
        self.ensure_one()
        settlement_ids = self._customer_settlement_ids_from_source_payload(payload)
        if not settlement_ids:
            if log_missing:
                self._log(
                    "sales_reconcile",
                    "skipped",
                    "No CustomerSettlement ID is referenced by this Splendid source payload; bulk Reconcile Customer Settlements can check the CustomerSettlements API later.",
                    payload,
                    self._external_id(payload),
                )
            return True

        has_review = False
        for settlement_id in settlement_ids:
            try:
                settlement_payload = self._fetch_detail_by_id("/CustomerSettlements", settlement_id)
                stats = self._reconcile_customer_settlement_payload(settlement_payload, log_result=True)
                has_review = has_review or bool(stats.get("review_count"))
            except Exception as exc:  # pylint: disable=broad-except
                has_review = True
                self._log(
                    "sales_reconcile",
                    "error",
                    "Could not reconcile CustomerSettlement %s referenced by source %s: %s"
                    % (settlement_id, self._external_id(payload), exc),
                    payload,
                    settlement_id,
                )
        return not has_review

    def _customer_document_status_is_void(self, payload):
        if not isinstance(payload, dict):
            return False
        if bool(self._find_value(payload, "isVoid", default=False)):
            return True
        status = self._find_value(payload, "status")
        if status in (False, None, ""):
            return False
        try:
            return int(float(str(status).strip())) == 50
        except (TypeError, ValueError):
            return str(status).strip() == "50"

    def _find_customer_payment_by_settlement_source(self, source_id=False, source_number=False):
        self.ensure_one()
        Payment = self.env["account.payment"].with_company(self.company_id).sudo()
        payment = Payment
        if source_id:
            payment = self._mapped_record("customer_payment", source_id, "account.payment")
            if not payment and "splendid_customer_payment_id" in Payment._fields:
                payment = Payment.search([
                    ("company_id", "=", self.company_id.id),
                    ("payment_type", "=", "inbound"),
                    ("partner_type", "=", "customer"),
                    ("splendid_customer_payment_id", "=", str(source_id)),
                ], limit=1)
        if not payment and source_number:
            payment = Payment.search([
                ("company_id", "=", self.company_id.id),
                ("payment_type", "=", "inbound"),
                ("partner_type", "=", "customer"),
                ("payment_reference", "=", source_number),
            ], limit=1)
        if payment and source_id:
            vals = {}
            if "splendid_customer_payment_id" in Payment._fields and not payment.splendid_customer_payment_id:
                vals["splendid_customer_payment_id"] = str(source_id)
            if vals:
                payment.write(vals)
            self._set_mapping(
                "customer_payment", source_id, payment,
                {"id": source_id, "number": source_number},
                source_number or source_id,
            )
        return payment

    def _find_customer_refund_by_settlement_source(self, source_id=False, source_number=False):
        self.ensure_one()
        Payment = self.env["account.payment"].with_company(self.company_id).sudo()
        payment = Payment
        if source_id:
            payment = self._mapped_record("customer_refund", source_id, "account.payment")
            if not payment and "splendid_customer_refund_id" in Payment._fields:
                payment = Payment.search([
                    ("company_id", "=", self.company_id.id),
                    ("payment_type", "=", "outbound"),
                    ("partner_type", "=", "customer"),
                    ("splendid_customer_refund_id", "=", str(source_id)),
                ], limit=1)
        if not payment and source_number:
            payment = Payment.search([
                ("company_id", "=", self.company_id.id),
                ("payment_type", "=", "outbound"),
                ("partner_type", "=", "customer"),
                ("payment_reference", "=", source_number),
            ], limit=1)
        if payment and source_id:
            self._set_mapping(
                "customer_refund", source_id, payment,
                {"id": source_id, "number": source_number},
                source_number or source_id,
            )
        return payment

    def _receivable_lines_for_move(self, move, open_only=True):
        if not move:
            return self.env["account.move.line"]
        lines = move.line_ids.filtered(
            lambda line: line.account_id.account_type == "asset_receivable"
        )
        if open_only:
            lines = lines.filtered(
                lambda line: not line.reconciled and abs(line.amount_residual) > 0.00001
            )
        return lines

    def _existing_customer_reconciled_amount_between_moves(self, move_a, move_b):
        """Company-currency amount already reconciled between two receivable moves."""
        if not move_a or not move_b:
            return 0.0
        lines_a = self._receivable_lines_for_move(move_a, open_only=False)
        lines_b = self._receivable_lines_for_move(move_b, open_only=False)
        if not lines_a or not lines_b:
            return 0.0
        partials = self.env["account.partial.reconcile"].sudo().search([
            "|",
            "&", ("debit_move_id", "in", lines_a.ids), ("credit_move_id", "in", lines_b.ids),
            "&", ("debit_move_id", "in", lines_b.ids), ("credit_move_id", "in", lines_a.ids),
        ])
        return sum(partials.mapped("amount"))

    def _prepare_customer_settlement_source_entry(self, detail):
        """Resolve one CustomerSettlement detail into a posted Odoo move."""
        self.ensure_one()
        source = self._normalize_customer_settlement_source(
            self._find_value(detail, "source")
        )
        source_id = self._find_value(detail, "sourceId")
        source_number = self._find_value(detail, "sourceNumber", "number")
        amount = self._safe_float(
            self._find_value(detail, "adjustedAmount", "amount"), 0.0
        )
        side_raw = self._find_value(detail, "accountSide")
        try:
            account_side = int(side_raw)
        except (TypeError, ValueError):
            account_side = -1
        result = {
            "source": source,
            "source_id": source_id,
            "source_number": source_number,
            "amount": amount,
            "account_side": account_side,
            "record": False,
            "move": False,
            "message": False,
        }
        if amount <= 0.0:
            result["message"] = "Settlement detail has no positive adjustedAmount."
            return result
        if account_side not in (0, 1):
            result["message"] = "Settlement detail has unsupported accountSide %s." % side_raw
            return result

        if source == "customerpayment":
            payment_payload = {}
            if source_id:
                try:
                    payment_payload = self._fetch_detail_by_id("/CustomerPayments", source_id)
                except Exception as exc:  # pylint: disable=broad-except
                    result["message"] = (
                        "Could not verify Splendid CustomerPayment %s/%s before reconciliation: %s"
                        % (source_number or "", source_id, exc)
                    )
                    return result
                if self._customer_document_status_is_void(payment_payload):
                    result["message"] = (
                        "CustomerPayment %s/%s is status=50 / void in Splendid and was not reconciled."
                        % (source_number or "", source_id)
                    )
                    return result
            payment = self._find_customer_payment_by_settlement_source(source_id, source_number)
            if not payment:
                if not source_id:
                    result["message"] = (
                        "CustomerPayment %s has no Splendid sourceId, so it cannot be fetched automatically."
                        % (source_number or "")
                    )
                    return result
                if not payment_payload:
                    try:
                        payment_payload = self._fetch_detail_by_id("/CustomerPayments", source_id)
                    except Exception as exc:  # pylint: disable=broad-except
                        result["message"] = (
                            "CustomerPayment %s/%s was not found in Odoo and could not be fetched from Splendid: %s"
                            % (source_number or "", source_id, exc)
                        )
                        return result
                if self._customer_document_status_is_void(payment_payload):
                    result["message"] = (
                        "CustomerPayment %s/%s is status=50 / void in Splendid and was not created or reconciled."
                        % (source_number or "", source_id)
                    )
                    return result
                try:
                    payment = self.with_context(
                        skip_splendid_customer_auto_reconcile=True
                    )._import_customer_payment_process(payment_payload)
                except Exception as exc:  # pylint: disable=broad-except
                    result["message"] = (
                        "CustomerPayment %s/%s was missing in Odoo and automatic creation failed: %s"
                        % (source_number or "", source_id, exc)
                    )
                    return result
            desired_journal = (
                self._resolve_journal_for_customer_payment(payment_payload)
                if payment_payload else payment.journal_id
            )
            state = getattr(payment, "state", False)
            if payment.journal_id != desired_journal and state != "draft":
                result["message"] = (
                    "CustomerPayment %s is posted in Odoo journal '%s', but Splendid payment account maps to '%s'. "
                    "Reset/delete and re-sync this payment before reconciliation."
                    % (source_number or source_id, payment.journal_id.display_name, desired_journal.display_name)
                )
                return result
            if payment.journal_id != desired_journal and state == "draft":
                payment.write({"journal_id": desired_journal.id})
            if getattr(payment, "state", False) == "draft":
                method, receivable = self._prepare_customer_payment_accounts(desired_journal, payment.partner_id, "inbound")
                vals = {}
                if payment.payment_method_line_id != method:
                    vals["payment_method_line_id"] = method.id
                if payment.destination_account_id != receivable:
                    vals["destination_account_id"] = receivable.id
                if vals:
                    payment.write(vals)
                self._validate_customer_payment_accounts(payment)
                payment.action_post()
            if not payment.move_id or payment.move_id.state != "posted":
                result["message"] = "CustomerPayment %s is not posted in Odoo." % (source_number or source_id)
                return result
            result.update({"record": payment, "move": payment.move_id})
            return result

        if source == "saleinvoice":
            invoice = self._find_sale_invoice_for_payment_settlement(source_id, source_number)
            if not invoice:
                if not source_id:
                    result["message"] = (
                        "SaleInvoice %s has no Splendid sourceId, so it cannot be fetched automatically."
                        % (source_number or "")
                    )
                    return result
                try:
                    invoice_payload = self._fetch_detail_by_id("/SaleInvoices", source_id)
                    invoice = self.with_context(
                        skip_splendid_customer_auto_reconcile=True
                    )._import_sale_invoice_process(invoice_payload)
                except Exception as exc:  # pylint: disable=broad-except
                    result["message"] = (
                        "SaleInvoice %s/%s was missing in Odoo and automatic creation failed: %s"
                        % (source_number or "", source_id, exc)
                    )
                    return result
            if invoice.state == "draft":
                invoice.action_post()
            if invoice.state != "posted":
                result["message"] = "SaleInvoice %s is not posted in Odoo." % (source_number or source_id)
                return result
            result.update({"record": invoice, "move": invoice})
            return result

        if source == "customerrefund":
            refund_payload = {}
            if source_id:
                try:
                    refund_payload = self._fetch_detail_by_id("/CustomerRefunds", source_id)
                except Exception as exc:  # pylint: disable=broad-except
                    result["message"] = (
                        "Could not verify Splendid CustomerRefund %s/%s before reconciliation: %s"
                        % (source_number or "", source_id, exc)
                    )
                    return result
                if self._customer_document_status_is_void(refund_payload):
                    result["message"] = (
                        "CustomerRefund %s/%s is status=50 / void in Splendid and was not reconciled."
                        % (source_number or "", source_id)
                    )
                    return result
            refund = self._find_customer_refund_by_settlement_source(source_id, source_number)
            if not refund:
                if not source_id:
                    result["message"] = (
                        "CustomerRefund %s has no Splendid sourceId, so it cannot be fetched automatically."
                        % (source_number or "")
                    )
                    return result
                if not refund_payload:
                    try:
                        refund_payload = self._fetch_detail_by_id("/CustomerRefunds", source_id)
                    except Exception as exc:  # pylint: disable=broad-except
                        result["message"] = (
                            "CustomerRefund %s/%s was not found in Odoo and could not be fetched from Splendid: %s"
                            % (source_number or "", source_id, exc)
                        )
                        return result
                if self._customer_document_status_is_void(refund_payload):
                    result["message"] = (
                        "CustomerRefund %s/%s is status=50 / void in Splendid and was not created or reconciled."
                        % (source_number or "", source_id)
                    )
                    return result
                try:
                    refund = self.with_context(
                        skip_splendid_customer_auto_reconcile=True
                    )._import_customer_refund_process(refund_payload)
                except Exception as exc:  # pylint: disable=broad-except
                    result["message"] = (
                        "CustomerRefund %s/%s was missing in Odoo and automatic creation failed: %s"
                        % (source_number or "", source_id, exc)
                    )
                    return result
            desired_journal = (
                self._resolve_journal_for_customer_refund(refund_payload)
                if refund_payload else refund.journal_id
            )
            state = getattr(refund, "state", False)
            if refund.journal_id != desired_journal and state != "draft":
                result["message"] = (
                    "CustomerRefund %s is posted in Odoo journal '%s', but Splendid refund account maps to '%s'. "
                    "Reset/delete and re-sync this refund before reconciliation."
                    % (source_number or source_id, refund.journal_id.display_name, desired_journal.display_name)
                )
                return result
            if refund.journal_id != desired_journal and state == "draft":
                refund.write({"journal_id": desired_journal.id})
            if getattr(refund, "state", False) == "draft":
                method, receivable = self._prepare_customer_payment_accounts(desired_journal, refund.partner_id, "outbound")
                vals = {}
                if refund.payment_method_line_id != method:
                    vals["payment_method_line_id"] = method.id
                if refund.destination_account_id != receivable:
                    vals["destination_account_id"] = receivable.id
                if vals:
                    refund.write(vals)
                self._validate_customer_payment_accounts(refund)
                refund.action_post()
            if not refund.move_id or refund.move_id.state != "posted":
                result["message"] = "CustomerRefund %s is not posted in Odoo." % (source_number or source_id)
                return result
            result.update({"record": refund, "move": refund.move_id})
            return result

        if source in ("salereturn", "creditnote", "customercreditnote"):
            credit_note = self._find_sale_return_for_refund_settlement(source_id, source_number)
            if not credit_note:
                if not source_id:
                    result["message"] = (
                        "SaleReturn/CreditNote %s has no Splendid sourceId, so it cannot be fetched automatically."
                        % (source_number or "")
                    )
                    return result
                try:
                    return_payload = self._fetch_detail_by_id("/SaleReturns", source_id)
                    credit_note = self.with_context(
                        skip_splendid_customer_auto_reconcile=True
                    )._import_sale_return_process(return_payload)
                except Exception as exc:  # pylint: disable=broad-except
                    result["message"] = (
                        "SaleReturn/CreditNote %s/%s was missing in Odoo and automatic creation failed: %s"
                        % (source_number or "", source_id, exc)
                    )
                    return result
            if credit_note.state == "draft":
                credit_note.action_post()
            if credit_note.state != "posted":
                result["message"] = "SaleReturn/CreditNote %s is not posted in Odoo." % (source_number or source_id)
                return result
            result.update({"record": credit_note, "move": credit_note})
            return result

        result["message"] = "Unsupported Splendid CustomerSettlement source '%s'." % (
            self._find_value(detail, "source") or ""
        )
        return result

    def _apply_exact_receivable_settlement(self, move_a, move_b, requested_amount):
        """Reconcile exactly one Splendid amount between two receivable moves.

        Debit/credit direction is taken from Odoo residual signs. No payment,
        write-off, extra journal entry, or destructive unreconcile is created.
        """
        self.ensure_one()
        requested = self._safe_float(requested_amount, 0.0)
        result = {
            "requested": requested,
            "already": 0.0,
            "new": 0.0,
            "remaining": requested,
            "message": False,
        }
        if requested <= 0.0:
            return result
        if not move_a or not move_b:
            result["message"] = "One side of the settlement is missing in Odoo."
            return result
        company_currency = self.company_id.currency_id
        if move_a.currency_id != company_currency or move_b.currency_id != company_currency:
            result["message"] = "Foreign-currency CustomerSettlement was not auto-reconciled."
            return result

        already_actual = self._existing_customer_reconciled_amount_between_moves(move_a, move_b)
        result["already"] = min(already_actual, requested)
        if already_actual > requested + 0.00001:
            result["remaining"] = 0.0
            result["message"] = (
                "Odoo already has %.2f reconciled between these documents, more than Splendid %.2f."
                % (already_actual, requested)
            )
            return result
        remaining = max(requested - already_actual, 0.0)
        result["remaining"] = remaining
        if remaining <= 0.00001:
            result["remaining"] = 0.0
            return result

        lines_a = self._receivable_lines_for_move(move_a)
        lines_b = self._receivable_lines_for_move(move_b)
        if not lines_a or not lines_b:
            result["message"] = "No open receivable lines are available on one or both documents."
            return result

        Partial = self.env["account.partial.reconcile"].sudo()
        for line_a in lines_a:
            for line_b in lines_b:
                if remaining <= 0.00001:
                    break
                if line_a.account_id != line_b.account_id:
                    continue
                if (
                    line_a.partner_id and line_b.partner_id
                    and line_a.partner_id.commercial_partner_id != line_b.partner_id.commercial_partner_id
                ):
                    continue
                line_a.invalidate_recordset()
                line_b.invalidate_recordset()
                residual_a = line_a.amount_residual
                residual_b = line_b.amount_residual
                if residual_a > 0.00001 and residual_b < -0.00001:
                    debit_line, credit_line = line_a, line_b
                elif residual_b > 0.00001 and residual_a < -0.00001:
                    debit_line, credit_line = line_b, line_a
                else:
                    continue
                available = min(
                    remaining,
                    max(debit_line.amount_residual, 0.0),
                    abs(min(credit_line.amount_residual, 0.0)),
                )
                if available <= 0.00001:
                    continue
                vals = {
                    "debit_move_id": debit_line.id,
                    "credit_move_id": credit_line.id,
                    "amount": available,
                }
                if debit_line.currency_id == company_currency:
                    vals["debit_amount_currency"] = available
                if credit_line.currency_id == company_currency:
                    vals["credit_amount_currency"] = available
                Partial.create(vals)
                remaining -= available
                result["new"] += available
            if remaining <= 0.00001:
                break

        result["remaining"] = max(remaining, 0.0)
        if result["remaining"] > 0.00001:
            result["message"] = (
                "Requested %.2f; already matched %.2f; newly matched %.2f; remaining %.2f. "
                "Check Odoo residuals, receivable accounts, partner, or previous reconciliations."
                % (requested, result["already"], result["new"], result["remaining"])
            )
        return result

    def _reconcile_customer_settlement_payload(self, payload, log_result=True):
        """Mirror one GET /CustomerSettlements/{id} payload exactly in Odoo."""
        self.ensure_one()
        stats = {
            "allocation_count": 0,
            "already_reconciled": 0.0,
            "newly_reconciled": 0.0,
            "review_count": 0,
        }
        settlement_id = self._external_id(payload)
        settlement_number = self._find_value(payload, "number") or settlement_id
        status = self._find_value(payload, "status")
        try:
            status_int = int(float(str(status))) if status not in (False, None, "") else None
        except (TypeError, ValueError):
            status_int = None
        if status_int == 50:
            if log_result:
                self._log(
                    "sales_reconcile",
                    "skipped",
                    "CustomerSettlement %s skipped because Splendid status=50." % settlement_number,
                    payload,
                    settlement_id,
                )
            return stats

        details = self._find_value(payload, "customerSettlementDetails", default=[]) or []
        if not details:
            if log_result:
                self._log(
                    "sales_reconcile",
                    "skipped",
                    "CustomerSettlement %s has no customerSettlementDetails." % settlement_number,
                    payload,
                    settlement_id,
                )
            return stats

        side_entries = {0: [], 1: []}
        review_messages = []
        for detail in details:
            if not isinstance(detail, dict):
                continue
            entry = self._prepare_customer_settlement_source_entry(detail)
            if entry["message"]:
                stats["review_count"] += 1
                review_messages.append(entry["message"])
                continue
            side_entries[entry["account_side"]].append(entry)

        side0_total = sum(item["amount"] for item in side_entries[0])
        side1_total = sum(item["amount"] for item in side_entries[1])
        if not side_entries[0] or not side_entries[1]:
            stats["review_count"] += 1
            review_messages.append(
                "CustomerSettlement does not have valid entries on both accountSide 0 and 1."
            )
        elif abs(side0_total - side1_total) > 0.01:
            stats["review_count"] += 1
            review_messages.append(
                "Splendid customer settlement sides do not balance: side0 %.2f vs side1 %.2f."
                % (side0_total, side1_total)
            )

        right_index = 0
        right_remaining = side_entries[1][0]["amount"] if side_entries[1] else 0.0
        for left in side_entries[0]:
            left_remaining = left["amount"]
            while left_remaining > 0.00001 and right_index < len(side_entries[1]):
                right = side_entries[1][right_index]
                pair_amount = min(left_remaining, right_remaining)
                if pair_amount <= 0.00001:
                    right_index += 1
                    if right_index < len(side_entries[1]):
                        right_remaining = side_entries[1][right_index]["amount"]
                    continue
                stats["allocation_count"] += 1
                result = self._apply_exact_receivable_settlement(
                    left["move"], right["move"], pair_amount
                )
                stats["already_reconciled"] += result["already"]
                stats["newly_reconciled"] += result["new"]
                if result["message"]:
                    stats["review_count"] += 1
                    review_messages.append(
                        "%s %s ↔ %s %s (%.2f): %s"
                        % (
                            left["source"], left["source_number"] or left["source_id"],
                            right["source"], right["source_number"] or right["source_id"],
                            pair_amount, result["message"],
                        )
                    )
                left_remaining -= pair_amount
                right_remaining -= pair_amount
                if right_remaining <= 0.00001:
                    right_index += 1
                    if right_index < len(side_entries[1]):
                        right_remaining = side_entries[1][right_index]["amount"]

        if log_result:
            state = "error" if review_messages else "success"
            message = (
                "CustomerSettlement %s checked from Splendid API: allocations=%s, "
                "newly reconciled=%.2f, already matched=%.2f."
                % (
                    settlement_number,
                    stats["allocation_count"],
                    stats["newly_reconciled"],
                    stats["already_reconciled"],
                )
            )
            if review_messages:
                message += " Review: " + " | ".join(review_messages)
            self._log(
                "sales_reconcile",
                state,
                message,
                payload,
                settlement_id,
            )
        return stats

    def _reconcile_all_customer_settlements_from_splendid(self):
        """Button backend: CustomerSettlements is the customer allocation source of truth."""
        self.ensure_one()
        summary = {
            "allocation_count": 0,
            "already_reconciled": 0.0,
            "newly_reconciled": 0.0,
            "review_count": 0,
        }
        settlement_rows = self._fetch_customer_settlement_list()
        if not settlement_rows:
            self._log(
                "sales_reconcile",
                "skipped",
                "Splendid returned 0 CustomerSettlements for the current sync range. From Date=%s; To Date=%s."
                % (self.sync_from_date or "blank", self.sync_to_date or "blank"),
                {"from_date": self.sync_from_date, "to_date": self.sync_to_date},
            )
            return summary

        for row in settlement_rows:
            settlement_id = self._external_id(row)
            if not settlement_id:
                summary["review_count"] += 1
                self._log(
                    "sales_reconcile", "error",
                    "CustomerSettlement list row has no Splendid ID.",
                    row,
                )
                continue
            try:
                with self.env.cr.savepoint():
                    payload = self._fetch_detail_by_id("/CustomerSettlements", settlement_id)
                    result = self._reconcile_customer_settlement_payload(payload, log_result=True)
                    for key in summary:
                        summary[key] += result.get(key, 0)
            except Exception as exc:  # pylint: disable=broad-except
                summary["review_count"] += 1
                _logger.exception(
                    "Failed Splendid CustomerSettlement reconciliation for %s", settlement_id
                )
                self._log(
                    "sales_reconcile", "error",
                    "CustomerSettlement %s failed: %s" % (settlement_id, exc),
                    row, settlement_id,
                )

        self._log(
            "sales_reconcile",
            "error" if summary["review_count"] else "success",
            (
                "Splendid CustomerSettlements reconciliation summary: settlements fetched=%s, "
                "allocations=%s, newly reconciled=%.2f, already matched=%.2f, review=%s."
                % (
                    len(settlement_rows),
                    summary["allocation_count"],
                    summary["newly_reconciled"],
                    summary["already_reconciled"],
                    summary["review_count"],
                )
            ),
            {"customer_settlements_fetched": len(settlement_rows), **summary},
        )
        self.env.cr.commit()
        return summary

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
        """Reconcile only through authoritative Splendid CustomerSettlements.

        Older module versions tried to assign the payment's open line directly to
        every SaleInvoice referenced in customerPaymentSettlementDetails. That is
        not idempotent and loses the exact adjustedAmount allocation. The source
        payload is now used only to discover customerSettlementId values; the
        actual pairing comes from GET /CustomerSettlements/{id}.
        """
        if not payment:
            return False
        return self._reconcile_customer_settlements_referenced_by_payload(
            payload,
            log_missing=False,
        )

    def _reconcile_moves(self, moves):
        if not moves:
            return False

        lines = moves.mapped("line_ids").filtered(
            lambda l:
                not l.reconciled
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



    def _resolve_journal_for_customer_refund(self, payload):
        return self._resolve_customer_liquidity_journal(payload, "customerRefundDetails", "customer refund")

    def _import_customer_refund_process(self, payload):
        external_id = self._external_id(payload)
        payment = self._mapped_record("customer_refund", external_id, "account.payment")

        partner = self._resolve_customer(payload)
        journal = self._resolve_journal_for_customer_refund(payload)
        method, receivable = self._prepare_customer_payment_accounts(journal, partner, "outbound")

        if payment:
            state = getattr(payment, "state", False)
            if payment.journal_id != journal and state != "draft":
                raise UserError(_(
                    "Existing Odoo customer refund %s is already posted in journal '%s', but Splendid now maps it to '%s'. "
                    "Reset/delete that refund payment before re-syncing; the integration will not silently move a posted payment between liquidity journals."
                ) % (payment.display_name, payment.journal_id.display_name, journal.display_name))
            vals = {}
            if payment.journal_id != journal and state == "draft":
                vals["journal_id"] = journal.id
            if payment.payment_method_line_id != method and state == "draft":
                vals["payment_method_line_id"] = method.id
            if payment.destination_account_id != receivable and state == "draft":
                vals["destination_account_id"] = receivable.id
            if vals:
                payment.sudo().write(vals)
            self._validate_customer_payment_accounts(payment)
            if self.auto_post_customer_refunds and getattr(payment, "state", False) == "draft":
                payment.action_post()
            if self.auto_reconcile_customer_refunds and not self.env.context.get("skip_splendid_customer_auto_reconcile"):
                self._reconcile_customer_refund(payment, payload)
            return payment

        amount = self._safe_float(self._find_value(payload, "totalAmount", "allocatedAmount", "amount"), 0.0)
        if amount <= 0:
            raise UserError(_("Customer refund %s has no positive amount to import.") % external_id)
        payment_ref = self._find_value(payload, "number", "reference", "comments") or external_id
        vals = {
            "payment_type": "outbound",
            "partner_type": "customer",
            "partner_id": partner.id,
            "amount": amount,
            "date": self._parse_date(self._find_value(payload, "date")),
            "journal_id": journal.id,
            "company_id": self.company_id.id,
            "payment_reference": payment_ref,
            "payment_method_line_id": method.id,
            "destination_account_id": receivable.id,
            "splendid_customer_refund_id": external_id,
            "splendid_is_imported": True,
        }
        if "splendid_raw_payload" in self.env["account.payment"]._fields:
            vals["splendid_raw_payload"] = payload

        payment = self.env["account.payment"].with_company(self.company_id).sudo().create(vals)
        self._validate_customer_payment_accounts(payment)
        if self.auto_post_customer_refunds and getattr(payment, "state", False) == "draft":
            payment.action_post()
        self._set_mapping("customer_refund", external_id, payment, payload, payment_ref)
        if self.auto_reconcile_customer_refunds and not self.env.context.get("skip_splendid_customer_auto_reconcile"):
            self._reconcile_customer_refund(payment, payload)
        return payment

    def _find_sale_return_for_refund_settlement(self, source_id=False, source_number=False):
        Move = self.env["account.move"].with_company(self.company_id).sudo()

        if source_id:
            move = self._mapped_record("sale_return", source_id, "account.move")
            if move:
                return move
            if "splendid_sale_return_id" in Move._fields:
                move = Move.search([
                    ("company_id", "=", self.company_id.id),
                    ("move_type", "=", "out_refund"),
                    ("splendid_sale_return_id", "=", str(source_id)),
                ], limit=1)
                if move:
                    return move

        if source_number:
            move = Move.search([
                ("company_id", "=", self.company_id.id),
                ("move_type", "=", "out_refund"),
                "|",
                ("ref", "=", source_number),
                ("name", "=", source_number),
            ], limit=1)
            if move:
                return move

        return Move

    def _ensure_sale_return_for_refund_settlement(self, source_id=False, source_number=False):
        credit_note = self._find_sale_return_for_refund_settlement(source_id=source_id, source_number=source_number)
        if credit_note:
            return credit_note
        if source_id:
            try:
                payload = self._fetch_detail_by_id("/SaleReturns", source_id)
                if payload and self._sale_return_details(payload):
                    return self._import_sale_return_process(payload)
            except Exception as exc:  # pylint: disable=broad-except
                self._log(
                    "customer_refunds",
                    "error",
                    "Could not auto-import sale return %s for customer refund settlement: %s" % (source_id, exc),
                    {"source_id": source_id, "source_number": source_number},
                    source_id,
                )
        return self.env["account.move"].with_company(self.company_id).sudo()

    def _reconcile_customer_refund(self, payment, payload):
        if not payment:
            return False

        if getattr(payment, "state", False) == "draft":
            payment.action_post()
        if not payment.move_id:
            return False

        settlement_lines = []
        settlement_lines += self._find_value(payload, "customerRefundSettlementDetails", default=[]) or []
        settlement_lines += self._find_value(payload, "customerSingleSettledEntryItems", default=[]) or []

        credit_notes = self.env["account.move"].with_company(self.company_id).sudo()
        for item in settlement_lines:
            if not isinstance(item, dict):
                continue
            if str(self._find_value(item, "source", default="")).lower() != "salereturn":
                continue
            source_id = self._find_value(item, "sourceId")
            source_number = self._find_value(item, "sourceNumber", "number")
            credit_note = self._ensure_sale_return_for_refund_settlement(source_id=source_id, source_number=source_number)
            if credit_note:
                credit_notes |= credit_note

        if not credit_notes:
            self._log(
                "customer_refunds",
                "error",
                "Customer refund imported but matching sale return credit note was not found.",
                payload,
                self._external_id(payload),
                payment,
            )
            return False

        for credit_note in credit_notes:
            if credit_note.state == "draft":
                credit_note.action_post()

        payment_lines_all = payment.move_id.line_ids.filtered(
            lambda line:
                not line.reconciled
                and abs(line.amount_residual) > 0.00001
                and line.account_id.account_type == "asset_receivable"
        )

        if not payment_lines_all:
            self._log(
                "customer_refunds",
                "error",
                "Customer refund posted but no receivable line found on payment move.",
                payload,
                self._external_id(payload),
                payment,
            )
            return False

        for credit_note in credit_notes:
            if credit_note.payment_state == "paid":
                continue
            credit_lines = credit_note.line_ids.filtered(
                lambda line:
                    not line.reconciled
                    and abs(line.amount_residual) > 0.00001
                    and line.account_id.account_type == "asset_receivable"
            )
            if not credit_lines:
                continue
            for account in credit_lines.mapped("account_id"):
                credit_account_lines = credit_lines.filtered(lambda l, acc=account: l.account_id == acc)
                payment_account_lines = payment_lines_all.filtered(lambda l, acc=account: l.account_id == acc)
                if not payment_account_lines:
                    continue
                partner_credit_lines = credit_account_lines.filtered(
                    lambda l: not l.partner_id or not payment.partner_id or l.partner_id.commercial_partner_id == payment.partner_id.commercial_partner_id
                )
                partner_payment_lines = payment_account_lines.filtered(
                    lambda l: not l.partner_id or not payment.partner_id or l.partner_id.commercial_partner_id == payment.partner_id.commercial_partner_id
                )
                lines_to_reconcile = (partner_credit_lines | partner_payment_lines) if partner_credit_lines and partner_payment_lines else (credit_account_lines | payment_account_lines)
                try:
                    lines_to_reconcile.reconcile()
                except Exception as exc:  # pylint: disable=broad-except
                    _logger.warning(
                        "Could not reconcile Splendid customer refund %s with credit note %s on account %s: %s",
                        payment.display_name,
                        credit_note.display_name,
                        account.display_name,
                        exc,
                    )

        unpaid_notes = credit_notes.filtered(lambda move: move.payment_state != "paid")
        if unpaid_notes:
            self._log(
                "customer_refunds",
                "error",
                "Customer refund imported but sale return credit note is still not fully paid. Check amount, partner, receivable account, currency, or partial settlement.",
                payload,
                self._external_id(payload),
                payment,
            )
        return True

    # -------------------------------------------------------------------------
    # Purchase process sync: Splendid purchase invoices -> Vendor Bills,
    # Receipts, Purchase Returns, Vendor Credit Notes and Vendor Payments.
    # -------------------------------------------------------------------------

    purchase_journal_id = fields.Many2one("account.journal", domain="[('type','=','purchase'), ('company_id','=',company_id)]")
    auto_post_purchase_bills = fields.Boolean(string="Post Vendor Bills / Debit Notes", default=True)
    auto_create_purchase_receipts = fields.Boolean(string="Create Purchase Receipts", default=True)
    auto_validate_purchase_receipts = fields.Boolean(string="Validate Purchase Receipts", default=False)
    auto_create_purchase_return_transfers = fields.Boolean(string="Create Purchase Return Transfers", default=True)
    auto_validate_purchase_return_transfers = fields.Boolean(string="Validate Purchase Return Transfers", default=False)
    auto_post_vendor_payments = fields.Boolean(string="Post Vendor Payments", default=True)
    auto_reconcile_vendor_payments = fields.Boolean(string="Reconcile Vendor Payments", default=True)

    last_purchase_process_sync = fields.Datetime(copy=False, string="Last Purchase Process Sync")
    last_purchase_invoices_sync = fields.Datetime(copy=False, string="Last Purchase Invoices Sync")
    last_purchase_returns_sync = fields.Datetime(copy=False, string="Last Purchase Returns Sync")
    last_vendor_payments_sync = fields.Datetime(copy=False, string="Last Vendor Payments Sync")

    purchase_invoices_fetched_count = fields.Integer(copy=False, readonly=True)
    purchase_invoices_imported_count = fields.Integer(copy=False, readonly=True)
    purchase_invoices_failed_count = fields.Integer(copy=False, readonly=True)
    purchase_returns_fetched_count = fields.Integer(copy=False, readonly=True)
    purchase_returns_imported_count = fields.Integer(copy=False, readonly=True)
    purchase_returns_failed_count = fields.Integer(copy=False, readonly=True)
    vendor_payments_fetched_count = fields.Integer(copy=False, readonly=True)
    vendor_payments_imported_count = fields.Integer(copy=False, readonly=True)
    vendor_payments_failed_count = fields.Integer(copy=False, readonly=True)

    def action_sync_purchase_process(self):
        for rec in self:
            rec = rec._with_target_company()
            rec._sync_purchase_process()
        return True

    def action_sync_purchase_invoices(self):
        for rec in self:
            rec = rec._with_target_company()
            rec._sync_purchase_invoices()
        return True

    def action_sync_purchase_returns(self):
        for rec in self:
            rec = rec._with_target_company()
            rec._sync_purchase_returns()
        return True

    def action_sync_vendor_payments(self):
        for rec in self:
            rec = rec._with_target_company()
            rec._sync_vendor_payments()
        return True

    def action_reconcile_purchase_settlements(self):
        """Reconcile existing Odoo purchase documents from Splendid allocations.

        This is intentionally a reconciliation-only action. It does not create
        write-offs and it does not create missing vendor payments or purchase
        returns. Draft Splendid vendor bills/refunds referenced by a settlement
        are posted before the exact allocation is applied.
        """
        summaries = []
        for rec in self:
            rec = rec._with_target_company()
            summaries.append(rec._reconcile_all_purchase_settlements_from_splendid())

        total_new = sum(item.get("newly_reconciled", 0.0) for item in summaries)
        total_existing = sum(item.get("already_reconciled", 0.0) for item in summaries)
        total_review = sum(item.get("review_count", 0) for item in summaries)
        total_allocations = sum(item.get("allocation_count", 0) for item in summaries)

        message = _(
            "Splendid VendorSettlements reconciliation complete. Allocations checked: %(allocations)s; "
            "newly reconciled: %(new).2f; already matched: %(existing).2f; review items: %(review)s."
        ) % {
            "allocations": total_allocations,
            "new": total_new,
            "existing": total_existing,
            "review": total_review,
        }
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Splendid Reconciliation"),
                "message": message,
                "type": "warning" if total_review else "success",
                "sticky": bool(total_review),
            },
        }

    def _vendor_payment_settlement_lines(self, payload):
        """Return one canonical vendor-payment settlement list.

        Splendid can expose the same allocation in both
        vendorPaymentSettlementDetails and vendorSingleSettledEntryItems. Prefer
        the dedicated settlement list so the same amount is never applied twice.
        """
        primary = self._find_value(payload, "vendorPaymentSettlementDetails", default=[]) or []
        if primary:
            return primary
        return self._find_value(payload, "vendorSingleSettledEntryItems", default=[]) or []

    def _purchase_invoice_settlement_allocations(self, settlement_lines):
        """Aggregate Splendid PurchaseInvoice settlement rows by source invoice."""
        allocations = {}
        for item in settlement_lines or []:
            if not isinstance(item, dict):
                continue
            if str(self._find_value(item, "source", default="")).strip().lower() != "purchaseinvoice":
                continue
            source_id = self._find_value(item, "sourceId")
            source_number = self._find_value(item, "sourceNumber", "number")
            amount = self._safe_float(
                self._find_value(item, "adjustedAmount", "amount"),
                0.0,
            )
            if amount <= 0.0:
                continue
            key = (str(source_id or ""), str(source_number or ""))
            if key not in allocations:
                allocations[key] = {
                    "source_id": source_id,
                    "source_number": source_number,
                    "amount": 0.0,
                }
            allocations[key]["amount"] += amount
        return list(allocations.values())

    def _find_vendor_payment_for_settlement(self, external_id, payload=None):
        self.ensure_one()
        Payment = self.env["account.payment"].with_company(self.company_id).sudo()
        payment = self._mapped_record("vendor_payment", external_id, "account.payment")
        if not payment and external_id and "splendid_vendor_payment_id" in Payment._fields:
            payment = Payment.search([
                ("company_id", "=", self.company_id.id),
                ("splendid_vendor_payment_id", "=", str(external_id)),
            ], limit=1)
        if payment and payload:
            self._set_mapping(
                "vendor_payment",
                external_id,
                payment,
                payload,
                self._find_value(payload, "number", "reference") or external_id,
            )
        return payment

    def _find_purchase_return_for_settlement(self, external_id, payload=None):
        self.ensure_one()
        Move = self.env["account.move"].with_company(self.company_id).sudo()
        refund = self._mapped_record("purchase_return", external_id, "account.move")
        if not refund and external_id and "splendid_purchase_return_id" in Move._fields:
            refund = Move.search([
                ("company_id", "=", self.company_id.id),
                ("move_type", "=", "in_refund"),
                ("splendid_purchase_return_id", "=", str(external_id)),
            ], limit=1)
        if not refund and payload:
            source_number = self._find_value(payload, "number", "reference")
            if source_number:
                refund = Move.search([
                    ("company_id", "=", self.company_id.id),
                    ("move_type", "=", "in_refund"),
                    ("ref", "=", source_number),
                ], limit=1)
        if refund and payload:
            self._set_mapping(
                "purchase_return",
                external_id,
                refund,
                payload,
                self._find_value(payload, "number", "reference") or external_id,
            )
        return refund

    def _payable_lines_for_move(self, move, open_only=True):
        if not move:
            return self.env["account.move.line"]
        lines = move.line_ids.filtered(
            lambda line: line.account_id.account_type == "liability_payable"
        )
        if open_only:
            lines = lines.filtered(
                lambda line: not line.reconciled and abs(line.amount_residual) > 0.00001
            )
        return lines

    def _existing_reconciled_amount_between_moves(self, source_move, target_move):
        """Company-currency amount already reconciled between two moves."""
        if not source_move or not target_move:
            return 0.0
        source_lines = self._payable_lines_for_move(source_move, open_only=False)
        target_lines = self._payable_lines_for_move(target_move, open_only=False)
        if not source_lines or not target_lines:
            return 0.0
        partials = self.env["account.partial.reconcile"].sudo().search([
            "|",
            "&", ("debit_move_id", "in", source_lines.ids), ("credit_move_id", "in", target_lines.ids),
            "&", ("debit_move_id", "in", target_lines.ids), ("credit_move_id", "in", source_lines.ids),
        ])
        return sum(partials.mapped("amount"))

    def _apply_exact_purchase_settlement(self, source_move, bill, requested_amount):
        """Apply one exact Splendid allocation without payment/write-off creation.

        source_move is either an outbound vendor-payment journal entry or a vendor
        refund. Both normally carry a positive/debit payable residual; the vendor
        bill carries the negative/credit payable residual.
        """
        self.ensure_one()
        requested = self._safe_float(requested_amount, 0.0)
        result = {
            "requested": requested,
            "already": 0.0,
            "new": 0.0,
            "remaining": requested,
            "message": False,
        }
        if requested <= 0.0:
            return result
        if not source_move or not bill:
            result["message"] = "Source move or purchase invoice is missing."
            return result

        company_currency = self.company_id.currency_id
        if source_move.currency_id != company_currency or bill.currency_id != company_currency:
            result["message"] = "Foreign-currency settlement was not auto-reconciled."
            return result

        already = self._existing_reconciled_amount_between_moves(source_move, bill)
        result["already"] = min(already, requested)
        remaining = max(requested - already, 0.0)
        result["remaining"] = remaining
        if remaining <= 0.00001:
            result["remaining"] = 0.0
            return result

        source_lines = self._payable_lines_for_move(source_move).filtered(
            lambda line: line.amount_residual > 0.00001
        )
        bill_lines = self._payable_lines_for_move(bill).filtered(
            lambda line: line.amount_residual < -0.00001
        )
        if not source_lines or not bill_lines:
            result["message"] = "No compatible open payable lines are available."
            return result

        Partial = self.env["account.partial.reconcile"].sudo()
        for source_line in source_lines:
            compatible_bills = bill_lines.filtered(
                lambda line, src=source_line:
                    line.account_id == src.account_id
                    and (
                        not line.partner_id
                        or not src.partner_id
                        or line.partner_id.commercial_partner_id == src.partner_id.commercial_partner_id
                    )
            )
            for bill_line in compatible_bills:
                if remaining <= 0.00001:
                    break
                source_line.invalidate_recordset()
                bill_line.invalidate_recordset()
                available = min(
                    remaining,
                    max(source_line.amount_residual, 0.0),
                    abs(min(bill_line.amount_residual, 0.0)),
                )
                if available <= 0.00001:
                    continue
                Partial.create({
                    "debit_move_id": source_line.id,
                    "credit_move_id": bill_line.id,
                    "amount": available,
                    "debit_amount_currency": available,
                    "credit_amount_currency": available,
                })
                source_line.invalidate_recordset()
                bill_line.invalidate_recordset()
                remaining -= available
                result["new"] += available
            if remaining <= 0.00001:
                break

        result["remaining"] = max(remaining, 0.0)
        if result["remaining"] > 0.00001:
            result["message"] = (
                "Requested %.2f; already matched %.2f; newly matched %.2f; remaining %.2f. "
                "Another Odoo reconciliation may already be consuming the source or bill residual."
                % (requested, result["already"], result["new"], result["remaining"])
            )
        return result

    def _reconcile_vendor_payment_settlements_exact(
        self, payment, payload, force_post=False, allow_import_missing=True, log_result=True
    ):
        self.ensure_one()
        stats = {
            "allocation_count": 0,
            "already_reconciled": 0.0,
            "newly_reconciled": 0.0,
            "review_count": 0,
        }
        external_id = self._external_id(payload)
        if not payment:
            stats["review_count"] = 1
            return stats

        if getattr(payment, "state", False) == "draft":
            method, payable = self._prepare_vendor_payment_accounts(payment.journal_id, payment.partner_id)
            vals = {}
            if payment.payment_method_line_id != method:
                vals["payment_method_line_id"] = method.id
            if payment.destination_account_id != payable:
                vals["destination_account_id"] = payable.id
            if vals:
                payment.sudo().write(vals)
            self._validate_vendor_payment_accounts(payment)
            if force_post or self.auto_post_vendor_payments:
                payment.action_post()

        if not payment.move_id or payment.move_id.state != "posted":
            stats["review_count"] = 1
            if log_result:
                self._log(
                    "purchase_reconcile",
                    "error",
                    "Vendor payment %s is not posted, so Splendid settlements were not applied." % payment.display_name,
                    payload,
                    external_id,
                    payment,
                )
            return stats

        allocations = self._purchase_invoice_settlement_allocations(
            self._vendor_payment_settlement_lines(payload)
        )
        review_messages = []
        for allocation in allocations:
            stats["allocation_count"] += 1
            source_id = allocation["source_id"]
            source_number = allocation["source_number"]
            requested = allocation["amount"]
            if allow_import_missing:
                bill = self._ensure_purchase_invoice_for_payment_settlement(
                    source_id=source_id,
                    source_number=source_number,
                )
            else:
                bill = self._find_purchase_invoice_for_payment_settlement(
                    source_id=source_id,
                    source_number=source_number,
                )
            if not bill:
                stats["review_count"] += 1
                review_messages.append(
                    "Purchase invoice %s/%s not found for %.2f."
                    % (source_number or "", source_id or "", requested)
                )
                continue
            if bill.state == "draft" and force_post:
                bill.action_post()
            elif bill.state == "draft" and self.auto_post_purchase_bills:
                bill.action_post()
            if bill.state != "posted":
                stats["review_count"] += 1
                review_messages.append(
                    "Purchase invoice %s is not posted for settlement %.2f."
                    % (bill.display_name, requested)
                )
                continue
            result = self._apply_exact_purchase_settlement(payment.move_id, bill, requested)
            stats["already_reconciled"] += result["already"]
            stats["newly_reconciled"] += result["new"]
            if result["message"]:
                stats["review_count"] += 1
                review_messages.append(
                    "%s: %s" % (source_number or bill.display_name, result["message"])
                )

        if log_result:
            state = "error" if review_messages else "success"
            message = (
                "Vendor payment Splendid settlements checked: allocations=%s, newly reconciled=%.2f, "
                "already matched=%.2f."
                % (
                    stats["allocation_count"],
                    stats["newly_reconciled"],
                    stats["already_reconciled"],
                )
            )
            if review_messages:
                message += " Review: " + " | ".join(review_messages)
            self._log(
                "purchase_reconcile",
                state,
                message,
                payload,
                external_id,
                payment,
            )
        return stats

    def _fetch_vendor_settlement_list(self):
        """Fetch Splendid VendorSettlements using the connection date range.

        VendorSettlements is the authoritative source for which vendor payment /
        purchase return was actually settled against which purchase invoice.
        The list call is only used to obtain settlement IDs. Every row is then
        refreshed with GET /VendorSettlements/{id} before reconciliation.
        """
        self.ensure_one()
        date_payload = self._date_range_payload()
        if date_payload:
            return self._fetch_search_collection(
                "/VendorSettlements/Search",
                filter_payload=date_payload,
            )
        return self._fetch_collection(
            "/VendorSettlements",
            params={"orderBy": "Date", "ascending": "true"},
            use_paging=True,
        )

    def _normalize_vendor_settlement_source(self, value):
        return re.sub(r"[^a-z0-9]", "", str(value or "").strip().lower())

    def _vendor_settlement_ids_from_source_payload(self, payload):
        """Return unique VendorSettlement IDs referenced by a source payload."""
        ids = []
        direct_id = self._find_value(payload, "vendorSettlementId")
        if direct_id not in (False, None, ""):
            ids.append(direct_id)
        for item in self._find_value(payload, "vendorSingleSettledEntryItems", default=[]) or []:
            if not isinstance(item, dict):
                continue
            settlement_id = self._find_value(item, "vendorSettlementId")
            if settlement_id not in (False, None, "") and settlement_id not in ids:
                ids.append(settlement_id)
        return ids

    def _reconcile_vendor_settlements_referenced_by_payload(self, payload, log_missing=False):
        """Reconcile only VendorSettlements explicitly referenced by this payload."""
        self.ensure_one()
        settlement_ids = self._vendor_settlement_ids_from_source_payload(payload)
        if not settlement_ids:
            if log_missing:
                self._log(
                    "purchase_reconcile",
                    "skipped",
                    "No VendorSettlement ID is referenced by this Splendid source payload; bulk Reconcile Splendid Settlements can check the VendorSettlements API later.",
                    payload,
                    self._external_id(payload),
                )
            return True

        has_review = False
        for settlement_id in settlement_ids:
            try:
                settlement_payload = self._fetch_detail_by_id("/VendorSettlements", settlement_id)
                stats = self._reconcile_vendor_settlement_payload(settlement_payload, log_result=True)
                has_review = has_review or bool(stats.get("review_count"))
            except Exception as exc:  # pylint: disable=broad-except
                has_review = True
                self._log(
                    "purchase_reconcile",
                    "error",
                    "Could not reconcile VendorSettlement %s referenced by source %s: %s"
                    % (settlement_id, self._external_id(payload), exc),
                    payload,
                    settlement_id,
                )
        return not has_review

    def _find_vendor_payment_by_settlement_source(self, source_id=False, source_number=False):
        """Find an already imported Odoo vendor payment from Splendid source data.

        The Splendid VendorSettlement detail sourceId is the VendorPayment ID.
        Prefer account.payment.splendid_vendor_payment_id, then the sync map, and
        only use the visible Splendid payment number as a recovery fallback.
        """
        self.ensure_one()
        Payment = self.env["account.payment"].with_company(self.company_id).sudo()
        payment = Payment

        if source_id:
            payment = self._mapped_record("vendor_payment", source_id, "account.payment")
            if not payment and "splendid_vendor_payment_id" in Payment._fields:
                payment = Payment.search([
                    ("company_id", "=", self.company_id.id),
                    ("payment_type", "=", "outbound"),
                    ("partner_type", "=", "supplier"),
                    ("splendid_vendor_payment_id", "=", str(source_id)),
                ], limit=1)

        if not payment and source_number:
            payment = Payment.search([
                ("company_id", "=", self.company_id.id),
                ("payment_type", "=", "outbound"),
                ("partner_type", "=", "supplier"),
                ("payment_reference", "=", source_number),
            ], limit=1)

        if payment and source_id:
            vals = {}
            if "splendid_vendor_payment_id" in Payment._fields and not payment.splendid_vendor_payment_id:
                vals["splendid_vendor_payment_id"] = str(source_id)
            if vals:
                payment.write(vals)
            self._set_mapping(
                "vendor_payment",
                source_id,
                payment,
                {"id": source_id, "number": source_number},
                source_number or source_id,
            )
        return payment

    def _prepare_vendor_settlement_source_entry(self, detail):
        """Resolve one VendorSettlement detail into a posted Odoo accounting move."""
        self.ensure_one()
        source = self._normalize_vendor_settlement_source(
            self._find_value(detail, "source")
        )
        source_id = self._find_value(detail, "sourceId")
        source_number = self._find_value(detail, "number", "sourceNumber")
        amount = self._safe_float(self._find_value(detail, "adjustedAmount", "amount"), 0.0)
        side_raw = self._find_value(detail, "accountSide")
        try:
            account_side = int(float(str(side_raw)))
        except (TypeError, ValueError):
            account_side = None

        result = {
            "source": source,
            "source_id": source_id,
            "source_number": source_number,
            "amount": amount,
            "account_side": account_side,
            "record": False,
            "move": False,
            "message": False,
        }
        if amount <= 0.0:
            result["message"] = "Settlement detail has no positive adjustedAmount."
            return result
        if account_side not in (0, 1):
            result["message"] = "Settlement detail has unsupported accountSide %s." % side_raw
            return result

        if source == "vendorpayment":
            # VendorSettlement is the allocation source of truth, but the source
            # VendorPayment can later be voided in Splendid. Verify its current
            # state before touching Odoo so status=50 is never reconciled.
            payment_payload = {}
            if source_id:
                try:
                    payment_payload = self._fetch_detail_by_id("/VendorPayments", source_id)
                except Exception as exc:  # pylint: disable=broad-except
                    result["message"] = (
                        "Could not verify Splendid VendorPayment %s/%s before reconciliation: %s"
                        % (source_number or "", source_id, exc)
                    )
                    return result
                if self._vendor_payment_is_void(payment_payload):
                    result["message"] = (
                        "VendorPayment %s/%s is status=50 / void in Splendid and was not reconciled."
                        % (source_number or "", source_id)
                    )
                    return result

            payment = self._find_vendor_payment_by_settlement_source(
                source_id=source_id,
                source_number=source_number,
            )
            if not payment:
                result["message"] = (
                    "VendorPayment %s/%s was not found in Odoo. Run Sync Vendor Payments first."
                    % (source_number or "", source_id or "")
                )
                return result

            desired_journal = (
                self._resolve_journal_for_vendor_payment(payment_payload)
                if payment_payload else payment.journal_id
            )
            state = getattr(payment, "state", False)
            if payment.journal_id != desired_journal and state != "draft":
                result["message"] = (
                    "VendorPayment %s is posted in Odoo journal '%s', but Splendid payment account maps to '%s'. "
                    "Reset/delete and re-sync this payment before reconciliation."
                    % (source_number or source_id, payment.journal_id.display_name, desired_journal.display_name)
                )
                return result
            if payment.journal_id != desired_journal and state == "draft":
                payment.write({"journal_id": desired_journal.id})

            if getattr(payment, "state", False) == "draft":
                method, payable = self._prepare_vendor_payment_accounts(
                    desired_journal, payment.partner_id
                )
                vals = {}
                if payment.payment_method_line_id != method:
                    vals["payment_method_line_id"] = method.id
                if payment.destination_account_id != payable:
                    vals["destination_account_id"] = payable.id
                if vals:
                    payment.write(vals)
                self._validate_vendor_payment_accounts(payment)
                payment.action_post()
            if not payment.move_id or payment.move_id.state != "posted":
                result["message"] = "VendorPayment %s is not posted in Odoo." % (source_number or source_id)
                return result
            result.update({"record": payment, "move": payment.move_id})
            return result

        if source == "purchaseinvoice":
            bill = self._find_purchase_invoice_for_payment_settlement(
                source_id=source_id,
                source_number=source_number,
            )
            if not bill:
                result["message"] = (
                    "PurchaseInvoice %s/%s was not found in Odoo. Run Sync Purchase Invoices first."
                    % (source_number or "", source_id or "")
                )
                return result
            if bill.state == "draft":
                bill.action_post()
            if bill.state != "posted":
                result["message"] = "PurchaseInvoice %s is not posted in Odoo." % (source_number or source_id)
                return result
            result.update({"record": bill, "move": bill})
            return result

        if source in ("purchasereturn", "vendordebitnote", "debitnote"):
            refund = self._find_purchase_return_for_settlement(
                source_id,
                payload={"id": source_id, "number": source_number},
            )
            if not refund:
                result["message"] = (
                    "PurchaseReturn %s/%s was not found in Odoo. Run Sync Purchase Returns first."
                    % (source_number or "", source_id or "")
                )
                return result
            if refund.state == "draft":
                refund.action_post()
            if refund.state != "posted":
                result["message"] = "PurchaseReturn %s is not posted in Odoo." % (source_number or source_id)
                return result
            result.update({"record": refund, "move": refund})
            return result

        result["message"] = "Unsupported Splendid VendorSettlement source '%s'." % (
            self._find_value(detail, "source") or ""
        )
        return result

    def _apply_exact_payable_settlement(self, move_a, move_b, requested_amount):
        """Reconcile exactly one Splendid amount between two payable moves.

        Debit/credit direction is derived from Odoo residual signs rather than
        hard-coded source types. No payment or write-off is created here.
        """
        self.ensure_one()
        requested = self._safe_float(requested_amount, 0.0)
        result = {
            "requested": requested,
            "already": 0.0,
            "new": 0.0,
            "remaining": requested,
            "message": False,
        }
        if requested <= 0.0:
            return result
        if not move_a or not move_b:
            result["message"] = "One side of the settlement is missing in Odoo."
            return result

        company_currency = self.company_id.currency_id
        if move_a.currency_id != company_currency or move_b.currency_id != company_currency:
            result["message"] = "Foreign-currency VendorSettlement was not auto-reconciled."
            return result

        already_actual = self._existing_reconciled_amount_between_moves(move_a, move_b)
        result["already"] = min(already_actual, requested)
        if already_actual > requested + 0.00001:
            result["remaining"] = 0.0
            result["message"] = (
                "Odoo already has %.2f reconciled between these documents, more than Splendid %.2f."
                % (already_actual, requested)
            )
            return result

        remaining = max(requested - already_actual, 0.0)
        result["remaining"] = remaining
        if remaining <= 0.00001:
            result["remaining"] = 0.0
            return result

        lines_a = self._payable_lines_for_move(move_a)
        lines_b = self._payable_lines_for_move(move_b)
        if not lines_a or not lines_b:
            result["message"] = "No open payable lines are available on one or both documents."
            return result

        Partial = self.env["account.partial.reconcile"].sudo()
        for line_a in lines_a:
            for line_b in lines_b:
                if remaining <= 0.00001:
                    break
                if line_a.account_id != line_b.account_id:
                    continue
                if (
                    line_a.partner_id
                    and line_b.partner_id
                    and line_a.partner_id.commercial_partner_id != line_b.partner_id.commercial_partner_id
                ):
                    continue

                line_a.invalidate_recordset()
                line_b.invalidate_recordset()
                residual_a = line_a.amount_residual
                residual_b = line_b.amount_residual
                if residual_a > 0.00001 and residual_b < -0.00001:
                    debit_line, credit_line = line_a, line_b
                elif residual_b > 0.00001 and residual_a < -0.00001:
                    debit_line, credit_line = line_b, line_a
                else:
                    continue

                available = min(
                    remaining,
                    max(debit_line.amount_residual, 0.0),
                    abs(min(credit_line.amount_residual, 0.0)),
                )
                if available <= 0.00001:
                    continue
                Partial.create({
                    "debit_move_id": debit_line.id,
                    "credit_move_id": credit_line.id,
                    "amount": available,
                    "debit_amount_currency": available,
                    "credit_amount_currency": available,
                })
                remaining -= available
                result["new"] += available
            if remaining <= 0.00001:
                break

        result["remaining"] = max(remaining, 0.0)
        if result["remaining"] > 0.00001:
            result["message"] = (
                "Requested %.2f; already matched %.2f; newly matched %.2f; remaining %.2f. "
                "Check Odoo residuals, payable accounts, partner, or previous reconciliations."
                % (requested, result["already"], result["new"], result["remaining"])
            )
        return result

    def _reconcile_vendor_settlement_payload(self, payload, log_result=True):
        """Mirror one GET /VendorSettlements/{id} payload exactly in Odoo."""
        self.ensure_one()
        stats = {
            "allocation_count": 0,
            "already_reconciled": 0.0,
            "newly_reconciled": 0.0,
            "review_count": 0,
        }
        settlement_id = self._external_id(payload)
        settlement_number = self._find_value(payload, "number") or settlement_id
        status = self._find_value(payload, "status")
        try:
            status_int = int(float(str(status))) if status not in (False, None, "") else None
        except (TypeError, ValueError):
            status_int = None

        if status_int == 50:
            if log_result:
                self._log(
                    "purchase_reconcile",
                    "skipped",
                    "VendorSettlement %s skipped because Splendid status=50." % settlement_number,
                    payload,
                    settlement_id,
                )
            return stats

        details = self._find_value(payload, "vendorSettlementDetails", default=[]) or []
        if not details:
            if log_result:
                self._log(
                    "purchase_reconcile",
                    "skipped",
                    "VendorSettlement %s has no vendorSettlementDetails." % settlement_number,
                    payload,
                    settlement_id,
                )
            return stats

        side_entries = {0: [], 1: []}
        review_messages = []
        for detail in details:
            if not isinstance(detail, dict):
                continue
            entry = self._prepare_vendor_settlement_source_entry(detail)
            if entry["message"]:
                stats["review_count"] += 1
                review_messages.append(entry["message"])
                continue
            side_entries[entry["account_side"]].append(entry)

        side0_total = sum(item["amount"] for item in side_entries[0])
        side1_total = sum(item["amount"] for item in side_entries[1])
        if not side_entries[0] or not side_entries[1]:
            stats["review_count"] += 1
            review_messages.append(
                "VendorSettlement does not have valid entries on both accountSide 0 and 1."
            )
        elif abs(side0_total - side1_total) > 0.01:
            stats["review_count"] += 1
            review_messages.append(
                "Splendid settlement sides do not balance: side0 %.2f vs side1 %.2f."
                % (side0_total, side1_total)
            )

        # Pair the exact adjusted amounts in the same order returned by Splendid.
        # This preserves every detail's allocated total, including one payment
        # settled against several purchase invoices.
        right_index = 0
        right_remaining = side_entries[1][0]["amount"] if side_entries[1] else 0.0
        for left in side_entries[0]:
            left_remaining = left["amount"]
            while left_remaining > 0.00001 and right_index < len(side_entries[1]):
                right = side_entries[1][right_index]
                pair_amount = min(left_remaining, right_remaining)
                if pair_amount <= 0.00001:
                    right_index += 1
                    if right_index < len(side_entries[1]):
                        right_remaining = side_entries[1][right_index]["amount"]
                    continue

                stats["allocation_count"] += 1
                result = self._apply_exact_payable_settlement(
                    left["move"], right["move"], pair_amount
                )
                stats["already_reconciled"] += result["already"]
                stats["newly_reconciled"] += result["new"]
                if result["message"]:
                    stats["review_count"] += 1
                    review_messages.append(
                        "%s %s ↔ %s %s (%.2f): %s"
                        % (
                            left["source"], left["source_number"] or left["source_id"],
                            right["source"], right["source_number"] or right["source_id"],
                            pair_amount, result["message"],
                        )
                    )

                # Consume the Splendid target allocation even if Odoo could not
                # fully apply it; never redirect that shortfall to another bill.
                left_remaining -= pair_amount
                right_remaining -= pair_amount
                if right_remaining <= 0.00001:
                    right_index += 1
                    if right_index < len(side_entries[1]):
                        right_remaining = side_entries[1][right_index]["amount"]

        if log_result:
            state = "error" if review_messages else "success"
            message = (
                "VendorSettlement %s checked from Splendid API: allocations=%s, "
                "newly reconciled=%.2f, already matched=%.2f."
                % (
                    settlement_number,
                    stats["allocation_count"],
                    stats["newly_reconciled"],
                    stats["already_reconciled"],
                )
            )
            if review_messages:
                message += " Review: " + " | ".join(review_messages)
            self._log(
                "purchase_reconcile",
                state,
                message,
                payload,
                settlement_id,
            )
        return stats

    def _reconcile_all_purchase_settlements_from_splendid(self):
        """Button backend: VendorSettlements is the accounting source of truth."""
        self.ensure_one()
        summary = {
            "allocation_count": 0,
            "already_reconciled": 0.0,
            "newly_reconciled": 0.0,
            "review_count": 0,
        }

        settlement_rows = self._fetch_vendor_settlement_list()
        if not settlement_rows:
            self._log(
                "purchase_reconcile",
                "skipped",
                "Splendid returned 0 VendorSettlements for the current sync range. From Date=%s; To Date=%s."
                % (self.sync_from_date or "blank", self.sync_to_date or "blank"),
                {"from_date": self.sync_from_date, "to_date": self.sync_to_date},
            )
            return summary

        for row in settlement_rows:
            settlement_id = self._external_id(row)
            if not settlement_id:
                summary["review_count"] += 1
                self._log(
                    "purchase_reconcile",
                    "error",
                    "VendorSettlement list row has no Splendid ID.",
                    row,
                )
                continue
            try:
                with self.env.cr.savepoint():
                    # Never trust the list row for allocations. The GET-by-ID
                    # payload contains vendorSettlementDetails with real sourceId,
                    # accountSide and adjustedAmount values.
                    payload = self._fetch_detail_by_id("/VendorSettlements", settlement_id)
                    result = self._reconcile_vendor_settlement_payload(
                        payload,
                        log_result=True,
                    )
                    for key in summary:
                        summary[key] += result.get(key, 0)
            except Exception as exc:  # pylint: disable=broad-except
                summary["review_count"] += 1
                _logger.exception(
                    "Failed Splendid VendorSettlement reconciliation for %s", settlement_id
                )
                self._log(
                    "purchase_reconcile",
                    "error",
                    "VendorSettlement %s failed: %s" % (settlement_id, exc),
                    row,
                    settlement_id,
                )

        self._log(
            "purchase_reconcile",
            "error" if summary["review_count"] else "success",
            (
                "Splendid VendorSettlements reconciliation summary: settlements fetched=%s, "
                "allocations=%s, newly reconciled=%.2f, already matched=%.2f, review=%s."
                % (
                    len(settlement_rows),
                    summary["allocation_count"],
                    summary["newly_reconciled"],
                    summary["already_reconciled"],
                    summary["review_count"],
                )
            ),
            {"vendor_settlements_fetched": len(settlement_rows), **summary},
        )
        self.env.cr.commit()
        return summary

    def _default_purchase_journal(self):
        self.ensure_one()
        journal = self.purchase_journal_id
        if not journal:
            journal = self.env["account.journal"].with_company(self.company_id).sudo().search([
                ("company_id", "=", self.company_id.id),
                ("type", "=", "purchase"),
            ], limit=1)
        if not journal:
            raise UserError(_("Please configure a Purchase Journal for Splendid purchase sync."))
        return journal

    def _date_in_connection_range(self, value):
        date_value = self._parse_date(value) if value else False
        if not date_value:
            return True
        if self.sync_from_date and date_value < self.sync_from_date:
            return False
        if self.sync_to_date and date_value > self.sync_to_date:
            return False
        return True

    def _filter_rows_by_date_range(self, rows):
        if not (self.sync_from_date or self.sync_to_date):
            return rows
        return [row for row in rows if self._date_in_connection_range(self._find_value(row, "date"))]

    def _payload_in_sync_date_range(self, payload, date_field="date"):
        self.ensure_one()

        if not self.sync_from_date and not self.sync_to_date:
            return True

        payload_date = self._find_value(payload, date_field)
        if not payload_date:
            return True

        payload_date = self._parse_date(payload_date)

        if self.sync_from_date and payload_date < self.sync_from_date:
            return False

        if self.sync_to_date and payload_date > self.sync_to_date:
            return False

        return True


    def _fetch_purchase_list(self, key):
        self.ensure_one()

        endpoints = {
            "purchase_invoices": "/PurchaseInvoices",
            "purchase_returns": "/PurchaseReturns",
            "vendor_payments": "/VendorPayments",
        }
        search_endpoints = {
            "purchase_returns": "/PurchaseReturns/Search",
            "vendor_payments": "/VendorPayments/Search",
        }

        endpoint = endpoints[key]
        params = {
            "orderBy": "Date",
            "ascending": "true",
        }

        # Purchase Returns supports a dedicated Search endpoint with a date filter.
        # Use it when From/To Date is configured. This avoids silently dropping old
        # returns after the list call and makes deleted returns fetchable again as
        # long as their date is inside the configured range.
        date_payload = self._date_range_payload()
        if key in search_endpoints and date_payload:
            return self._fetch_search_collection(
                search_endpoints[key],
                filter_payload=date_payload,
            )

        # PurchaseInvoices list API in this integration is intentionally fetched
        # as one configured page; preserve the existing working behaviour.
        if key == "purchase_invoices":
            params.update({
                "page": 1,
                "size": 150,
            })
            rows = self._fetch_collection(
                endpoint,
                params=params,
                use_paging=False,
            )
        else:
            rows = self._fetch_collection(
                endpoint,
                params=params,
                use_paging=True,
            )

        # Safety filter for endpoints fetched without the Search API.
        return [
            row for row in rows
            if self._payload_in_sync_date_range(row, "date")
        ]
    def _sync_purchase_process(self):
        self.ensure_one()
        self._sync_purchase_invoices()
        self._sync_purchase_returns()
        self._sync_vendor_payments()
        self.last_purchase_process_sync = fields.Datetime.now()
        self.env.cr.commit()
        return True

    def _purchase_invoice_status_is_50(self, payload):
        """Return True when Splendid purchase invoice status is 50.

        Status 50 purchase invoices must not create an Odoo Purchase Order,
        receipt, vendor bill, or the invoice-triggered vendor payment flow.
        """
        if not isinstance(payload, dict):
            return False
        status = self._find_value(payload, "status")
        if status in (False, None, ""):
            return False
        try:
            return int(float(str(status).strip())) == 50
        except (TypeError, ValueError):
            return str(status).strip() == "50"

    def _vendor_payment_is_void(self, payload):
        """Splendid VendorPayment status 50 means void and must not be imported.

        isVoid is also honoured defensively. Existing Odoo payments are never
        deleted automatically; they are simply excluded from new import /
        settlement work and surfaced in the sync log for review.
        """
        if not isinstance(payload, dict):
            return False
        if self._safe_bool(self._find_value(payload, "isVoid"), False):
            return True
        status = self._find_value(payload, "status")
        if status in (False, None, ""):
            return False
        try:
            return int(float(str(status).strip())) == 50
        except (TypeError, ValueError):
            return str(status).strip() == "50"

    def _sync_purchase_invoices(self):
        self.ensure_one()
        rows = self._fetch_purchase_list("purchase_invoices")
        imported = failed = 0
        for row in rows:
            external_id = self._external_id(row)
            try:
                # Fast skip when the list endpoint already exposes status=50.
                if self._purchase_invoice_status_is_50(row):
                    self._log(
                        "purchase_invoices",
                        "skipped",
                        "Skipped Splendid purchase invoice because status=50.",
                        row,
                        external_id,
                    )
                    continue

                payload = self._fetch_detail_by_id("/PurchaseInvoices", external_id)

                # Authoritative guard on the full invoice payload. This prevents
                # PO / receipt / vendor bill / invoice-triggered payment creation.
                if self._purchase_invoice_status_is_50(payload):
                    self._log(
                        "purchase_invoices",
                        "skipped",
                        "Skipped Splendid purchase invoice because status=50.",
                        payload,
                        external_id,
                    )
                    continue

                record = self._import_purchase_invoice_process(payload)
                imported += 1
                self._log("purchase_invoices", "success", "Purchase invoice imported/updated as vendor bill", payload, external_id, record)
                self._sync_vendor_payments_from_purchase_invoice(payload)
            except Exception as exc:  # pylint: disable=broad-except
                failed += 1
                _logger.exception("Failed to import Splendid purchase invoice %s", external_id)
                self._log("purchase_invoices", "error", str(exc), row, external_id)
        self._set_count("purchase_invoices", len(rows), imported, failed)
        self.last_purchase_invoices_sync = fields.Datetime.now()
        self.env.cr.commit()
        return True

    def _sync_purchase_returns(self):
        self.ensure_one()
        rows = self._fetch_purchase_list("purchase_returns")
        imported = failed = 0

        if not rows:
            self._log(
                "purchase_returns",
                "skipped",
                "Splendid returned 0 purchase returns for the current sync range. From Date=%s, To Date=%s." % (
                    self.sync_from_date or "not set",
                    self.sync_to_date or "not set",
                ),
                {
                    "from_date": fields.Date.to_string(self.sync_from_date) if self.sync_from_date else False,
                    "to_date": fields.Date.to_string(self.sync_to_date) if self.sync_to_date else False,
                },
            )

        for row in rows:
            external_id = self._external_id(row)
            try:
                payload = self._fetch_detail_by_id("/PurchaseReturns", external_id)
                record = self._import_purchase_return_process(payload)
                imported += 1
                self._log(
                    "purchase_returns",
                    "success",
                    "Purchase return imported/updated and settlement reconciliation checked",
                    payload,
                    external_id,
                    record,
                )
            except Exception as exc:  # pylint: disable=broad-except
                failed += 1
                _logger.exception("Failed to import Splendid purchase return %s", external_id)
                self._log("purchase_returns", "error", str(exc), row, external_id)

        self._set_count("purchase_returns", len(rows), imported, failed)
        self.last_purchase_returns_sync = fields.Datetime.now()
        self._log(
            "purchase_returns",
            "success" if not failed else "error",
            "Purchase return sync summary: fetched=%s imported=%s failed=%s" % (len(rows), imported, failed),
            {"fetched": len(rows), "imported": imported, "failed": failed},
        )
        self.env.cr.commit()
        return True

    def _sync_vendor_payments(self):
        self.ensure_one()
        rows = self._fetch_purchase_list("vendor_payments")
        imported = failed = skipped = 0
        for row in rows:
            external_id = self._external_id(row)

            # Fast skip when the list endpoint already exposes status=50 / void.
            # Do not create or update an Odoo payment for a void Splendid payment.
            if self._vendor_payment_is_void(row):
                skipped += 1
                self._log(
                    "vendor_payments",
                    "skipped",
                    "Skipped Splendid vendor payment because status=50 / void.",
                    row,
                    external_id,
                )
                continue

            try:
                # A failed account.payment.action_post() can put the PostgreSQL
                # transaction in an aborted state. Keep each payment isolated so a
                # bad payment setup never breaks the complete Purchase sync.
                with self.env.cr.savepoint():
                    payload = self._fetch_detail_by_id("/VendorPayments", external_id)
                    if self._vendor_payment_is_void(payload):
                        skipped += 1
                        self._log(
                            "vendor_payments",
                            "skipped",
                            "Skipped Splendid vendor payment because detail status=50 / void.",
                            payload,
                            external_id,
                        )
                        continue
                    record = self._import_vendor_payment_process(payload)
                    if record:
                        imported += 1
                        self._log(
                            "vendor_payments",
                            "success",
                            "Vendor payment imported/updated",
                            payload,
                            external_id,
                            record,
                        )
            except Exception as exc:  # pylint: disable=broad-except
                failed += 1
                _logger.exception("Failed to import Splendid vendor payment %s", external_id)
                self._log("vendor_payments", "error", str(exc), row, external_id)
        self._set_count("vendor_payments", len(rows), imported, failed)
        self.last_vendor_payments_sync = fields.Datetime.now()
        self._log(
            "vendor_payments",
            "success" if not failed else "error",
            "Vendor payment sync summary: fetched=%s imported=%s skipped_void=%s failed=%s"
            % (len(rows), imported, skipped, failed),
            {"fetched": len(rows), "imported": imported, "skipped_void": skipped, "failed": failed},
        )
        self.env.cr.commit()
        return True

    def _sync_vendor_payments_from_purchase_invoice(self, invoice_payload):
        for item in self._find_value(invoice_payload, "vendorSingleSettledEntryItems", default=[]) or []:
            if not isinstance(item, dict):
                continue
            if str(self._find_value(item, "source", default="")).lower() != "vendorpayment":
                continue
            payment_id = self._find_value(item, "sourceId")
            if not payment_id:
                continue
            try:
                # Important: purchase invoice import must survive a payment posting
                # configuration error. The savepoint rolls back only this payment.
                with self.env.cr.savepoint():
                    payment_payload = self._fetch_detail_by_id("/VendorPayments", payment_id)
                    if self._vendor_payment_is_void(payment_payload):
                        self._log(
                            "vendor_payments",
                            "skipped",
                            "Vendor payment referenced by purchase invoice was skipped because Splendid status=50 / void.",
                            payment_payload,
                            payment_id,
                        )
                        continue
                    payment = self._import_vendor_payment_process(payment_payload)
                    if payment:
                        self._log("vendor_payments", "success", "Vendor payment imported from purchase invoice settlement", payment_payload, payment_id, payment)
            except Exception as exc:  # pylint: disable=broad-except
                _logger.exception("Failed to import vendor payment %s from purchase invoice settlement", payment_id)
                self._log("vendor_payments", "error", str(exc), item, payment_id)

    def _resolve_vendor(self, payload):
        external_id = self._find_value(payload, "vendorId")
        partner = self._mapped_record("vendor", external_id, "res.partner") if external_id else self.env["res.partner"]
        if partner:
            return partner
        nested = self._nested(payload, "vendor")
        if nested:
            return self._import_partner(nested, "vendor")
        raise UserError(_("Vendor could not be resolved for Splendid record %s") % self._external_id(payload))

    def _purchase_invoice_details(self, payload):
        details = self._find_value(payload, "purchaseInvoiceDetails", default=[]) or []
        return details if isinstance(details, list) else []

    def _purchase_return_details(self, payload):
        details = self._find_value(payload, "purchaseReturnDetails", default=[]) or []
        return details if isinstance(details, list) else []

    def _vendor_location(self):
        loc = self.env.ref("stock.stock_location_suppliers", raise_if_not_found=False)
        if not loc:
            loc = self.env["stock.location"].sudo().search([("usage", "=", "supplier")], limit=1)
        if not loc:
            raise UserError(_("Vendor stock location was not found."))
        return loc

    def _resolve_purchase_line_account(self, line, product_tmpl):
        product_payload = self._nested(line, "product")
        account_candidates = [
            self._find_value(product_payload, "expenseAccountId"),
            self._find_value(product_payload, "inventoryAccountId"),
            self._find_value(line, "accountId"),
        ]
        account_code = self._find_value(self._nested(line, "account"), "code")
        for account_id in account_candidates:
            account = self._resolve_account(account_id, account_code if account_id == self._find_value(line, "accountId") else False)
            if account and account.account_type not in ("income", "income_other", "asset_receivable", "liability_payable"):
                return account
        if product_tmpl:
            product = product_tmpl.product_variant_id
            account = product.property_account_expense_id or product.categ_id.property_account_expense_categ_id
            if account:
                return account
        account = self.default_expense_account_id or self._default_account("expense")
        if not account:
            raise UserError(_("No expense account found/configured for Splendid purchase line."))
        return account

    def _vendor_bill_line_vals_from_purchase_line(self, line, move_type="in_invoice", purchase_line=False):
        product_tmpl = self._resolve_product_from_line(line)
        self._apply_product_inventory_uom_from_payload(product_tmpl, self._nested(line, "product") or line)
        product = product_tmpl.product_variant_id
        taxes = self._resolve_taxes_from_line(line, "purchase")

        # IMPORTANT: under Odoo Anglo-Saxon + automated valuation, a storable
        # product's Vendor Bill line must be allowed to use Odoo's native
        # account computation. stock_account.AccountMoveLine._compute_account_id
        # replaces the purchase expense account with the Product Category's
        # Stock Input (Interim Received) account.
        #
        # Do NOT force Splendid expenseAccountId / inventoryAccountId here for
        # real-time valued stock products; doing so posts the whole purchase
        # directly to COGS and bypasses Odoo's stock-interim reconciliation.
        use_native_stock_account = bool(
            self.company_id.anglo_saxon_accounting
            and getattr(product, "is_storable", False)
            and getattr(product, "valuation", False) == "real_time"
        )

        vals = {
            "product_id": product.id,
            "name": self._find_value(line, "description") or product.display_name,
            "quantity": self._safe_float(self._find_value(line, "quantity"), 1.0),
            "price_unit": self._safe_float(self._find_value(line, "price", "tagPrice"), 0.0),
            "discount": self._line_discount_percent(line),
        }
        if not use_native_stock_account:
            account = self._resolve_purchase_line_account(line, product_tmpl)
            vals["account_id"] = account.id
        # Splendid is the tax source of truth for Vendor Bills/Debit Notes.
        # Explicitly clear Odoo product Vendor Taxes when the Splendid line has
        # no tax; otherwise use only the mapped Splendid taxes.
        vals["tax_ids"] = [(6, 0, taxes.ids)]
        if purchase_line and "purchase_line_id" in self.env["account.move.line"]._fields:
            vals["purchase_line_id"] = purchase_line.id
        elif purchase_line and "purchase_line_ids" in self.env["account.move.line"]._fields:
            vals["purchase_line_ids"] = [(6, 0, [purchase_line.id])]
        return vals

    def _get_or_create_purchase_adjustment_product(self, name, default_code):
        self.ensure_one()
        Product = self.env["product.template"].with_company(self.company_id).sudo()
        domain = ["|", ("default_code", "=", default_code), ("name", "=", name)]
        if "company_id" in Product._fields:
            domain = ["&", "|", ("company_id", "=", False), ("company_id", "=", self.company_id.id)] + domain
        product_tmpl = Product.search(domain, limit=1)
        vals = {}
        if "sale_ok" in Product._fields:
            vals["sale_ok"] = False
        if "purchase_ok" in Product._fields:
            vals["purchase_ok"] = True
        if "type" in Product._fields:
            vals["type"] = "service"
        if "detailed_type" in Product._fields:
            vals["detailed_type"] = "service"
        expense_account = self.default_expense_account_id or self._default_account("expense")
        if expense_account and "property_account_expense_id" in Product._fields:
            vals["property_account_expense_id"] = expense_account.id
        if product_tmpl:
            if vals:
                product_tmpl.write(vals)
            return product_tmpl
        vals.update({
            "name": name,
            "default_code": default_code,
            "list_price": 0.0,
            "standard_price": 0.0,
        })
        if "company_id" in Product._fields:
            vals["company_id"] = self.company_id.id
        return Product.create(vals)

    def _purchase_adjustment_line_cmd(self, payload, field_name, name, default_code, sign=1.0):
        self.ensure_one()
        amount = self._safe_float(self._find_value(payload, field_name), 0.0)
        if amount <= 0:
            return False
        product_tmpl = self._get_or_create_purchase_adjustment_product(name, default_code)
        product = product_tmpl.product_variant_id
        account = (
            product.property_account_expense_id
            or product.categ_id.property_account_expense_categ_id
            or self.default_expense_account_id
            or self._default_account("expense")
        )
        if not account:
            raise UserError(_("Expense account is required for %s product.") % name)
        return (0, 0, {
            "product_id": product.id,
            "name": name,
            "quantity": 1.0,
            "price_unit": amount * sign,
            "discount": 0.0,
            "account_id": account.id,
            "tax_ids": [(6, 0, [])],
        })

    def _purchase_shipping_amount(self, payload):
        """Return the Splendid purchase invoice shippingCharges amount."""
        self.ensure_one()
        amount = self._safe_float(
            self._find_value(
                payload,
                "shippingCharges",
                "shippingCharge",
                "shipping_charges",
                "shipping_charge",
            ),
            0.0,
        )
        return amount if amount > 0.0 else 0.0

    def _get_or_create_purchase_shipping_product(self):
        """Return the single service product used for Splendid purchase shipping."""
        return self._get_or_create_purchase_adjustment_product(
            "shippingCharges",
            "SHIPPING_CHARGES",
        )

    def _purchase_shipping_order_line_vals(self, payload):
        """Build the Purchase Order service line for Splendid shippingCharges."""
        self.ensure_one()
        amount = self._purchase_shipping_amount(payload)
        if not amount:
            return False

        product_tmpl = self._get_or_create_purchase_shipping_product()
        product = product_tmpl.product_variant_id
        PurchaseLine = self.env["purchase.order.line"]
        vals = {
            "product_id": product.id,
            "name": "shippingCharges",
            "product_qty": 1.0,
            "price_unit": amount,
            "product_uom": (product.uom_po_id or product.uom_id).id,
            "date_planned": fields.Datetime.now(),
        }
        if "taxes_id" in PurchaseLine._fields:
            vals["taxes_id"] = [(6, 0, [])]
        if "discount" in PurchaseLine._fields:
            vals["discount"] = 0.0
        return vals

    def _purchase_shipping_bill_line_cmd(self, payload, purchase_line=False):
        """Build the Vendor Bill line for Splendid shippingCharges."""
        self.ensure_one()
        amount = self._purchase_shipping_amount(payload)
        if not amount:
            return False

        product_tmpl = self._get_or_create_purchase_shipping_product()
        product = product_tmpl.product_variant_id
        account = (
            product.property_account_expense_id
            or product.categ_id.property_account_expense_categ_id
            or self.default_expense_account_id
            or self._default_account("expense")
        )
        if not account:
            raise UserError(_("Expense account is required for shippingCharges product."))

        vals = {
            "product_id": product.id,
            "name": "shippingCharges",
            "quantity": 1.0,
            "price_unit": amount,
            "discount": 0.0,
            "account_id": account.id,
            "tax_ids": [(6, 0, [])],
        }
        MoveLine = self.env["account.move.line"]
        if purchase_line and "purchase_line_id" in MoveLine._fields:
            vals["purchase_line_id"] = purchase_line.id
        elif purchase_line and "purchase_line_ids" in MoveLine._fields:
            vals["purchase_line_ids"] = [(6, 0, [purchase_line.id])]
        return (0, 0, vals)

    def _ensure_purchase_shipping_order_line(self, order, payload):
        """Idempotently add/update shippingCharges on an existing Purchase Order."""
        self.ensure_one()
        amount = self._purchase_shipping_amount(payload)
        if not order or not amount:
            return self.env["purchase.order.line"]

        product_tmpl = self._get_or_create_purchase_shipping_product()
        product = product_tmpl.product_variant_id
        line = order.order_line.filtered(lambda l: l.product_id.id == product.id)[:1]
        vals = self._purchase_shipping_order_line_vals(payload)
        if line:
            line.sudo().write({
                "name": vals["name"],
                "product_qty": vals["product_qty"],
                "price_unit": vals["price_unit"],
                "product_uom": vals["product_uom"],
                **({"taxes_id": vals["taxes_id"]} if "taxes_id" in vals else {}),
                **({"discount": vals["discount"]} if "discount" in vals else {}),
            })
            return line

        vals["order_id"] = order.id
        return self.env["purchase.order.line"].with_company(self.company_id).sudo().create(vals)

    def _ensure_purchase_shipping_bill_line(self, bill, payload, purchase_order=False):
        """Idempotently add/update shippingCharges on a draft Vendor Bill.

        Posted bills are never altered automatically; accounting entries already
        posted in Odoo must remain stable.
        """
        self.ensure_one()
        amount = self._purchase_shipping_amount(payload)
        if not bill or not amount:
            return self.env["account.move.line"]
        if bill.state != "draft":
            self._log(
                "purchase_invoices",
                "skipped",
                "shippingCharges could not be added because the existing Vendor Bill is already posted.",
                payload,
                self._external_id(payload),
                bill,
            )
            return self.env["account.move.line"]

        product_tmpl = self._get_or_create_purchase_shipping_product()
        product = product_tmpl.product_variant_id
        bill_line = bill.invoice_line_ids.filtered(lambda l: l.product_id.id == product.id)[:1]
        purchase_line = self.env["purchase.order.line"]
        if purchase_order:
            purchase_line = purchase_order.order_line.filtered(lambda l: l.product_id.id == product.id)[:1]

        cmd = self._purchase_shipping_bill_line_cmd(payload, purchase_line=purchase_line)
        vals = dict(cmd[2])
        if bill_line:
            bill_line.sudo().write(vals)
            return bill_line

        vals["move_id"] = bill.id
        return self.env["account.move.line"].with_company(self.company_id).sudo().create(vals)

    def _purchase_discount_line_cmd(self, payload):
        return self._purchase_adjustment_line_cmd(payload, "discountAmount", "Purchase Discount", "PURCHASE_DISCOUNT", sign=-1.0)

    def _purchase_tax_amount_line_cmd(self, payload):
        return self._purchase_adjustment_line_cmd(payload, "taxAmount", "Purchase Tax Amount", "PURCHASE_TAX_AMOUNT", sign=1.0)

    def _purchase_auto_roundoff_line_cmd(self, payload):
        amount = self._safe_float(self._find_value(payload, "autoRoundOff"), 0.0)
        if abs(amount) <= 0.00001:
            return False
        product_tmpl = self._get_or_create_purchase_adjustment_product("Purchase Round Off", "PURCHASE_ROUND_OFF")
        product = product_tmpl.product_variant_id
        account = product.property_account_expense_id or product.categ_id.property_account_expense_categ_id or self.default_expense_account_id or self._default_account("expense")
        if not account:
            raise UserError(_("Expense account is required for Purchase Round Off product."))
        return (0, 0, {
            "product_id": product.id,
            "name": "Purchase Round Off",
            "quantity": 1.0,
            "price_unit": amount,
            "discount": 0.0,
            "account_id": account.id,
            "tax_ids": [(6, 0, [])],
        })

    def _purchase_order_line_vals_from_invoice_line(self, line):
        product_tmpl = self._resolve_product_from_line(line)
        self._apply_product_inventory_uom_from_payload(product_tmpl, self._nested(line, "product") or line)
        product = product_tmpl.product_variant_id
        taxes = self._resolve_taxes_from_line(line, "purchase")
        PurchaseLine = self.env["purchase.order.line"]
        vals = {
            "product_id": product.id,
            "name": self._find_value(line, "description") or product.display_name,
            "product_qty": self._safe_float(self._find_value(line, "quantity"), 1.0),
            "price_unit": self._safe_float(self._find_value(line, "price", "tagPrice"), 0.0),
            "product_uom": (product.uom_po_id or product.uom_id).id,
            "date_planned": self._parse_datetime(self._find_value(line, "date") or fields.Datetime.now()),
        }
        if "discount" in PurchaseLine._fields:
            vals["discount"] = self._line_discount_percent(line)
        if "taxes_id" in PurchaseLine._fields:
            # Always write the source tax set (including empty) so the
            # product/category Vendor Taxes cannot leak into Splendid POs.
            vals["taxes_id"] = [(6, 0, taxes.ids)]
        return vals

    def _prepare_purchase_order_from_invoice(self, payload):
        self.ensure_one()
        external_id = self._external_id(payload)
        order = self._mapped_record("purchase_invoice_order", external_id, "purchase.order")
        if order:
            self._ensure_purchase_shipping_order_line(order, payload)
            if order.state in ("draft", "sent", "to approve"):
                order.button_confirm()
            if self.auto_create_purchase_receipts:
                self._mark_purchase_receipt_from_order(order, payload)
            return order

        partner = self._resolve_vendor(payload)
        details = self._purchase_invoice_details(payload)
        if not details:
            raise UserError(_("No purchase invoice lines found for Splendid purchase invoice %s") % external_id)

        warehouse = self._resolve_warehouse(details[0]) if details else False
        order_line_commands = [
            (0, 0, self._purchase_order_line_vals_from_invoice_line(line))
            for line in details
        ]
        shipping_order_line = self._purchase_shipping_order_line_vals(payload)
        if shipping_order_line:
            order_line_commands.append((0, 0, shipping_order_line))

        order_vals = {
            "partner_id": partner.id,
            "date_order": self._parse_datetime(self._find_value(payload, "date")),
            "origin": self._find_value(payload, "number") or external_id,
            "company_id": self.company_id.id,
            "order_line": order_line_commands,
            "splendid_purchase_invoice_id": external_id,
            "splendid_purchase_invoice_number": self._find_value(payload, "number"),
            "splendid_is_imported": True,
        }
        if warehouse and warehouse.in_type_id and "picking_type_id" in self.env["purchase.order"]._fields:
            order_vals["picking_type_id"] = warehouse.in_type_id.id
        if "splendid_raw_payload" in self.env["purchase.order"]._fields:
            order_vals["splendid_raw_payload"] = payload

        order = self.env["purchase.order"].with_company(self.company_id).sudo().create(order_vals)
        self._set_mapping("purchase_invoice_order", external_id, order, payload, order.name)

        if order.state in ("draft", "sent", "to approve"):
            order.button_confirm()

        if self.auto_create_purchase_receipts:
            self._mark_purchase_receipt_from_order(order, payload)

        return order

    def _mark_purchase_receipt_from_order(self, order, payload):
        external_id = self._external_id(payload)
        pickings = order.picking_ids.filtered(lambda p: p.state != "cancel") if "picking_ids" in order._fields else self.env["stock.picking"]
        for picking in pickings:
            vals = {
                "splendid_purchase_invoice_id": external_id,
                "splendid_source_model": "purchase_invoice_receipt",
                "splendid_is_imported": True,
            }
            if "splendid_raw_payload" in picking._fields:
                vals["splendid_raw_payload"] = payload
            picking.sudo().write(vals)
            self._set_mapping("purchase_invoice_receipt", "%s_%s" % (external_id, picking.id), picking, payload, picking.name)
            if self.auto_validate_purchase_receipts:
                self._validate_picking(picking)
        return pickings

    def _import_purchase_invoice_process(self, payload):
        external_id = self._external_id(payload)

        # Defensive guard for every entry point (manual purchase sync, purchase
        # process, or vendor-payment settlement auto-import). Status 50 is not
        # allowed to create any Odoo purchase document.
        if self._purchase_invoice_status_is_50(payload):
            self._log(
                "purchase_invoices",
                "skipped",
                "Skipped Splendid purchase invoice because status=50.",
                payload,
                external_id,
            )
            return self.env["account.move"].with_company(self.company_id).sudo()

        purchase_order = self._prepare_purchase_order_from_invoice(payload)

        existing_bill = self._mapped_record("purchase_invoice", external_id, "account.move")
        if existing_bill:
            self._ensure_purchase_shipping_bill_line(
                existing_bill,
                payload,
                purchase_order=purchase_order,
            )
            # v36: if an older Splendid Vendor Bill is still draft, repair stock
            # product lines before posting so Anglo-Saxon accounting uses Stock
            # Interim (Received), not a Splendid COGS/expense account. Posted
            # bills are deliberately never rewritten here.
            if existing_bill.state == "draft":
                existing_bill._splendid_repair_purchase_bill_stock_accounts(raise_on_posted=False)
            if self.auto_post_purchase_bills and existing_bill.state == "draft":
                existing_bill.action_post()
            if self.auto_create_purchase_receipts:
                self._mark_purchase_receipt_from_order(purchase_order, payload)
            return existing_bill

        partner = self._resolve_vendor(payload)
        details = self._purchase_invoice_details(payload)
        if not details:
            raise UserError(_("No purchase invoice lines found for Splendid purchase invoice %s") % external_id)

        purchase_lines_by_product = {}
        for po_line in purchase_order.order_line:
            if po_line.product_id:
                purchase_lines_by_product.setdefault(po_line.product_id.id, []).append(po_line)

        invoice_lines = []
        for line in details:
            product_tmpl = self._resolve_product_from_line(line)
            product = product_tmpl.product_variant_id
            purchase_line = False
            product_lines = purchase_lines_by_product.get(product.id) or []
            if product_lines:
                purchase_line = product_lines.pop(0)
            invoice_lines.append((0, 0, self._vendor_bill_line_vals_from_purchase_line(
                line,
                move_type="in_invoice",
                purchase_line=purchase_line,
            )))

        # Splendid exposes purchase shipping as a top-level shippingCharges amount.
        # Keep it as one tax-free service line on both the PO and Vendor Bill.
        shipping_product = self._get_or_create_purchase_shipping_product() if self._purchase_shipping_amount(payload) else False
        shipping_purchase_line = False
        if shipping_product:
            shipping_product_id = shipping_product.product_variant_id.id
            shipping_lines = purchase_lines_by_product.get(shipping_product_id) or []
            if shipping_lines:
                shipping_purchase_line = shipping_lines.pop(0)
        shipping_line = self._purchase_shipping_bill_line_cmd(
            payload,
            purchase_line=shipping_purchase_line,
        )
        if shipping_line:
            invoice_lines.append(shipping_line)

        discount_line = self._purchase_discount_line_cmd(payload)
        if discount_line:
            invoice_lines.append(discount_line)
        tax_line = self._purchase_tax_amount_line_cmd(payload)
        if tax_line:
            invoice_lines.append(tax_line)
        round_line = self._purchase_auto_roundoff_line_cmd(payload)
        if round_line:
            invoice_lines.append(round_line)

        move_vals = {
            "move_type": "in_invoice",
            "partner_id": partner.id,
            "invoice_date": self._parse_date(self._find_value(payload, "date")),
            "invoice_date_due": self._parse_date(self._find_value(payload, "dueDate")) if self._find_value(payload, "dueDate") else False,
            "journal_id": self._default_purchase_journal().id,
            "ref": self._find_value(payload, "number", "reference", "paymentReference") or external_id,
            "invoice_origin": purchase_order.name,
            "invoice_line_ids": invoice_lines,
            "company_id": self.company_id.id,
            "splendid_purchase_invoice_id": external_id,
            "splendid_source_model": "purchase_invoice",
            "splendid_is_imported": True,
        }
        if "splendid_raw_payload" in self.env["account.move"]._fields:
            move_vals["splendid_raw_payload"] = payload

        bill = self.env["account.move"].with_company(self.company_id).sudo().with_context(default_move_type="in_invoice").create(move_vals)
        self._set_mapping("purchase_invoice", external_id, bill, payload, move_vals["ref"])

        if self.auto_post_purchase_bills and bill.state == "draft":
            bill.action_post()
        if self.auto_create_purchase_receipts:
            self._mark_purchase_receipt_from_order(purchase_order, payload)
        return bill

    def _create_purchase_receipt_from_invoice(self, payload):
        external_id = self._external_id(payload)
        existing = self._mapped_record("purchase_invoice_receipt", external_id, "stock.picking")
        if existing:
            return existing
        details = self._purchase_invoice_details(payload)
        if not details:
            return self.env["stock.picking"]
        warehouse = self._resolve_warehouse(details[0])
        picking_type = warehouse.in_type_id or self.env["stock.picking.type"].with_company(self.company_id).sudo().search([
            ("code", "=", "incoming"),
            ("company_id", "=", self.company_id.id),
        ], limit=1)
        source_location = self._vendor_location()
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
            "partner_id": self._resolve_vendor(payload).id,
            "location_id": source_location.id,
            "location_dest_id": dest_location.id,
            "origin": self._find_value(payload, "number") or external_id,
            "scheduled_date": self._parse_datetime(self._find_value(payload, "date")),
            "company_id": self.company_id.id,
            "move_ids": move_cmds,
            "splendid_purchase_invoice_id": external_id,
            "splendid_source_model": "purchase_invoice_receipt",
            "splendid_is_imported": True,
        }
        if "splendid_raw_payload" in self.env["stock.picking"]._fields:
            picking_vals["splendid_raw_payload"] = payload
        picking = self.env["stock.picking"].with_company(self.company_id).sudo().create(picking_vals)
        self._set_mapping("purchase_invoice_receipt", external_id, picking, payload, picking.name)
        if picking.state == "draft":
            picking.action_confirm()
        if self.auto_validate_purchase_receipts:
            self._validate_picking(picking)
        return picking

    def _get_original_purchase_bills(self, payload):
        moves = self.env["account.move"].with_company(self.company_id).sudo()
        settlement_lines = self._find_value(payload, "purchaseReturnSettlementDetails", default=[]) or []
        settlement_lines += self._find_value(payload, "vendorSingleSettledEntryItems", default=[]) or []
        for item in settlement_lines:
            if not isinstance(item, dict):
                continue
            if str(self._find_value(item, "source", default="")).lower() != "purchaseinvoice":
                continue
            source_id = self._find_value(item, "sourceId")
            source_number = self._find_value(item, "sourceNumber", "number")
            move = self._find_purchase_invoice_for_payment_settlement(source_id=source_id, source_number=source_number)
            if move:
                moves |= move
        source_id = self._find_value(payload, "purchaseInvoiceId")
        if source_id:
            move = self._find_purchase_invoice_for_payment_settlement(source_id=source_id)
            if move:
                moves |= move
        return moves

    def _import_purchase_return_process(self, payload):
        self.ensure_one()
        external_id = self._external_id(payload)
        Move = self.env["account.move"].with_company(self.company_id).sudo()

        debit_note = self._mapped_record("purchase_return", external_id, "account.move")

        # Mapping can be deleted independently from the refund. Reuse the actual
        # Odoo refund when it still exists instead of creating a duplicate.
        if not debit_note and external_id and "splendid_purchase_return_id" in Move._fields:
            debit_note = Move.search([
                ("company_id", "=", self.company_id.id),
                ("move_type", "=", "in_refund"),
                ("splendid_purchase_return_id", "=", str(external_id)),
            ], limit=1)
            if debit_note:
                self._set_mapping(
                    "purchase_return",
                    external_id,
                    debit_note,
                    payload,
                    self._find_value(payload, "number", "reference") or external_id,
                )

        # If the Odoo refund was deleted, a stale mapping resolves to an empty
        # recordset and this recreates the refund. _set_mapping() then heals the
        # old mapping row to point to the new Odoo record.
        if not debit_note:
            debit_note = self._create_purchase_return_credit_note(payload)

        if debit_note.state == "draft" and self.auto_post_purchase_bills:
            debit_note.action_post()

        # Reconcile through the authoritative Splendid VendorSettlement IDs.
        # The source payload is only used to discover vendorSettlementId; the
        # actual allocation comes from GET /VendorSettlements/{id}.
        if debit_note.state == "posted" and self.auto_reconcile_vendor_payments:
            self._reconcile_vendor_settlements_referenced_by_payload(
                payload,
                log_missing=False,
            )

        if self.auto_create_purchase_return_transfers:
            self._create_purchase_return_transfer(payload)
        return debit_note

    def _purchase_return_settlement_lines(self, payload):
        """Return one non-duplicated settlement list from a Splendid return.

        The detail payload can expose the same allocation twice:
        purchaseReturnSettlementDetails (adjustedAmount) and
        vendorSingleSettledEntryItems (amount). Prefer the first list so amounts
        are never reconciled twice.
        """
        primary = self._find_value(payload, "purchaseReturnSettlementDetails", default=[]) or []
        if primary:
            return primary
        return self._find_value(payload, "vendorSingleSettledEntryItems", default=[]) or []

    def _open_payable_lines(self, move):
        if not move:
            return self.env["account.move.line"]
        return move.line_ids.filtered(
            lambda line:
                not line.reconciled
                and abs(line.amount_residual) > 0.00001
                and line.account_id.account_type == "liability_payable"
        )

    def _reconcile_purchase_return_settlements_exact(
        self, debit_note, payload, force_post=False, allow_import_missing=True, log_result=True
    ):
        """Apply exact Splendid Purchase Return allocations bill by bill.

        The method is idempotent: it first measures what is already reconciled
        between this refund and the target bill, then applies only the remaining
        Splendid allocation. No payment or write-off is created.
        """
        self.ensure_one()
        stats = {
            "allocation_count": 0,
            "already_reconciled": 0.0,
            "newly_reconciled": 0.0,
            "review_count": 0,
        }
        external_id = self._external_id(payload)
        if not debit_note:
            stats["review_count"] = 1
            return stats

        if debit_note.state == "draft" and force_post:
            debit_note.action_post()
        elif debit_note.state == "draft" and self.auto_post_purchase_bills:
            debit_note.action_post()
        if debit_note.state != "posted":
            stats["review_count"] = 1
            if log_result:
                self._log(
                    "purchase_reconcile",
                    "error",
                    "Purchase return %s is not posted, so Splendid settlements were not applied."
                    % debit_note.display_name,
                    payload,
                    external_id,
                    debit_note,
                )
            return stats

        allocations = self._purchase_invoice_settlement_allocations(
            self._purchase_return_settlement_lines(payload)
        )
        review_messages = []
        for allocation in allocations:
            stats["allocation_count"] += 1
            source_id = allocation["source_id"]
            source_number = allocation["source_number"]
            requested = allocation["amount"]
            if allow_import_missing:
                bill = self._ensure_purchase_invoice_for_payment_settlement(
                    source_id=source_id,
                    source_number=source_number,
                )
            else:
                bill = self._find_purchase_invoice_for_payment_settlement(
                    source_id=source_id,
                    source_number=source_number,
                )
            if not bill:
                stats["review_count"] += 1
                review_messages.append(
                    "Purchase invoice %s/%s not found for %.2f."
                    % (source_number or "", source_id or "", requested)
                )
                continue
            if bill.state == "draft" and force_post:
                bill.action_post()
            elif bill.state == "draft" and self.auto_post_purchase_bills:
                bill.action_post()
            if bill.state != "posted":
                stats["review_count"] += 1
                review_messages.append(
                    "Purchase invoice %s is not posted for settlement %.2f."
                    % (bill.display_name, requested)
                )
                continue

            result = self._apply_exact_purchase_settlement(debit_note, bill, requested)
            stats["already_reconciled"] += result["already"]
            stats["newly_reconciled"] += result["new"]
            if result["message"]:
                stats["review_count"] += 1
                review_messages.append(
                    "%s: %s" % (source_number or bill.display_name, result["message"])
                )

        if log_result:
            state = "error" if review_messages else "success"
            message = (
                "Purchase return Splendid settlements checked: allocations=%s, newly reconciled=%.2f, "
                "already matched=%.2f."
                % (
                    stats["allocation_count"],
                    stats["newly_reconciled"],
                    stats["already_reconciled"],
                )
            )
            if review_messages:
                message += " Review: " + " | ".join(review_messages)
            self._log(
                "purchase_reconcile",
                state,
                message,
                payload,
                external_id,
                debit_note,
            )
        return stats

    def _create_purchase_return_credit_note(self, payload):
        external_id = self._external_id(payload)
        partner = self._resolve_vendor(payload)
        original_bills = self._get_original_purchase_bills(payload)
        invoice_lines = []
        for line in self._purchase_return_details(payload):
            invoice_lines.append((0, 0, self._vendor_bill_line_vals_from_purchase_line(line, move_type="in_refund")))
        if not invoice_lines:
            raise UserError(_("No purchase return lines found for Splendid purchase return %s") % external_id)

        discount_line = self._purchase_discount_line_cmd(payload)
        if discount_line:
            invoice_lines.append(discount_line)
        tax_line = self._purchase_tax_amount_line_cmd(payload)
        if tax_line:
            invoice_lines.append(tax_line)

        vals = {
            "move_type": "in_refund",
            "partner_id": partner.id,
            "invoice_date": self._parse_date(self._find_value(payload, "date")),
            "journal_id": self._default_purchase_journal().id,
            "invoice_origin": ", ".join(original_bills.mapped("name")) if original_bills else self._find_value(payload, "purchaseInvoiceNumber"),
            "ref": self._find_value(payload, "number", "reference") or external_id,
            "invoice_line_ids": invoice_lines,
            "company_id": self.company_id.id,
            "splendid_purchase_return_id": external_id,
            "splendid_source_model": "purchase_return",
            "splendid_is_imported": True,
        }
        if original_bills and len(original_bills) == 1 and "reversed_entry_id" in self.env["account.move"]._fields:
            vals["reversed_entry_id"] = original_bills.id
        if "splendid_raw_payload" in self.env["account.move"]._fields:
            vals["splendid_raw_payload"] = payload
        debit_note = self.env["account.move"].with_company(self.company_id).sudo().with_context(default_move_type="in_refund").create(vals)
        self._set_mapping("purchase_return", external_id, debit_note, payload, vals["ref"])
        if self.auto_post_purchase_bills and debit_note.state == "draft":
            debit_note.action_post()
        # Exact bill-by-bill settlement is applied by
        # _import_purchase_return_process() using Splendid adjustedAmount values.
        return debit_note

    def _create_purchase_return_transfer(self, payload):
        external_id = self._external_id(payload)
        existing = self._mapped_record("purchase_return_transfer", external_id, "stock.picking")
        if existing:
            return existing
        details = self._purchase_return_details(payload)
        if not details:
            return self.env["stock.picking"]
        warehouse = self._resolve_warehouse(details[0])
        picking_type = warehouse.out_type_id or self.env["stock.picking.type"].with_company(self.company_id).sudo().search([
            ("code", "=", "outgoing"),
            ("company_id", "=", self.company_id.id),
        ], limit=1)
        source_location = warehouse.lot_stock_id
        dest_location = self._vendor_location()
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
            "partner_id": self._resolve_vendor(payload).id,
            "location_id": source_location.id,
            "location_dest_id": dest_location.id,
            "origin": self._find_value(payload, "number") or external_id,
            "scheduled_date": self._parse_datetime(self._find_value(payload, "date")),
            "company_id": self.company_id.id,
            "move_ids": move_cmds,
            "splendid_purchase_return_id": external_id,
            "splendid_source_model": "purchase_return_transfer",
            "splendid_is_imported": True,
        }
        if "splendid_raw_payload" in self.env["stock.picking"]._fields:
            picking_vals["splendid_raw_payload"] = payload
        picking = self.env["stock.picking"].with_company(self.company_id).sudo().create(picking_vals)
        self._set_mapping("purchase_return_transfer", external_id, picking, payload, picking.name)
        if picking.state == "draft":
            picking.action_confirm()
        if self.auto_validate_purchase_return_transfers:
            self._validate_picking(picking)
        return picking

    def _vendor_payment_account_detail(self, payload):
        """Return the single Splendid payment-account detail used by a VendorPayment.

        An Odoo account.payment can only use one journal. If Splendid sends one
        VendorPayment split across different liquidity accounts, do not guess a
        journal; stop that payment for review instead.
        """
        details = [
            line for line in (self._find_value(payload, "vendorPaymentDetails", default=[]) or [])
            if isinstance(line, dict)
            and self._safe_float(self._find_value(line, "amount"), 0.0) > 0.0
        ]
        if not details:
            return {}

        account_keys = []
        for line in details:
            account_id = self._find_value(line, "accountId")
            account_code = self._find_value(self._nested(line, "account"), "code")
            key = str(account_id or account_code or "").strip()
            if key and key not in account_keys:
                account_keys.append(key)
        if len(account_keys) > 1:
            raise UserError(_(
                "Splendid vendor payment %s uses multiple payment accounts (%s). "
                "One Odoo payment cannot safely map to more than one Bank/Cash journal."
            ) % (
                self._find_value(payload, "number") or self._external_id(payload),
                ", ".join(account_keys),
            ))
        return details[0]

    def _payment_journal_type_from_account_payload(self, account, account_payload):
        """Choose Bank vs Cash without falling back to an unrelated cash journal."""
        text = " ".join(str(value or "") for value in (
            self._find_value(account_payload, "name"),
            self._find_value(account_payload, "code"),
            self._find_value(account_payload, "description"),
        )).lower()
        if self._find_value(account_payload, "bankAccount"):
            return "bank"
        if "bank" in text:
            return "bank"
        if any(token in text for token in ("cash", "undeposited", "petty", "cash in hand")):
            return "cash"
        # Splendid payment accounts should resolve to an Odoo liquidity account.
        # When the source does not identify a bank explicitly, cash is the safer
        # journal class; importantly it is still a dedicated journal for THIS
        # exact Splendid account, not the generic configured Cash journal.
        return "cash"

    def _get_or_create_vendor_payment_journal(self, account_id, account, account_payload):
        """Return the exact Odoo Bank/Cash journal for a Splendid payment GL account."""
        self.ensure_one()
        Journal = self.env["account.journal"].with_company(self.company_id).sudo()
        account_id_text = str(account_id or "").strip()

        # 1) Exact Odoo default account. This also reuses journals imported by
        #    Splendid BankAccounts master data.
        journal = Journal.search([
            ("company_id", "=", self.company_id.id),
            ("type", "in", ("bank", "cash")),
            ("default_account_id", "=", account.id),
        ], limit=1)
        if journal:
            vals = {}
            if "splendid_payment_account_id" in Journal._fields and account_id_text:
                if journal.splendid_payment_account_id != account_id_text:
                    vals["splendid_payment_account_id"] = account_id_text
            if vals:
                journal.write(vals)
            return journal

        # 2) Exact Splendid account ID previously attached to a journal.
        if account_id_text and "splendid_payment_account_id" in Journal._fields:
            journal = Journal.search([
                ("company_id", "=", self.company_id.id),
                ("type", "in", ("bank", "cash")),
                ("splendid_payment_account_id", "=", account_id_text),
            ], limit=1)
            if journal:
                if journal.default_account_id != account:
                    journal.write({"default_account_id": account.id})
                return journal

        # 3) Backward compatibility with BankAccounts master mapping.
        if account_id_text:
            journal = Journal.search([
                ("company_id", "=", self.company_id.id),
                ("type", "in", ("bank", "cash")),
                ("splendid_bank_account_account_id", "=", account_id_text),
            ], limit=1)
            if journal:
                vals = {"default_account_id": account.id}
                if "splendid_payment_account_id" in Journal._fields:
                    vals["splendid_payment_account_id"] = account_id_text
                journal.write(vals)
                return journal

        if account.account_type != "asset_cash":
            raise UserError(_(
                "Splendid vendor payment account %s [%s] mapped to Odoo account '%s' "
                "with type '%s', not a Bank and Cash liquidity account. "
                "The payment was not put into the fallback Cash journal."
            ) % (
                account_id_text or "?",
                self._find_value(account_payload, "code") or account.code or "",
                account.display_name,
                account.account_type,
            ))

        journal_type = self._payment_journal_type_from_account_payload(account, account_payload)
        account_name = self._find_value(account_payload, "name") or account.name or account.display_name
        account_code = self._find_value(account_payload, "code") or account.code or account_id_text
        vals = {
            "name": ("Splendid - %s" % account_name)[:100],
            "type": journal_type,
            "code": self._unique_journal_code(account_code or account_name),
            "company_id": self.company_id.id,
            "default_account_id": account.id,
            "splendid_is_imported": True,
        }
        if "splendid_payment_account_id" in Journal._fields:
            vals["splendid_payment_account_id"] = account_id_text
        journal = Journal.create(vals)
        return journal

    def _resolve_journal_for_vendor_payment(self, payload):
        """Map VendorPayment to the exact account from vendorPaymentDetails.

        Previous behaviour fell back to bank_journal_id when an exact journal did
        not exist, causing unrelated Splendid accounts to land in one Cash
        journal. Now accountId/account.code is authoritative and a dedicated
        Bank/Cash journal is reused or created for that exact Odoo liquidity
        account.
        """
        detail = self._vendor_payment_account_detail(payload)
        if not detail:
            # Preserve compatibility only for old payloads that genuinely have no
            # vendorPaymentDetails account information.
            return self._default_bank_journal()

        account_payload = self._nested(detail, "account")
        account_id = self._find_value(detail, "accountId") or self._find_value(account_payload, "id")
        account_code = self._find_value(account_payload, "code")
        if not account_id and not account_code:
            raise UserError(_(
                "Splendid vendor payment %s has vendorPaymentDetails but no accountId/account code. "
                "Journal mapping was not guessed."
            ) % (self._find_value(payload, "number") or self._external_id(payload)))

        account = self._resolve_account(account_id, account_code)
        if not account:
            raise UserError(_(
                "Could not resolve Splendid vendor payment account %s [%s] in Odoo."
            ) % (account_id or "?", account_code or ""))
        return self._get_or_create_vendor_payment_journal(
            account_id=account_id,
            account=account,
            account_payload=account_payload,
        )

    def _prepare_vendor_payment_accounts(self, journal, partner):
        """Return a valid outbound method + payable account for vendor payments.

        Odoo 18 creates the payment journal entry from:
        - payment_method_line_id.payment_account_id -> liquidity/outstanding line
        - partner.property_account_payable_id       -> counterpart line

        The previous integration selected outbound_payment_method_line_ids[0]
        even when that method had no payment_account_id. On this Odoo build that
        produced an account.move.line with account_id=NULL and PostgreSQL raised
        account_move_line_check_accountable_required_fields.
        """
        self.ensure_one()

        methods = journal.outbound_payment_method_line_ids
        if not methods:
            raise UserError(_(
                "Bank/Cash journal '%s' has no outbound payment method. "
                "Configure an outbound Manual payment method before importing vendor payments."
            ) % journal.display_name)

        # Prefer an already-correct method. Manual is preferred when several exist.
        method = methods.filtered(lambda m: m.payment_account_id and m.code == "manual")[:1]
        if not method:
            method = methods.filtered(lambda m: m.payment_account_id)[:1]
        if not method:
            method = methods.filtered(lambda m: m.code == "manual")[:1] or methods[:1]

        # Imported Splendid bank journals already carry default_account_id.
        # If the Manual method has no Outstanding Payments account configured,
        # use that journal account rather than letting Odoo generate account_id=NULL.
        if not method.payment_account_id:
            fallback_payment_account = journal.default_account_id
            if not fallback_payment_account:
                raise UserError(_(
                    "Vendor payment journal '%s' has no Outstanding Payments account "
                    "and no Default Account. Configure one before posting vendor payments."
                ) % journal.display_name)
            method.sudo().write({"payment_account_id": fallback_payment_account.id})

        payable = partner.with_company(self.company_id).property_account_payable_id
        if not payable:
            payable = self.default_payable_account_id or self._default_account("payable")
            if not payable or payable.account_type != "liability_payable":
                raise UserError(_(
                    "Vendor '%s' has no payable account and no valid default payable account is configured."
                ) % partner.display_name)
            partner.with_company(self.company_id).sudo().write({
                "property_account_payable_id": payable.id,
            })

        return method, payable

    def _validate_vendor_payment_accounts(self, payment):
        """Fail with a readable error before Odoo reaches the SQL constraint."""
        payment.invalidate_recordset()
        if not payment.payment_method_line_id:
            raise UserError(_("Vendor payment has no payment method line."))
        if not payment.outstanding_account_id:
            raise UserError(_(
                "Vendor payment method '%s' on journal '%s' has no Outstanding Payments account."
            ) % (payment.payment_method_line_id.display_name, payment.journal_id.display_name))
        if not payment.destination_account_id:
            raise UserError(_(
                "Vendor '%s' has no payable account for company '%s'."
            ) % (payment.partner_id.display_name, payment.company_id.display_name))
        return True

    def _import_vendor_payment_process(self, payload):
        external_id = self._external_id(payload)
        if self._vendor_payment_is_void(payload):
            self._log(
                "vendor_payments",
                "skipped",
                "Splendid vendor payment was not imported because status=50 / void.",
                payload,
                external_id,
            )
            return self.env["account.payment"].with_company(self.company_id).sudo()

        payment = self._mapped_record("vendor_payment", external_id, "account.payment")

        if payment:
            desired_journal = self._resolve_journal_for_vendor_payment(payload)
            state = getattr(payment, "state", False)
            if payment.journal_id != desired_journal and state != "draft":
                raise UserError(_(
                    "Existing Odoo vendor payment %s is already posted in journal '%s', but Splendid account %s maps to '%s'. "
                    "Reset/delete that payment before re-syncing; the integration will not silently move a posted payment between liquidity journals."
                ) % (
                    payment.display_name,
                    payment.journal_id.display_name,
                    self._find_value(self._vendor_payment_account_detail(payload), "accountId") or "?",
                    desired_journal.display_name,
                ))
            if payment.journal_id != desired_journal and state == "draft":
                payment.sudo().write({"journal_id": desired_journal.id})

            method, payable = self._prepare_vendor_payment_accounts(desired_journal, payment.partner_id)
            payment_vals = {}
            if payment.payment_method_line_id != method:
                payment_vals["payment_method_line_id"] = method.id
            if payment.destination_account_id != payable:
                payment_vals["destination_account_id"] = payable.id
            if payment_vals and getattr(payment, "state", False) == "draft":
                payment.sudo().write(payment_vals)
            self._validate_vendor_payment_accounts(payment)
            if self.auto_post_vendor_payments and getattr(payment, "state", False) == "draft":
                payment.action_post()
            if self.auto_reconcile_vendor_payments:
                self._reconcile_vendor_payment(payment, payload)
            return payment

        partner = self._resolve_vendor(payload)
        journal = self._resolve_journal_for_vendor_payment(payload)
        method, payable = self._prepare_vendor_payment_accounts(journal, partner)

        amount = self._safe_float(self._find_value(payload, "totalAmount", "allocatedAmount", "amount"), 0.0)
        if amount <= 0:
            raise UserError(_("Vendor payment %s has no positive amount to import.") % external_id)

        payment_ref = self._find_value(payload, "number", "reference", "comments") or external_id
        vals = {
            "payment_type": "outbound",
            "partner_type": "supplier",
            "partner_id": partner.id,
            "amount": amount,
            "date": self._parse_date(self._find_value(payload, "date")),
            "journal_id": journal.id,
            "company_id": self.company_id.id,
            "payment_reference": payment_ref,
            "payment_method_line_id": method.id,
            "destination_account_id": payable.id,
            "splendid_vendor_payment_id": external_id,
            "splendid_is_imported": True,
        }
        if "splendid_raw_payload" in self.env["account.payment"]._fields:
            vals["splendid_raw_payload"] = payload

        payment = self.env["account.payment"].with_company(self.company_id).sudo().create(vals)
        self._validate_vendor_payment_accounts(payment)

        if self.auto_post_vendor_payments and getattr(payment, "state", False) == "draft":
            payment.action_post()

        # Only map the payment after successful creation/posting. A savepoint in
        # the caller rolls the complete payment back if posting fails.
        self._set_mapping("vendor_payment", external_id, payment, payload, payment_ref)

        if self.auto_reconcile_vendor_payments:
            self._reconcile_vendor_payment(payment, payload)
        return payment

    def _find_purchase_invoice_for_payment_settlement(self, source_id=False, source_number=False):
        Move = self.env["account.move"].with_company(self.company_id).sudo()

        if source_id:
            bill = self._mapped_record("purchase_invoice", source_id, "account.move")
            if bill:
                return bill

            if "splendid_purchase_invoice_id" in Move._fields:
                bill = Move.search([
                    ("company_id", "=", self.company_id.id),
                    ("move_type", "=", "in_invoice"),
                    ("splendid_purchase_invoice_id", "=", str(source_id)),
                ], limit=1)
                if bill:
                    return bill

        if source_number:
            bill = Move.search([
                ("company_id", "=", self.company_id.id),
                ("move_type", "=", "in_invoice"),
                "|",
                "|",
                ("ref", "=", source_number),
                ("name", "=", source_number),
                ("invoice_origin", "=", source_number),
            ], limit=1)
            if bill:
                return bill

        return Move

    def _ensure_purchase_invoice_for_payment_settlement(self, source_id=False, source_number=False):
        self.ensure_one()

        bill = self._find_purchase_invoice_for_payment_settlement(
            source_id=source_id,
            source_number=source_number,
        )
        if bill:
            return bill

        # Agar payment settlement me purchase invoice sourceId hai,
        # lekin woh bill date range / previous sync ki wajah se import nahi hui,
        # to direct PurchaseInvoices/{id} call karke bill create karo.
        if source_id:
            try:
                payload = self._fetch_detail_by_id("/PurchaseInvoices", source_id)
                if self._purchase_invoice_status_is_50(payload):
                    self._log(
                        "purchase_reconcile",
                        "skipped",
                        "Purchase invoice %s was not auto-imported for settlement because Splendid status=50." % source_id,
                        payload,
                        source_id,
                    )
                    return self.env["account.move"].with_company(self.company_id).sudo()
                if payload and self._purchase_invoice_details(payload):
                    bill = self._import_purchase_invoice_process(payload)
                    return bill
            except Exception as exc:  # pylint: disable=broad-except
                self._log(
                    "vendor_payments",
                    "error",
                    "Could not auto-import purchase invoice %s for vendor payment settlement: %s" % (source_id, exc),
                    {"source_id": source_id, "source_number": source_number},
                    source_id,
                )

        return self.env["account.move"].with_company(self.company_id).sudo()

    def _get_vendor_payment_outstanding_lines(self, payment):
        if not payment or not payment.move_id:
            return self.env["account.move.line"]
        return payment.move_id.line_ids.filtered(
            lambda line:
                not line.reconciled
                and line.partner_id == payment.partner_id
                and abs(line.amount_residual) > 0.00001
                and line.debit > 0
        )


    def _reconcile_vendor_payment(self, payment, payload):
        """Reconcile a vendor payment only through Splendid VendorSettlements.

        The account.payment already carries splendid_vendor_payment_id. The
        VendorSettlement detail sourceId is matched to that field, so the payment
        payload itself is not treated as the allocation source of truth.
        """
        if not payment:
            return False
        return self._reconcile_vendor_settlements_referenced_by_payload(
            payload,
            log_missing=False,
        )

   
    def _reconcile_moves(self, moves):
        if not moves:
            return False

        # Normalize accidental Python collections to an Odoo account.move recordset.
        # mapped()/filtered() only exist on Odoo recordsets.
        if isinstance(moves, (list, tuple, set)):
            move_recordset = self.env["account.move"].with_company(self.company_id).sudo()
            for move in moves:
                if getattr(move, "_name", None) == "account.move":
                    move_recordset |= move
            moves = move_recordset
            if not moves:
                return False

        lines = moves.mapped("line_ids").filtered(
            lambda l:
                not l.reconciled
                and l.account_id.account_type in ("asset_receivable", "liability_payable")
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
                    _logger.warning("Could not reconcile Splendid move lines: %s", exc)
        return True



    # -------------------------------------------------------------------------
    # Manufacturing process: Splendid Job Orders -> one BoM + one Odoo MO each
    # -------------------------------------------------------------------------
    def _fetch_job_orders(self):
        """Fetch Job Orders using the same connection date range as Sales/Purchase.

        Splendid exposes both GET /JobOrders and POST /JobOrders/Search.  When a
        date range is configured, Search is used so old Job Orders can be tested
        without pulling the entire history.
        """
        self.ensure_one()
        date_payload = self._date_range_payload()
        if date_payload:
            return self._fetch_search_collection(
                "/JobOrders/Search",
                filter_payload=date_payload,
                params={"orderBy": "Date", "ascending": "true"},
            )
        return self._fetch_collection(
            "/JobOrders",
            params={"orderBy": "Date", "ascending": "true"},
            use_paging=True,
        )

    def _sync_job_orders(self):
        self.ensure_one()

        rows = self._fetch_job_orders()
        # Defensive Odoo-side date filtering in case Splendid returns a wider set.
        rows = self._filter_rows_by_date_range(rows)
        imported = failed = skipped = 0

        if not rows:
            self._log(
                "job_orders",
                "skipped",
                "Splendid returned 0 Job Orders for the current sync range. From Date=%s, To Date=%s." % (
                    self.sync_from_date or "not set",
                    self.sync_to_date or "not set",
                ),
                {
                    "from_date": fields.Date.to_string(self.sync_from_date) if self.sync_from_date else False,
                    "to_date": fields.Date.to_string(self.sync_to_date) if self.sync_to_date else False,
                },
            )

        for row in rows:
            external_id = self._external_id(row)
            try:
                with self.env.cr.savepoint():
                    payload = self._fetch_detail_by_id("/JobOrders", external_id)
                    if not payload:
                        raise UserError(_("Splendid returned no Job Order detail for %s.") % external_id)
                    if self._safe_bool(self._find_value(payload, "isVoid"), False):
                        skipped += 1
                        self._log(
                            "job_orders",
                            "skipped",
                            "Skipped Splendid Job Order because isVoid=true. Existing Odoo MO is not cancelled automatically.",
                            payload,
                            external_id,
                        )
                        continue

                    production = self._import_job_order_process(payload)
                    imported += 1
                    self._log(
                        "job_orders",
                        "success",
                        "Job Order imported as a dedicated BoM and Manufacturing Order. Splendid component cost/totalCost fields were ignored; each mapped jobOrderExpense is represented by a fixed-cost Manufacturing Work Order so Odoo includes it in native Work Center costing.",
                        payload,
                        external_id,
                        production,
                    )
            except Exception as exc:  # pylint: disable=broad-except
                failed += 1
                _logger.exception("Failed to import Splendid Job Order %s", external_id)
                self._log("job_orders", "error", str(exc), row, external_id)

        self._set_count("job_orders", len(rows), imported, failed)
        self.last_manufacturing_sync = fields.Datetime.now()
        self._log(
            "job_orders",
            "success" if not failed else "error",
            "Job Order sync summary: fetched=%s imported=%s skipped=%s failed=%s" % (
                len(rows), imported, skipped, failed,
            ),
            {"fetched": len(rows), "imported": imported, "skipped": skipped, "failed": failed},
        )
        self.env.cr.commit()
        return True

    def _job_order_details(self, payload):
        details = self._find_value(payload, "jobOrderDetails", "details", default=[]) or []
        return details if isinstance(details, list) else []

    def _job_order_parent_line(self, payload):
        for line in self._job_order_details(payload):
            if not isinstance(line, dict):
                continue
            if self._safe_bool(self._find_value(line, "isParent"), False):
                return line
        return {}

    def _job_order_component_lines(self, payload):
        """Only Splendid input lines become BoM components.

        The parent/output line is deliberately excluded. Splendid component line cost,
        totalCost and costPercentage are deliberately ignored; only product, quantity,
        UoM and warehouse are used. Job Order expenses are handled separately as
        fixed-cost Manufacturing Work Orders on this Job Order's dedicated BoM.
        """
        result = []
        for line in self._job_order_details(payload):
            if not isinstance(line, dict):
                continue
            if self._safe_bool(self._find_value(line, "isParent"), False):
                continue
            if not self._safe_bool(self._find_value(line, "isInput"), False):
                continue
            qty = self._safe_float(self._find_value(line, "quantity"), 0.0)
            if qty <= 0:
                continue
            result.append(line)
        return result

    def _resolve_job_order_product(self, product_id=False, nested=None):
        line = {"productId": product_id, "product": nested or {}}
        return self._resolve_product_from_line(line)

    def _job_order_finished_product(self, payload):
        external_id = self._find_value(payload, "assemblyProductId")
        nested = self._nested(payload, "assemblyProduct")
        product_tmpl = self._resolve_job_order_product(external_id, nested)
        product = product_tmpl.product_variant_id or product_tmpl.product_variant_ids[:1]
        if not product:
            raise UserError(_("Finished product could not be resolved for Splendid Job Order %s.") % self._external_id(payload))
        return product_tmpl, product

    def _mrp_picking_type_for_warehouse(self, warehouse):
        PickingType = self.env["stock.picking.type"].with_company(self.company_id).sudo()
        domain = [
            ("company_id", "=", self.company_id.id),
            ("code", "=", "mrp_operation"),
        ]
        if warehouse and "warehouse_id" in PickingType._fields:
            picking_type = PickingType.search(domain + [("warehouse_id", "=", warehouse.id)], limit=1)
            if picking_type:
                return picking_type
        return PickingType.search(domain, limit=1)

    def _job_order_source_warehouse(self, payload):
        return self._resolve_warehouse(payload)

    def _job_order_destination_warehouse(self, payload, source_warehouse):
        parent_line = self._job_order_parent_line(payload)
        if parent_line:
            warehouse_id = self._find_value(parent_line, "warehouseId", "warehouseID")
            if warehouse_id:
                return self._resolve_warehouse(parent_line, warehouse_id=warehouse_id)
        return source_warehouse

    def _find_existing_job_order_bom(self, external_id):
        bom = self._mapped_record("job_order_bom", external_id, "mrp.bom")
        if bom:
            return bom
        Bom = self.env["mrp.bom"].with_company(self.company_id).sudo()
        if "splendid_job_order_id" in Bom._fields:
            bom = Bom.search([
                ("company_id", "=", self.company_id.id),
                ("splendid_job_order_id", "=", str(external_id)),
            ], limit=1)
            if bom:
                self._set_mapping("job_order_bom", external_id, bom, external_name=bom.code)
        return bom

    def _find_existing_job_order_mo(self, external_id):
        production = self._mapped_record("job_order", external_id, "mrp.production")
        if production:
            return production
        Production = self.env["mrp.production"].with_company(self.company_id).sudo()
        if "splendid_job_order_id" in Production._fields:
            production = Production.search([
                ("company_id", "=", self.company_id.id),
                ("splendid_job_order_id", "=", str(external_id)),
            ], limit=1)
            if production:
                self._set_mapping("job_order", external_id, production, external_name=production.origin or production.name)
        return production

    def _job_order_bom_line_commands(self, payload):
        commands = []
        for line in self._job_order_component_lines(payload):
            product_tmpl = self._resolve_product_from_line(line)
            product = product_tmpl.product_variant_id or product_tmpl.product_variant_ids[:1]
            if not product:
                raise UserError(_("Component product is missing for Job Order detail %s.") % (self._find_value(line, "id") or ""))
            qty = self._safe_float(self._find_value(line, "quantity"), 0.0)
            vals = {
                "product_id": product.id,
                "product_qty": qty,
                "product_uom_id": product.uom_id.id,
            }
            if "splendid_job_order_detail_id" in self.env["mrp.bom.line"]._fields:
                vals["splendid_job_order_detail_id"] = str(self._find_value(line, "id") or "")
            if "splendid_warehouse_id" in self.env["mrp.bom.line"]._fields:
                vals["splendid_warehouse_id"] = str(self._find_value(line, "warehouseId", "warehouseID") or "")
            commands.append((0, 0, vals))
        if not commands:
            raise UserError(_("No input component lines were found in Splendid Job Order %s.") % self._external_id(payload))
        return commands

    def _get_or_create_job_order_bom(self, payload, finished_tmpl, finished_product, source_warehouse):
        external_id = self._external_id(payload)
        number = self._find_value(payload, "number", "reference") or str(external_id)
        bom = self._find_existing_job_order_bom(external_id)
        production = self._find_existing_job_order_mo(external_id)
        picking_type = self._mrp_picking_type_for_warehouse(source_warehouse)
        qty = self._safe_float(self._find_value(payload, "quantityToProduce"), 0.0)
        if qty <= 0:
            raise UserError(_("Splendid Job Order %s has quantityToProduce <= 0.") % number)

        vals = {
            "product_tmpl_id": finished_tmpl.id,
            "product_id": finished_product.id,
            # The BoM quantity equals this Job Order's planned production quantity,
            # so Splendid component quantities remain exact, without normalizing.
            "product_qty": qty,
            "product_uom_id": finished_product.uom_id.id,
            "code": str(number),
            "type": "normal",
            "company_id": self.company_id.id,
            "splendid_job_order_id": str(external_id),
            "splendid_job_order_number": str(number),
            "splendid_is_imported": True,
        }
        if picking_type:
            vals["picking_type_id"] = picking_type.id

        # A Job Order owns its BoM. Update it only while no Odoo MO has started;
        # otherwise changing components underneath a running MO would be unsafe.
        if bom:
            if not production or production.state == "draft":
                vals["bom_line_ids"] = [(5, 0, 0)] + self._job_order_bom_line_commands(payload)
                bom.write(vals)
                self._sync_job_order_expense_operations(bom, payload, production=production)
            self._set_mapping("job_order_bom", external_id, bom, payload, number)
            return bom

        vals["bom_line_ids"] = self._job_order_bom_line_commands(payload)
        bom = self.env["mrp.bom"].with_company(self.company_id).sudo().create(vals)
        self._sync_job_order_expense_operations(bom, payload)
        self._set_mapping("job_order_bom", external_id, bom, payload, number)
        return bom

    def _apply_job_order_component_locations(self, production, payload):
        """Honor per-line Splendid warehouse where possible.

        Odoo's MO has a default component source location, but Splendid can specify
        a different warehouse on each input line.  Before confirmation, update the
        generated raw stock moves using the warehouse ID stored on the matching BoM
        line. This affects stock reservation/location only; it does not import any
        Splendid cost values.
        """
        if not production or production.state != "draft":
            return True
        detail_by_warehouse = {}
        for line in self._job_order_component_lines(payload):
            warehouse_id = self._find_value(line, "warehouseId", "warehouseID")
            if warehouse_id:
                detail_by_warehouse[str(warehouse_id)] = line
        for move in production.move_raw_ids:
            bom_line = move.bom_line_id
            warehouse_id = getattr(bom_line, "splendid_warehouse_id", False) if bom_line else False
            if not warehouse_id:
                continue
            source_line = detail_by_warehouse.get(str(warehouse_id), {})
            warehouse = self._resolve_warehouse(source_line, warehouse_id=warehouse_id)
            if warehouse and warehouse.lot_stock_id and move.location_id != warehouse.lot_stock_id:
                move.write({"location_id": warehouse.lot_stock_id.id})
        return True

    def _job_order_expense_lines(self, payload):
        expenses = self._find_value(payload, "jobOrderExpenses", default=[]) or []
        return [line for line in expenses if isinstance(line, dict)] if isinstance(expenses, list) else []

    def _job_order_expense_total_from_payload(self, payload):
        return sum(
            self._safe_float(self._find_value(line, "amount"), 0.0)
            for line in self._job_order_expense_lines(payload)
        )

    def _job_order_expense_external_id(self, line, index=0):
        value = self._find_value(line, "id", "expenseId", "jobOrderExpenseId")
        if value not in (False, None, ""):
            return str(value)
        stable = {
            "index": index,
            "accountId": self._find_value(line, "accountId"),
            "contactId": self._find_value(line, "contactId"),
            "description": self._find_value(line, "description"),
            "amount": self._safe_float(self._find_value(line, "amount"), 0.0),
        }
        digest = hashlib.sha1(json.dumps(stable, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]
        return "AUTO-%s" % digest

    def _resolve_job_order_expense_account(self, line):
        account_id = self._find_value(line, "accountId")
        account_payload = self._nested(line, "account")
        account_code = self._find_value(account_payload, "code")
        account = self._resolve_account(account_id, account_code)
        if not account and account_payload:
            try:
                account = self._import_chart_accounts(account_payload)
            except Exception as exc:  # pylint: disable=broad-except
                _logger.warning("Could not import Splendid Job Order expense account %s: %s", account_id, exc)
        return account

    def _job_order_expense_workcenter(self, account):
        """Return one technical Work Center per mapped Splendid expense account.

        The Work Center's standard ``expense_account_id`` is the Splendid account.
        The monetary amount itself is stored on the Job Order operation/work order,
        not in ``costs_hour``; this lets many Job Orders reuse the same Work Center
        without changing historical costs.
        """
        self.ensure_one()
        if not account:
            return self.env["mrp.workcenter"]

        Workcenter = self.env["mrp.workcenter"].with_company(self.company_id).sudo().with_context(active_test=False)
        workcenter = Workcenter.search([
            ("company_id", "=", self.company_id.id),
            ("splendid_is_external_cost_center", "=", True),
            ("expense_account_id", "=", account.id),
        ], limit=1)

        account_label = account.code or account.name or str(account.id)
        vals = {
            "name": "Splendid External Cost - %s" % account_label,
            "company_id": self.company_id.id,
            "splendid_is_external_cost_center": True,
            "expense_account_id": account.id,
            # Cost is fixed on each Work Order; hourly rate is intentionally 0.
            "costs_hour": 0.0,
            "time_start": 0.0,
            "time_stop": 0.0,
            "default_capacity": 1.0,
            "active": True,
        }
        if workcenter:
            update_vals = {key: value for key, value in vals.items() if workcenter[key] != value}
            if update_vals:
                workcenter.write(update_vals)
            return workcenter
        return Workcenter.create(vals)

    def _sync_job_order_expense_operations(self, bom, payload, production=False):
        """Create/update one fixed-cost BoM operation per Splendid Job Order expense.

        Because every Splendid Job Order owns a dedicated BoM, these operations
        generate dedicated Work Orders on the corresponding MO.  Odoo's native
        ``mrp_account`` finished-product valuation calls ``mrp.workorder._cal_cost``;
        our Work Order extension returns the exact Splendid expense amount.

        Existing non-draft MOs are never structurally changed.
        """
        self.ensure_one()
        Operation = self.env["mrp.routing.workcenter"].with_company(self.company_id).sudo().with_context(active_test=False)
        Expense = self.env["splendid.job.order.expense"].with_company(self.company_id).sudo()
        external_job_id = str(self._external_id(payload) or "")
        number = str(self._find_value(payload, "number", "reference") or external_job_id)

        existing_ops = Operation.search([
            ("bom_id", "=", bom.id),
            ("splendid_is_external_cost", "=", True),
        ])
        if production and production.state != "draft":
            # A confirmed/running/done MO already owns its Work Orders. Rebuilding
            # routing underneath it would change manufacturing costing unexpectedly.
            return existing_ops.filtered("active")

        existing_by_id = {op.splendid_job_expense_id: op for op in existing_ops if op.splendid_job_expense_id}
        seen_ids = set()
        result = Operation

        for index, line in enumerate(self._job_order_expense_lines(payload)):
            amount = self._safe_float(self._find_value(line, "amount"), 0.0)
            if abs(amount) <= 0.000001:
                continue
            expense_id = self._job_order_expense_external_id(line, index=index)
            seen_ids.add(expense_id)
            old_operation = existing_by_id.get(expense_id)

            # Never create a Work Order cost on top of accounting already posted by
            # an older module version. That would capitalize the same expense twice.
            legacy_expense = Expense.search([
                ("connection_id", "=", self.id),
                ("splendid_job_order_id", "=", external_job_id),
                ("splendid_expense_id", "=", expense_id),
            ], limit=1)
            legacy_posted = bool(
                legacy_expense and (
                    (legacy_expense.journal_entry_id and legacy_expense.journal_entry_id.state == "posted")
                    or (legacy_expense.vendor_bill_id and legacy_expense.vendor_bill_id.state == "posted")
                )
            )
            if legacy_posted:
                if old_operation:
                    if production:
                        production.workorder_ids.filtered(lambda wo: wo.operation_id == old_operation).unlink()
                    old_operation.unlink()
                self._log(
                    "job_order_expenses",
                    "error",
                    "Splendid Job Order expense %s was not converted to a Work Order because a legacy posted Journal Entry/Vendor Bill already exists. Reverse/review the legacy accounting before migrating this expense to Work Order costing." % expense_id,
                    line, expense_id, legacy_expense.journal_entry_id or legacy_expense.vendor_bill_id,
                )
                continue

            account = self._resolve_job_order_expense_account(line)
            if not account:
                if old_operation:
                    if production:
                        production.workorder_ids.filtered(lambda wo: wo.operation_id == old_operation).unlink()
                    old_operation.unlink()
                self._log(
                    "job_order_expenses",
                    "error",
                    "Splendid Job Order expense %s could not create a Work Order because its expense account is not mapped in Odoo. No account was guessed." % expense_id,
                    line, expense_id, bom,
                )
                continue

            workcenter = self._job_order_expense_workcenter(account)
            description = self._find_value(line, "description") or account.display_name or _("Splendid External Job Cost")
            vals = {
                "name": str(description),
                "bom_id": bom.id,
                "workcenter_id": workcenter.id,
                "sequence": 900 + index,
                "time_mode": "manual",
                # One nominal minute is used only so Odoo can schedule/display the Work Order.
                # It has ZERO impact on cost: _cal_cost() returns the fixed payload amount.
                "time_cycle_manual": 1.0,
                "active": True,
                "splendid_is_external_cost": True,
                "splendid_job_expense_id": expense_id,
                "splendid_external_cost": amount,
                "splendid_expense_account_id": account.id,
                "note": "Splendid Job Order %s / Expense %s. Fixed Work Order cost: %s %s. Duration is nominal and does not drive the cost." % (
                    number, expense_id, amount, self.company_id.currency_id.name or "",
                ),
            }
            if old_operation:
                old_operation.write(vals)
                operation = old_operation
            else:
                operation = Operation.create(vals)
            result |= operation

        stale_ops = existing_ops.filtered(lambda op: op.splendid_job_expense_id not in seen_ids)
        if stale_ops:
            if production:
                production.workorder_ids.filtered(lambda wo: wo.operation_id in stale_ops).unlink()
            stale_ops.unlink()
        return result

    def _resolve_job_order_expense_vendor(self, line, account=False):
        """Resolve the vendor conservatively.

        Priority:
        1) Splendid contactId -> existing/mapped Vendor (or GET /Vendors/{id})
        2) saved account.splendid_job_expense_vendor_id mapping
        3) exact unique Odoo vendor-name match using the Splendid account name,
           with a trailing parenthetical description removed (e.g. "M. Bros
           (Finished Goods Packaging)" -> exact vendor "M. Bros").

        No fuzzy matching is used.
        """
        Partner = self.env["res.partner"].with_company(self.company_id).sudo()
        contact_id = self._find_value(line, "contactId")
        if contact_id:
            vendor = self._mapped_record("vendor", contact_id, "res.partner")
            if not vendor and "splendid_vendor_id" in Partner._fields:
                candidates = Partner.search([
                    ("splendid_vendor_id", "=", str(contact_id)),
                ], limit=10)
                vendor = candidates.filtered(
                    lambda p: not p.company_id or p.company_id == self.company_id
                )[:1]
            if not vendor:
                nested_contact = self._nested(line, "contact")
                if nested_contact:
                    try:
                        vendor = self._import_vendors(nested_contact)
                    except Exception:  # pylint: disable=broad-except
                        vendor = Partner
            if not vendor:
                try:
                    vendor_payload = self._fetch_detail_by_id("/Vendors", contact_id)
                    if vendor_payload:
                        vendor = self._import_vendors(vendor_payload)
                except Exception as exc:  # pylint: disable=broad-except
                    _logger.warning("Could not resolve Splendid Job Order expense contactId %s as vendor: %s", contact_id, exc)
            if vendor:
                return vendor

        if account and "splendid_job_expense_vendor_id" in account._fields and account.splendid_job_expense_vendor_id:
            return account.splendid_job_expense_vendor_id

        account_payload = self._nested(line, "account")
        account_name = self._find_value(account_payload, "name") or (account.name if account else False)
        if account_name:
            candidate = re.sub(r"\s*\([^)]*\)\s*$", "", str(account_name)).strip()
            if candidate:
                vendors = Partner.search([
                    ("supplier_rank", ">", 0),
                    ("name", "=ilike", candidate),
                ], limit=10).filtered(
                    lambda p: not p.company_id or p.company_id == self.company_id
                )
                if len(vendors) == 1:
                    vendor = vendors[0]
                    if account and "splendid_job_expense_vendor_id" in account._fields and not account.splendid_job_expense_vendor_id:
                        account.splendid_job_expense_vendor_id = vendor.id
                    return vendor
        return Partner

    def _create_job_order_expense_entry(self, expense):
        """Deprecated compatibility stub: v30 creates no separate expense JE."""
        expense.sudo().write({
            "accounting_state": "not_required",
            "review_note": "Separate Job Order expense Journal Entries are disabled. Cost is handled through the linked Manufacturing Work Order.",
        })
        return self.env["account.move"]

    def _create_job_order_expense_bill(self, expense):
        """Deprecated compatibility stub: v30 creates no Vendor Bill here."""
        return self._create_job_order_expense_entry(expense)

    def _sync_job_order_expenses(self, production, payload):
        self.ensure_one()
        Expense = self.env["splendid.job.order.expense"].with_company(self.company_id).sudo()
        Operation = self.env["mrp.routing.workcenter"].with_company(self.company_id).sudo().with_context(active_test=False)
        Workorder = self.env["mrp.workorder"].with_company(self.company_id).sudo()
        external_job_id = str(self._external_id(payload) or "")
        number = str(self._find_value(payload, "number", "reference") or external_job_id)
        records = Expense
        seen_ids = set()

        # v27/v28 stored these expenses in mrp.production.extra_cost. v30 uses
        # exact fixed-cost Work Orders instead. Clear only open Splendid MOs so new valuation cannot
        # double count both Extra Unit Cost and Work Order cost. Done/Cancelled MOs
        # are historical and are never revalued automatically.
        if "extra_cost" in production._fields and production.state not in ("done", "cancel") and abs(production.extra_cost or 0.0) > 0.000001:
            production.write({"extra_cost": 0.0})

        # For an existing Draft MO, operations may just have been added to its
        # dedicated BoM. Recompute native Work Orders before linking audit rows.
        if production.state == "draft" and production.bom_id:
            production._compute_workorder_ids()

        for index, line in enumerate(self._job_order_expense_lines(payload)):
            amount = self._safe_float(self._find_value(line, "amount"), 0.0)
            if abs(amount) <= 0.000001:
                continue
            expense_id = self._job_order_expense_external_id(line, index=index)
            seen_ids.add(expense_id)
            account = self._resolve_job_order_expense_account(line)
            operation = Operation.search([
                ("bom_id", "=", production.bom_id.id),
                ("splendid_is_external_cost", "=", True),
                ("splendid_job_expense_id", "=", expense_id),
                ("active", "=", True),
            ], limit=1) if production.bom_id else Operation
            workorder = Workorder.search([
                ("production_id", "=", production.id),
                ("operation_id", "=", operation.id),
            ], limit=1) if operation else Workorder

            existing = Expense.search([
                ("connection_id", "=", self.id),
                ("splendid_job_order_id", "=", external_job_id),
                ("splendid_expense_id", "=", expense_id),
            ], limit=1)

            if not account:
                review_note = "Splendid Job Order expense account could not be resolved in Odoo; no Work Order cost was created."
            elif not operation:
                if production.state in ("done", "cancel"):
                    review_note = "MO is already Done/Cancelled. This expense was not migrated to Work Order costing because historical valuation is not changed automatically."
                elif existing and ((existing.journal_entry_id and existing.journal_entry_id.state == "posted") or (existing.vendor_bill_id and existing.vendor_bill_id.state == "posted")):
                    review_note = "Legacy posted accounting exists for this expense, so Work Order costing was intentionally not added to avoid duplicate capitalization."
                else:
                    review_note = "Splendid fixed-cost operation/work order is missing; review the dedicated Job Order BoM."
            else:
                review_note = False

            vals = {
                "connection_id": self.id,
                "production_id": production.id,
                "splendid_job_order_id": external_job_id,
                "splendid_job_order_number": number,
                "splendid_expense_id": expense_id,
                "splendid_account_id": str(self._find_value(line, "accountId") or ""),
                "splendid_contact_id": str(self._find_value(line, "contactId") or ""),
                "account_id": account.id if account else False,
                "description": self._find_value(line, "description") or (account.display_name if account else _("Splendid Job Order Expense")),
                "amount": amount,
                "is_current": True,
                "splendid_raw_payload": line,
                "operation_id": operation.id if operation else False,
                "workorder_id": workorder.id if workorder else False,
                "accounting_state": "not_required" if operation else "review",
                "review_note": review_note,
            }

            if existing:
                protected = (
                    (existing.journal_entry_id and existing.journal_entry_id.state == "posted")
                    or (existing.vendor_bill_id and existing.vendor_bill_id.state == "posted")
                )
                if protected:
                    # Historical posted accounting is immutable. Keep the audit link
                    # but do not rewrite amount/account/status behind that entry.
                    for key in ("amount", "account_id", "accounting_state"):
                        vals.pop(key, None)
                existing.write(vals)
                expense = existing
            else:
                expense = Expense.create(vals)
            records |= expense

        # Retain removed expenses for audit. Draft Work Order structures are
        # removed by _sync_job_order_expense_operations; posted history is never
        # reversed or deleted automatically.
        stale = Expense.search([
            ("connection_id", "=", self.id),
            ("splendid_job_order_id", "=", external_job_id),
            ("splendid_expense_id", "not in", list(seen_ids) or ["__none__"]),
        ])
        for expense in stale:
            expense.write({
                "is_current": False,
                "operation_id": False,
                "workorder_id": False,
                "accounting_state": "review",
                "review_note": "Expense is no longer present in the latest Splendid Job Order payload; retained for audit. Existing posted accounting/valuation was not reversed automatically.",
            })

        return records

    def _import_job_order_process(self, payload):
        external_id = self._external_id(payload)
        number = self._find_value(payload, "number", "reference") or str(external_id)
        existing = self._find_existing_job_order_mo(external_id)
        if existing:
            # Keep the external metadata fresh, but never overwrite Odoo's actual
            # consumed quantities, produced quantities, valuation or MO state.
            metadata = {
                "splendid_job_order_number": str(number),
                "splendid_job_order_status": int(self._safe_float(self._find_value(payload, "status"), 0.0)),
                "splendid_actual_quantity_produced": self._safe_float(self._find_value(payload, "actualQuantityProduced"), 0.0),
                "splendid_raw_payload": payload,
                "splendid_is_imported": True,
            }
            existing.write(metadata)
            self._set_mapping("job_order", external_id, existing, payload, number)
            self._sync_job_order_expenses(existing, payload)
            return existing

        finished_tmpl, finished_product = self._job_order_finished_product(payload)
        source_warehouse = self._job_order_source_warehouse(payload)
        dest_warehouse = self._job_order_destination_warehouse(payload, source_warehouse)
        bom = self._get_or_create_job_order_bom(
            payload,
            finished_tmpl,
            finished_product,
            source_warehouse,
        )
        qty = self._safe_float(self._find_value(payload, "quantityToProduce"), 0.0)
        if qty <= 0:
            raise UserError(_("Splendid Job Order %s has quantityToProduce <= 0.") % number)
        if not source_warehouse.lot_stock_id:
            raise UserError(_("Source warehouse %s has no stock location.") % source_warehouse.display_name)
        if not dest_warehouse.lot_stock_id:
            raise UserError(_("Destination warehouse %s has no stock location.") % dest_warehouse.display_name)

        picking_type = bom.picking_type_id or self._mrp_picking_type_for_warehouse(source_warehouse)
        if not picking_type:
            raise UserError(_(
                "No Manufacturing operation type was found for warehouse %s. Install/configure Odoo Manufacturing for this warehouse."
            ) % source_warehouse.display_name)

        vals = {
            "product_id": finished_product.id,
            "product_qty": qty,
            "product_uom_id": finished_product.uom_id.id,
            "bom_id": bom.id,
            "picking_type_id": picking_type.id,
            "origin": str(number),
            "date_start": self._parse_datetime(self._find_value(payload, "date")) or fields.Datetime.now(),
            "location_src_id": source_warehouse.lot_stock_id.id,
            "location_dest_id": dest_warehouse.lot_stock_id.id,
            "company_id": self.company_id.id,
            "splendid_job_order_id": str(external_id),
            "splendid_job_order_number": str(number),
            "splendid_job_order_status": int(self._safe_float(self._find_value(payload, "status"), 0.0)),
            "splendid_actual_quantity_produced": self._safe_float(self._find_value(payload, "actualQuantityProduced"), 0.0),
            "splendid_is_imported": True,
            "splendid_raw_payload": payload,
        }

        due_date = self._parse_datetime(self._find_value(payload, "dueDate"))
        if due_date and "date_deadline" in self.env["mrp.production"]._fields:
            vals["date_deadline"] = due_date

        production = self.env["mrp.production"].with_company(self.company_id).sudo().create(vals)
        self._set_mapping("job_order", external_id, production, payload, number)
        self._apply_job_order_component_locations(production, payload)
        self._sync_job_order_expenses(production, payload)

        if self.auto_confirm_job_orders and production.state == "draft":
            production.action_confirm()
        return production
