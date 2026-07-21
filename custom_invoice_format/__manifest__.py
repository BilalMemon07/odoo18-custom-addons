{
    'name': 'Custom Invoice Format (Official/Unofficial)',
    'version': '18.0.0.1.0',
    'category': 'Accounting/Accounting',
    'summary': 'Company-specific custom invoice fields and invoice layout',
    'depends': ['account', 'product'],
    'data': [
        'views/res_company.xml',
        'views/partner_view.xml',
        'views/product_view.xml',
        'reports/invoice_report.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
