{
    'name': 'Odoo Genics X Amin Enterprise Ext',
    'version': '1.0',
    'depends': ['sale', 'purchase', 'account','stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/location_master_views.xml',
        'views/res_partner.xml'

    ],
    'installable': True,
}