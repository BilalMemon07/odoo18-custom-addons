{
    'name': 'Custom Invoice Format (Official/Unofficial)',
    'version': '1.0',
    'depends': ['account','web','base'],
    'data': [
        'views/res_company.xml',
        'views/partner_view.xml',
        'views/product_view.xml',
        'reports/invoice_report.xml',
    ],
    'installable': True,
}