
## Customer Payment bankName fallback (18.0.5.24.0)
- When `customerPaymentDetails` / `customerRefundDetails` have no `accountId` or account code, the integration now reads `bankName` from the payment line or nested instrument.
- If all positive instrument lines name one bank (for example `BAHL`), it uses the unique Odoo **Bank** journal linked to that `res.bank`. Exact journal name/code and a unique `BANK - ...` name are compatibility fallbacks.
- If multiple banks or multiple journals for the same bank are found, sync stops for review instead of guessing.
- The existing exact accountId/account-code mapping remains higher priority whenever Splendid supplies it.

# Splendid Accounts Sync

Master-data-only Odoo 18 integration for Splendid Accounts.

Included sync:
- Chart of Accounts
- Customers
- Vendors
- Products
- Warehouses
- Bank Accounts
- Taxes

The previous transaction, inventory, manufacturing, sale and purchase sync buttons have been removed from the UI. This version stores Splendid external IDs on imported Odoo records and keeps a mapping table for later transaction integration.


## Manufacturing / Job Orders

- Splendid Job Orders are fetched from `/JobOrders` or `/JobOrders/Search` and then refreshed by `/JobOrders/{id}`.
- Each Job Order creates its own dedicated Odoo BoM and Manufacturing Order.
- Only input lines become BoM components; the parent line is the finished product.
- Splendid Job Order `cost`, `totalCost`, component line costs, and `jobOrderExpenses` are not imported into Odoo manufacturing valuation. Odoo computes MO cost from Odoo component and work-center costs.
- Per-line Splendid warehouses are applied to draft raw material moves where possible.

- Imported Manufacturing Orders are created in Draft by default. Enable **Confirm Manufacturing Orders** on the Splendid connection only when automatic confirmation/reservation is desired.


## Customer Settlements (18.0.5.23.0)
- Adds a separate **Reconcile Customer Settlements** action, parallel to VendorSettlements.
- Uses `CustomerSettlements` / `CustomerSettlements/Search` only to discover settlement IDs, then refreshes every allocation with `GET /CustomerSettlements/{id}`.
- `customerSettlementDetails.accountSide`, `source`, `sourceId`, `number`, and `adjustedAmount` are the source of truth. Top-level `sourceId=0` is ignored.
- Supports exact reconciliation for CustomerPayment, SaleInvoice, CustomerRefund, and SaleReturn/CreditNote sources.
- Reconciliation is exact and idempotent: existing pair partials are counted first, then only the remaining Splendid amount is reconciled. No write-off and no destructive unreconcile.
- Status 50 / void CustomerSettlements and void/status-50 CustomerPayments/CustomerRefunds are skipped for review.
- Generic `js_assign_outstanding_line()` customer-payment settlement logic is no longer used. Customer payments now reconcile only through authoritative CustomerSettlement IDs; use the separate bulk action for historical settlements.


## 18.0.5.25.0 - Splendid cheque payment mode

When a Customer Payment/Refund has positive payment details with `paymentMode = 20` and Splendid does not provide an exact `accountId`/account code, the sync no longer tries to choose between multiple journals of the same bank (for example BAHL - Amin Tea Store vs BAHL - Petty Cash). It creates/reuses one company-specific **Cheque** Bank journal backed by a dedicated **Cheques in Hand** `asset_cash` account and routes the Odoo payment through that journal. Exact Splendid account mapping still has priority whenever `accountId`/account code is present. Mixed payment modes do not use the cheque fallback.

## v18.0.5.27.0 - Manufacturing cost timing (superseded by v18.0.5.29.0)

- Splendid `jobOrderExpenses` remain loaded into Odoo `mrp.production.extra_cost` as a per-unit amount.
- Odoo `mrp_account` includes that Extra Unit Cost in the finished-product manufacturing valuation together with consumed components and Work Center cost.
- Automatic Job Order expense Journal Entries are no longer created during API sync. They are created from the MO completion accounting hook (`_post_labour`) so the WIP capitalization entry is posted at the same manufacturing event as Work Center accounting.
- Existing posted legacy Job Order expense entries/bills are preserved and never duplicated. Existing draft Job Order expense entries can be posted on MO completion when the posting option is enabled.
- No Vendor Bill or Vendor is required for the Job Order expense entry.



## v18.0.5.29.0 - Splendid Job Expenses as Work Orders

- Removed the custom Job Order expense Journal Entry creation flow.
- Removed jobOrderExpenses from `mrp.production.extra_cost` for open/new Splendid MOs.
- Each mapped Splendid `jobOrderExpenses` line now creates one fixed-cost BoM operation and one Manufacturing Work Order.
- Odoo native `mrp_account` reads the Work Order cost when valuing the finished product.
- A technical Work Center is reused per mapped Splendid expense account so Odoo's standard Work Center accounting uses the correct expense account.
- Normal Odoo Work Orders remain unchanged.
- Legacy posted Job Order Journal Entries/Vendor Bills are never duplicated or silently reversed.


## v18.0.5.30.0 - Exact fixed-cost Work Order costing

- Splendid Job Order expenses use a fixed Work Order cost, never duration x hourly rate.
- Standard Odoo Work Orders keep native per-hour costing.
- Splendid external Work Centers remain at 0 hourly cost; the payload amount is stored on the dedicated operation/work order.
- Expected, current and theoretical operation costs return the exact fixed amount.
- Odoo manufacturing finished-product valuation receives the fixed amount through `mrp.workorder._cal_cost()`.
- Analytic distribution for Splendid fixed-cost Work Orders uses the exact fixed amount instead of zero/hourly cost.
- Work Order form/list now visibly show the fixed Splendid cost.
- No separate custom Job Order expense Journal Entry is created.

## 18.0.5.31.0 - Fixed-cost Work Orders in MO Overview
- Odoo 18 finished MO Overview normally calculates operation Real Cost as hours × Work Center hourly cost.
- Splendid external-cost Work Orders now show their exact fixed payload amount as Real Cost in the Overview.
- Total Cost of Operations and per-unit Real Cost now include Splendid fixed Work Order costs.
- Normal Odoo Work Orders keep standard duration × hourly-rate costing.

## v18.0.5.32.0 - Splendid JournalEntries Migration
- Added bulk JournalEntries migration using `/JournalEntries` and `/JournalEntries/Search`.
- Every list row is refetched with `GET /JournalEntries/{id}` before import.
- Added one-by-one Journal Entry ID import for controlled testing/migration.
- Exact `journalEntryDetails.accountId` / account code mapping only; missing accounts are fetched from Splendid Accounts and no fallback GL account is guessed.
- Balanced-entry validation before Odoo `account.move` creation.
- Void source entries are skipped; posted Odoo entries are never silently rewritten.
- General journal `Splendid Journal Entries` is created/reused when no journal is configured.
- Posting is optional and disabled by default for migration review.


## v18.0.5.33.0 - JournalEntries base GET discovery + ID refresh
- Journal migration now always discovers rows from `GET /JournalEntries` with paging.
- `/JournalEntries/Search` is no longer used by the JournalEntries migration flow.
- Every discovered summary row is then refreshed from `GET /JournalEntries/{id}` before account, debit, credit, contact, status, or posting data is imported.
- Connection From/To Date controls are preserved by filtering the base-list summary dates locally; accounting still comes only from the ID-detail payload.
- This matches the intended Sale/Purchase-style two-step migration pattern: collection -> ID GET -> Odoo import.


## 18.0.5.34.0
- JournalEntries with Splendid `status = 30` are excluded from migration.
- During bulk sync, status 30 is checked on the base `GET /JournalEntries` row **before** calling `GET /JournalEntries/{id}`, so no ID-detail GET is performed for those rows.
- The ID-detail payload is defensively checked again before import.
- Manual single-ID import also skips status 30 after fetching the requested record.


## v18.0.5.35.0 - Splendid Expenses migration
- GET `/Expenses` first for discovery, then GET `/Expenses/{id}` for authoritative accounting data.
- Status `30` and void rows are skipped before the ID-detail GET; detail is checked again defensively.
- Each `expenseDetails` account is debited using exact Splendid account mapping; the top-level Expense account is credited for `netAmount`.
- Tax-bearing lines use the exact Splendid purchase/input tax account when source tax arithmetic is unambiguous; otherwise the record is stopped for review.
- No fallback balancing/write-off account is invented. Posted Odoo entries are never silently rewritten.


## v18.0.5.36.0 - Anglo-Saxon Splendid Vendor Bill stock account fix
- Storable products with Automated / real-time valuation no longer force Splendid expense/inventory account IDs onto Vendor Bill lines when Anglo-Saxon accounting is enabled.
- Odoo native `account.move.line._compute_account_id()` now selects Product Category Stock Input (Interim Received) for eligible purchase bill lines.
- Added explicit server action **Repair Splendid Vendor Bill Stock Accounts** for selected draft imported Splendid Vendor Bills.
- The repair does not alter posted bills automatically and does not change service/freight/non-stock expense lines.


## v18.0.5.37.0 - Auto-repair Splendid Vendor Bill stock account on post
- Fixes older imported draft Vendor Bills that still carry COGS/expense accounts on storable real-time-valued product lines.
- The repair now resolves the exact Product Category Stock Input (Interim Received) account through Odoo's native `get_product_accounts()` helper and assigns it directly.
- Posting/reposting a draft imported Splendid Vendor Bill automatically runs the repair first; the user no longer has to run the server action manually.
- Posted bills are still never rewritten silently; reset only the bill being corrected to Draft, review it, then Post.
- Service/freight/non-stock lines remain unchanged.


## v18.0.5.38.0 - Splendid tax source-of-truth
- Imported Sale Orders and Sales Invoices/Credit Notes always use exactly the taxes supplied on the Splendid line.
- Imported Purchase Orders and Vendor Bills/Debit Notes always use exactly the taxes supplied on the Splendid line.
- When Splendid sends no line tax, the Odoo tax M2M is explicitly cleared, so product default Customer Taxes / Vendor Taxes are not applied.
- Existing Splendid header tax/adjustment handling is unchanged.
- Normal non-Splendid Odoo sales/purchases are unchanged.
