# Splendid Accounts Sync for Odoo 18

End-to-end import from Splendid Accounts into Odoo 18.

## Main coverage

### Masters
- Chart of accounts
- Customers
- Vendors
- Products
- Warehouses

### Sales module
- Sale orders → `sale.order`
- Sale deliveries → `stock.picking` outgoing
- Sale invoices → `account.move` customer invoice
- Sale returns → `account.move` credit note
- Customer receipts → `account.payment` inbound
- Customer refunds → `account.payment` outbound

### Purchase module
- Purchase orders → `purchase.order`
- Purchase receipts → `stock.picking` incoming
- Purchase invoices/bills → `account.move` vendor bill
- Purchase returns → `account.move` vendor credit/debit note flow
- Vendor payments → `account.payment` outbound
- Vendor refunds → `account.payment` inbound

### Inventory / Manufacturing
- Inventory snapshot
- Inventory adjustments
- Stock movements
- BOMs
- Manufacturing/job orders

### Accounting / Bank
- Journal entries
- Expenses
- Bank deposits

## Recommended flow

1. Create a connection and select the destination company.
2. Test connection.
3. Sync Masters.
4. Sync Sales Module.
5. Sync Purchase Module.
6. Sync Inventory Module.
7. Sync Manufacturing Module.
8. Sync Accounting/Bank Module.

For large datasets, use the individual buttons instead of Sync All.

## Safety options

Keep these disabled during first testing:

- Auto Post Moves
- Auto Confirm Sale Orders
- Auto Confirm Purchase Orders
- Auto Validate Stock Pickings
- Auto Confirm Manufacturing Orders

Enable Auto Reconcile Payments only after invoices/bills are posted successfully.
