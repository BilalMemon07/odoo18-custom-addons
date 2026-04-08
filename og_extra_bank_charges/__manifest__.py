# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) Sitaram Solutions (<https://sitaramsolutions.in/>).
#
#    For Module Support : info@sitaramsolutions.in  or Skype : contact.hiren1188
#
##############################################################################

{
    'name': 'Extra Bank Charges In Payments',
    'version': '18.0.1.0',
    'category': 'Accounting',
    "license": "OPL-1",
    "price": 10,
    "currency": 'EUR',
    'author': 'Odoo Genics',
    'depends': ['base','account'],
    'data': [
             'views/sr_inherit_journal.xml',
             'views/sr_inherit_account_payment_views.xml',
             'wizards/sr_inherit_account_payment_register_views.xml'
    ],
    'website':'',
    'installable': True,
    'auto_install': False,
    'live_test_url':'',
    "images":[],
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
