# Splendid Accounts Sync for Odoo 18

This addon imports Splendid Accounts master data and transactions into Odoo 18.

## Supported API auth

The connection sends these headers on every request:

- `X-Api-Key`
- `X-Api-Secret`
- `X-App-Id`

The API URL format used by the module is:

`/api/{tenant}/{branch}/{endpoint}`

## Included sync objects

Master data:

- Chart of accounts: `/Accounts`
- Customers: `/Customers`
- Vendors: `/Vendors`
- Products: `/Products`
- Manufacturing BOM / assemblies: `/Products/AssemblyProducts` and `/Products/{productId}/Assemblies`

Transactions:

- Sales invoices: `/SaleInvoices`
- Sales returns: `/SaleReturns`
- Purchase invoices: `/PurchaseInvoices`
- Purchase returns: `/PurchaseReturns`
- Customer receipts: `/CustomerPayments`
- Vendor payments: `/VendorPayments`
- Journal entries: `/JournalEntries`
- Expenses: `/Expenses`

## How to use

1. Copy the folder `splendid_accounts_sync` to your Odoo custom addons path.
2. Restart Odoo and update Apps List.
3. Install **Splendid Accounts Sync**.
4. Open **Splendid Accounts → Connections**.
5. Create a connection and enter Base URL, Tenant, Branch, API Key, API Secret and App ID.
6. Configure Odoo journals and default accounts.
7. Click **Test Connection**.
8. Run **Sync Masters** first.
9. Then run **Sync Transactions**.

## Notes

- First sync should stay in draft mode until the accounting mapping is reviewed.
- External ID mappings prevent duplicate imports.
- Every import creates a log line under **Splendid Accounts → Sync Logs**.
- Exact tax mapping, warehouses, batches/serials and settlement allocation should be finalized after testing real API response samples.


## Multi-company behavior

Each Splendid connection has a required **Destination Company** field. Journals, accounts, partners, products, invoices, payments, journal entries, expenses, and BOMs are created using that selected company context. Create one connection per Odoo company/branch mapping.

## Splendid account mapping behavior

Transactions now resolve account lines from Splendid first:

- `accountId` on sale/purchase/expense/journal/payment detail lines
- nested `account` object returned by the API
- product accounts such as `salesAccountId`, `expenseAccountId`, `inventoryAccountId`
- header `accountId` for invoice/customer/vendor control account
- auto-fetch `/Accounts/{id}` when a referenced account is not already mapped

Default Odoo accounts are now only fallback accounts when Splendid does not send any account reference. Keep **Force Splendid Accounts** enabled to prevent silent posting to default/config accounts when Splendid has provided an account. If wrong draft records were imported before this fix, keep **Update Existing Draft Records** enabled and run **Sync Transactions** again; posted records will not be changed automatically.


## Inventory and Manufacturing Sync

This version also imports Splendid inventory and manufacturing data:

- Warehouses from Splendid branch warehouses into Odoo warehouses.
- Inventory snapshot from `/Products/Inventory` into Odoo stock quantities per warehouse.
- Inventory adjustments from `/InventoryAdjustments` as Odoo internal stock pickings.
- Stock movements from `/StocksMovement` as Odoo internal transfers.
- Manufacturing/job orders from `/JobOrders` as Odoo manufacturing orders.
- BOMs are still created from Splendid assembly products before manufacturing orders are imported.

Keep Auto Validate Stock Pickings and Auto Confirm Manufacturing Orders disabled for the first test sync. Enable them only after checking imported quantities and locations in staging.


## Individual Sync Buttons

To avoid API timeout/break issues on heavy data, the connection form now has an **Individual Sync Buttons** tab. You can sync each object separately:

Master data:

- Sync Chart of Accounts
- Sync Customers
- Sync Vendors
- Sync Products
- Sync Warehouses

Inventory:

- Sync Inventory Snapshot
- Sync Inventory Adjustments
- Sync Stock Movements

Manufacturing:

- Sync BOMs
- Sync Manufacturing Orders

Transactions:

- Sync Sales
- Sync Sales Returns
- Sync Purchases
- Sync Purchase Returns
- Sync Customer Receipts
- Sync Vendor Payments
- Sync Journal Entries
- Sync Expenses

Recommended order for large databases:

1. Sync Chart of Accounts
2. Sync Customers and Vendors
3. Sync Products and Warehouses
4. Sync Inventory Snapshot / Adjustments / Stock Movements
5. Sync BOMs
6. Sync Manufacturing Orders
7. Sync Sales / Purchases / Receipts / Payments / Journal Entries / Expenses one by one

The old grouped buttons are still available, but **Sync All** should only be used for small datasets or after testing.

## 18.0.1.4.1

Fixes added:
- Product import now maps Splendid stock/goods products to Odoo `consu` instead of invalid `product` for Odoo 18/19.
- Product import sets `is_storable` when Odoo has this field and Splendid `trackInventory` is enabled.
- Chart of Account import now sanitizes account codes so only alphanumeric characters and dots are sent to Odoo.

