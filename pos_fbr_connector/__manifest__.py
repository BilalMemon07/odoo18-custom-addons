# -*- coding: utf-8 -*-
{
    'name': "Odoo POS FBR Connector",

    'summary': """
        Send POS Order to FBR to pay sales tax""",

    'description': """
        Long description of module's purpose
    """,

    'author': "Cybat",
    'website': "https://www.cybat.net",

    'category': 'POS',
    'version': '18.0',

    # any module necessary for this one to work correctly
    'depends': ['point_of_sale', 'product'],

    # always loaded
    'data': [
        'views/pos_config.xml',
        'views/pos_order.xml',
        'views/product.xml',
        'views/cron.xml',
        'views/templates.xml',
        'views/ir_action_server.xml',
        # 'views/purchase_order.xml'
    ],
    # "qweb": ["static/src/xml/pos.xml"],
            # 'pos_fbr_connector/static/src/js/pos.js',
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_fbr_connector/static/src/js/payment_screen_extend.js',
            'pos_fbr_connector/static/src/js/models_extend.js',
            'pos_fbr_connector/static/src/js/pos_order_receipt_fbr.js',
            'pos_fbr_connector/static/src/css/pos.css',
            'pos_fbr_connector/static/src/xml/pos.xml',
        ],
    },
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    "application": True,
    'images': ['static/description/main_screenshot.png', ],
    "price": 63,
    "currency": "EUR",
    'license': 'LGPL-3',
}
