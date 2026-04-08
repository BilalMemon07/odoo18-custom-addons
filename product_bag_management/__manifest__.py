{
    'name': 'Product Bag Management',
    'version': '1.0',
    'depends': ['sale', 'purchase', 'account','stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/product_bag_views.xml'
    ],
    'installable': True,
}