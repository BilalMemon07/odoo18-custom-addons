# -*- coding: utf-8 -*-
from odoo import models


class ReportMoOverview(models.AbstractModel):
    _inherit = "report.mrp.report_mo_overview"

    def _get_finished_operation_data(self, production, level=0, current_index=False):
        """Show Splendid fixed Work Order amounts as the *real* operation cost.

        Odoo 18's finished-MO Overview deliberately recalculates ``real_cost`` as
        ``duration_in_hours * workcenter_hourly_cost``.  That is correct for normal
        Work Orders, but not for Splendid Job Order expenses: those are fixed total
        charges and their technical Work Centers intentionally have ``costs_hour = 0``.

        The manufacturing valuation already uses ``mrp.workorder._cal_cost()`` and
        therefore receives our exact Splendid fixed amount.  This override only makes
        the MO Overview use the same source of truth for finished MOs, so the report's
        Operations Real Cost / Total Cost of Operations / unit manufacturing cost are
        consistent with valuation.
        """
        data = super()._get_finished_operation_data(
            production, level=level, current_index=current_index
        )

        details = data.get("details") or []
        workorders = production.workorder_ids
        if not details or not workorders:
            return data

        currency = (production.company_id or self.env.company).currency_id

        # Odoo builds exactly one finished-operation detail, in workorder order.
        # Patch only the Splendid fixed-cost Work Orders; ordinary Work Orders remain
        # on Odoo's native duration x hourly-rate calculation.
        for workorder, detail in zip(workorders, details):
            if not workorder.splendid_is_external_cost:
                continue

            fixed_cost = workorder.splendid_external_cost or 0.0
            rounded_fixed_cost = currency.round(fixed_cost)
            duration_hours = detail.get("quantity") or 0.0

            # The report has a Unit Cost (per hour) column but no Fixed Cost column.
            # Keep the displayed hours intact and use an equivalent hourly rate only
            # for presentation. Real Cost remains the exact Splendid fixed amount.
            detail["unit_cost"] = (
                fixed_cost / duration_hours if duration_hours else fixed_cost
            )
            detail["mo_cost"] = rounded_fixed_cost
            detail["real_cost"] = rounded_fixed_cost
            detail["real_cost_decorator"] = False

            # For our dedicated per-Job-Order BoM operation the BoM operation cost is
            # also the same fixed charge. Setting it here avoids any stale zero value
            # from an already-generated report structure.
            if workorder.operation_id and workorder.operation_id.splendid_is_external_cost:
                detail["bom_cost"] = rounded_fixed_cost

        # Rebuild finished-operation totals from the patched details. These summary
        # values feed the MO header Real Cost and the footer "Total Cost of Operations"
        # / per-unit manufacturing cost in Odoo's standard Overview.
        summary = data.get("summary") or {}
        summary["mo_cost"] = sum(detail.get("mo_cost") or 0.0 for detail in details)
        summary["real_cost"] = sum(detail.get("real_cost") or 0.0 for detail in details)

        bom_values = [detail.get("bom_cost") for detail in details]
        if any(value is not False for value in bom_values):
            summary["bom_cost"] = sum(value or 0.0 for value in bom_values)

        summary["real_cost_decorator"] = self._get_comparison_decorator(
            summary.get("mo_cost", 0.0),
            summary.get("real_cost", 0.0),
            currency.rounding,
        )
        data["summary"] = summary
        return data
