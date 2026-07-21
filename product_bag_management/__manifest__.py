{
    'name': 'Product Bag Management',
    'version': '18.0.1.1.0',
    'category': 'Inventory/Inventory',
    'summary': 'Manage product quantities in bags while storing and invoicing weight UoM',
    'depends': [
        'sale',
        'purchase',
        'account',
        'stock',
        'custom_invoice_format',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/product_bag_views.xml',
        'reports/invoice_report.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
