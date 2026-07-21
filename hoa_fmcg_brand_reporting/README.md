# House of Amin FMCG Brand Reporting

Odoo 18 addon for House of Amin FMCG configuration and reports.

## Important integration note

This version does not create duplicate Region / Zone / City masters. It depends on and reuses the existing `odoo_genics_x_amin_enterprise_ext` location models:

- `ib.geo.region`
- `ib.geo.zone`
- `ib.geo.territory`
- `ib.geo.town`

The FMCG reporting fields use aliases named `fmcg_region_id`, `fmcg_zone_id`, `fmcg_territory_id`, and `fmcg_city_id` so reports and documents can use a consistent FMCG naming layer while contacts continue to use the existing `geo_*` fields.

## Company control

Enable **FMCG Company** on the target company. FMCG fields are shown only when the active company has this checkbox enabled.

## Main features

- FMCG Company checkbox on company
- Brand master with analytic account and brand account mapping
- Sales Channel master
- Reuse existing Region / Zone / Territory / Town masters
- Product brand and default brand analytic account
- FMCG product category flag with brand-required validation
- Auto brand and analytic distribution on sales, purchases, invoices/bills, and expenses
- Partner geo dimensions flow to SO, PO, invoice/bill, and delivery order
- Packaging Type product attribute: Standard Packaging and Custom / Special Packaging
- Reports: Cost vs Revenue, Brand Sales & Revenue, Region-wise, Salesperson-wise, Brand P&L

## Installation

1. Put both folders in addons path:
   - `odoo_genics_x_amin_enterprise_ext`
   - `hoa_fmcg_brand_reporting`
2. Update Apps List.
3. Install / upgrade `Odoo Genics X Amin Enterprise Ext`.
4. Install / upgrade `House of Amin FMCG Brand Reporting`.
5. Open the target company and enable **FMCG Company**.
