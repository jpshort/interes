# -*- coding: utf-8 -*-
##############################################################################
#
#    This module uses OpenERP, Open Source Management Solution Framework.
#    Copyright (C) 2014-Today BrowseInfo (<http://www.browseinfo.in>)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>
#
##############################################################################


{
    'name': 'Interest on Overdue Invoice',
    'summary': 'Calculate interest on Overdue Invoice Based on Payment Terms',
    'category': 'Accounting',
    'price': '55.00',
    'currency': "EUR",
    'description': """
    -Calculate Interest for Overdue Invoice, Calculate interest from Payment terms, Interest on payment terms, Interest on invoice, Overdue payment interest. Overdue charges on invoice. Overdue rate calculate. Penalty on overdue invoice, Penatly on overdue payment. Add interest on invoice. Add Interest on Ovedue payment. Late Payment charges. Apply Penalty charges for Overdue Invoice, Apply interest on ovedue invoice.

    """,
    "category": 'Accounting',
    'author': 'BrowseInfo',
    'website': 'www.browseinfo.in',
    'depends': ['base','sale','account'],
    'data': [
        'account_payment_term_view.xml',
        'security/invoice_security.xml',
    ],
    'demo': [],
    'test': [],
    'installable': True,
    'auto_install': False,
    'application': True,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
