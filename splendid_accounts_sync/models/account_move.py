# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    splendid_sale_invoice_id = fields.Char(index=True, copy=False)
    splendid_sale_return_id = fields.Char(index=True, copy=False)
    splendid_purchase_invoice_id = fields.Char(index=True, copy=False)
    splendid_purchase_return_id = fields.Char(index=True, copy=False)
    splendid_journal_entry_id = fields.Char(index=True, copy=False)
    splendid_expense_id = fields.Char(index=True, copy=False)
    splendid_job_order_expense_id = fields.Char(index=True, copy=False)
    splendid_job_order_id = fields.Char(index=True, copy=False)
    splendid_source_model = fields.Char(index=True, copy=False)
    splendid_is_imported = fields.Boolean(copy=False)
    splendid_raw_payload = fields.Json(copy=False)

    def _splendid_repair_purchase_bill_stock_accounts(self, raise_on_posted=True):
        """Restore Odoo native Anglo-Saxon accounts on imported Vendor Bills.

        Only Splendid Purchase Invoice bills are touched.  Only draft bills and
        only storable + real-time-valued product lines are recomputed.  Service,
        freight, tax and other non-stock expense lines keep their explicit
        accounts.  Posted accounting is never silently rewritten.
        """
        repaired = 0
        blocked = self.env["account.move"]

        for move in self:
            if (
                move.move_type not in ("in_invoice", "in_refund")
                or not move.splendid_purchase_invoice_id
                or not move.splendid_is_imported
            ):
                continue
            if not move.company_id.anglo_saxon_accounting:
                continue
            if move.state != "draft":
                blocked |= move
                continue

            stock_lines = move.invoice_line_ids.filtered(
                lambda line: line.product_id
                and getattr(line.product_id, "is_storable", False)
                and getattr(line.product_id, "valuation", False) == "real_time"
            )
            for line in stock_lines:
                old_account = line.account_id
                # Resolve the exact native Stock Input account from Odoo's own
                # product-account helper.  Do not rely on the previous invoice
                # line account or on Splendid expense/inventory account IDs.
                accounts = line.with_company(line.company_id).product_id.product_tmpl_id.get_product_accounts(
                    fiscal_pos=move.fiscal_position_id
                )
                stock_input = accounts.get("stock_input")
                if not stock_input:
                    raise UserError(_(
                        "No Stock Input (Interim Received) account is configured for product %s. "
                        "Configure the product/category stock accounts before posting this Splendid Vendor Bill."
                    ) % line.product_id.display_name)
                if line.account_id != stock_input:
                    line.account_id = stock_input
                    repaired += 1

        if blocked and raise_on_posted:
            names = ", ".join(blocked.mapped("name")[:10])
            if len(blocked) > 10:
                names += ", ..."
            raise UserError(_(
                "The following Splendid Vendor Bills are posted and were not changed: %s. "
                "Reset only the bills you want to correct to Draft first, then run "
                "'Repair Splendid Vendor Bill Stock Accounts', review the journal items, "
                "and post them again."
            ) % names)
        return repaired


    def _post(self, soft=True):
        """Guarantee correct Anglo-Saxon stock accounts before posting.

        Imported Splendid Vendor Bills created by older module versions may still
        carry the source COGS/expense account on storable real-time-valued lines.
        Reposting such a bill would otherwise keep that wrong account.  Repair
        eligible draft Splendid bills immediately before Odoo posts them.
        """
        candidates = self.filtered(lambda move: (
            move.state == "draft"
            and move.move_type in ("in_invoice", "in_refund")
            and move.splendid_purchase_invoice_id
            and move.splendid_is_imported
            and move.company_id.anglo_saxon_accounting
        ))
        for move in candidates:
            move._splendid_repair_purchase_bill_stock_accounts(raise_on_posted=False)
        posted = super()._post(soft=soft)

        # Imported Splendid Customer Invoices: after posting, run Odoo native
        # Anglo-Saxon reconciliation so delivered stock valuation is converted
        # into COGS. Purchase bills are handled above and remain unchanged.
        sale_candidates = posted.filtered(lambda move: (
            move.move_type in ("out_invoice", "out_refund")
            and move.splendid_sale_invoice_id
            and move.splendid_is_imported
            and move.company_id.anglo_saxon_accounting
        ))
        for move in sale_candidates:
            reconcile = getattr(move, "_stock_account_anglo_saxon_reconcile_valuation", False)
            if reconcile:
                reconcile()

        return posted

    def action_splendid_repair_purchase_bill_stock_accounts(self):
        repaired = self._splendid_repair_purchase_bill_stock_accounts(raise_on_posted=True)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Splendid Vendor Bill Accounts Repaired"),
                "message": _("%s stock-product Vendor Bill line(s) were recomputed using Odoo Anglo-Saxon Stock Input accounting.") % repaired,
                "type": "success",
                "sticky": False,
            },
        }
