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
from openerp import models, fields, api, _
import openerp.addons.decimal_precision as dp
import datetime
from datetime import datetime
from dateutil import relativedelta
from openerp.exceptions import except_orm, Warning, RedirectWarning


class account_payment_term(models.Model):
    _inherit = "account.payment.term"

    interest_type = fields.Selection([('daily', 'Daily'),
                                   ('monthly', 'Monthly'),
                                   ], 'Interest Type')
    interest_percentage = fields.Float('Interest Percentage', digits=(16, 6))
    account_id = fields.Many2one('account.account', 'Account')


class account_invoice(models.Model):
    _inherit = "account.invoice"

    @api.multi
    def action_move_create(self):
        """ Creates invoice related analytics and financial move lines """
        account_invoice_tax = self.env['account.invoice.tax']
        account_move = self.env['account.move']
        for inv in self:
            if not inv.journal_id.sequence_id:
                raise except_orm(_('Error!'), _('Please define sequence on the journal related to this invoice.'))
            if not inv.invoice_line_ids:
                raise except_orm(_('No Invoice Lines!'), _('Please create some invoice lines.'))
            if inv.move_id:
                continue
            ctx = dict(self._context, lang=inv.partner_id.lang)
            if not inv.date_invoice:
                inv.with_context(ctx).write({'date_invoice': fields.Date.context_today(self)})
            date_invoice = inv.date_invoice
            company_currency = inv.company_id.currency_id
            # create the analytical lines, one move line per invoice line
            iml = inv.invoice_line_move_line_get()
            iml += inv.tax_line_move_line_get()
            if inv.payment_term_id:
                total_fixed = total_percent = 0
                for line in inv.payment_term_id.line_ids:
                    if line.value == 'fixed':
                        total_fixed += line.value_amount
                    if line.value == 'procent':
                        total_percent += line.value_amount
                total_fixed = (total_fixed * 100) / (inv.amount_total or 1.0)
                if (total_fixed + total_percent) > 100:
                    raise except_orm(_('Error!'), _("Cannot create the invoice.\nThe related payment term is probably misconfigured as it gives a computed amount greater than the total invoiced amount. In order to avoid rounding issues, the latest line of your payment term must be of type 'balance'."))
            if inv.type in ('in_invoice', 'in_refund'):
                ref = inv.reference
            else:
                ref = inv.number
            diff_currency = inv.currency_id != company_currency
            # create one move line for the total and possibly adjust the other lines amount
            total, total_currency, iml = inv.with_context(ctx).compute_invoice_totals(company_currency, iml)
            name = inv.name or '/'
            totlines = []
            if inv.payment_term_id:
                totlines = inv.with_context(ctx).payment_term_id.compute(total, date_invoice)[0]
            if totlines:
                res_amount_currency = total_currency
                ctx['date'] = date_invoice
                for i, t in enumerate(totlines):
                    if inv.currency_id != company_currency:
                        amount_currency = company_currency.with_context(ctx).compute(t[1], inv.currency_id)
                    else:
                        amount_currency = False
                    # last line: add the diff
                    res_amount_currency -= amount_currency or 0
                    if i + 1 == len(totlines):
                        amount_currency += res_amount_currency
                    iml.append({
                        'type': 'dest',
                        'name': name,
                        'price': t[1],
                        'account_id': inv.account_id.id,
                        'date_maturity': t[0],
                        'amount_currency': diff_currency and amount_currency,
                        'currency_id': diff_currency and inv.currency_id.id,
                        'ref': ref,
                    })
            else:
                iml.append({
                    'type': 'dest',
                    'name': name,
                    'price': total,
                    'account_id': inv.account_id.id,
                    'date_maturity': inv.date_due,
                    'amount_currency': diff_currency and total_currency,
                    'currency_id': diff_currency and inv.currency_id.id,
                    'ref': ref
                })
            date = date_invoice
            # added for interest in iml
            date1 = datetime.strptime(self.date_due, '%Y-%m-%d')
            date2 = datetime.strptime(str(datetime.now().date()), '%Y-%m-%d')   
            if self.payment_term_id.id and date2 > date1:
                iml.append({
                    'type': 'dest',
                    'name': 'Interest Entery',
                    'price':-self.interest ,
                    'account_id': self.payment_term_id.account_id.id,
                    'date_maturity': inv.date_due,
                    'amount_currency': diff_currency and total_currency,
                    'currency_id': diff_currency and inv.currency_id.id,
                    'ref': ref,
                     
                })
            part = self.env['res.partner']._find_accounting_partner(inv.partner_id)
            line = [(0, 0, self.line_get_convert(l, part.id, date)) for l in iml]
            line = inv.group_lines(iml, line)
            journal = inv.journal_id.with_context(ctx)
            line = inv.finalize_invoice_move_lines(line)
            move_vals = {
                'ref': inv.reference or inv.name,
                'line_ids': line,
                'journal_id': journal.id,
                'date': inv.date_invoice,
                'narration': inv.comment,
                'company_id': inv.company_id.id,
            }
            ctx['company_id'] = inv.company_id.id
            ctx['dont_create_taxes'] = True
            ctx['invoice'] = inv
            ctx_nolang = ctx.copy()
            ctx_nolang.pop('lang', None)
            move = account_move.with_context(ctx_nolang).create(move_vals)
            # make the invoice point to that move
            vals = {
                'move_id': move.id,
                'move_name': move.name,
                'date': inv.date or date_invoice
            }
            inv.with_context(ctx).write(vals)
            # Pass invoice in context in method post: used if you want to get the same
            # account move reference when creating the same invoice after a cancelled one:
            move.post()
        return True

    @api.model
    def line_get_convert(self, line, part, date):
            # self.total = self.total + line['price']
            date1 = datetime.strptime(self.date_due, '%Y-%m-%d')
            date2 = datetime.strptime(str(datetime.now().date()), '%Y-%m-%d')   
            if self.payment_term_id.id and date2 > date1 and  self.type in('out_invoice') and line['name'] == '/':
                if line['price'] > 0:
                    total_amt = line['price'] + self.interest 
                    return {
                        'date_maturity': line.get('date_maturity', False),
                        'partner_id': part,
                        'name': line['name'][:64],
                        'date': date,
                        'debit':total_amt ,
                        'credit': line['price'] < 0  and -line['price'],
                        'account_id': line['account_id'],
                        'analytic_lines': line.get('analytic_lines', []),
                        'amount_currency': line['price'] > 0 and abs(line.get('amount_currency', False)) or -abs(line.get('amount_currency', False)),
                        'currency_id': line.get('currency_id', False),
                        'tax_code_id': line.get('tax_code_id', False),
                        'tax_amount': line.get('tax_amount', False),
                        'ref': line.get('ref', False),
                        'quantity': line.get('quantity', 1.00),
                        'product_id': line.get('product_id', False),
                        'product_uom_id': line.get('uos_id', False),
                        'analytic_account_id': line.get('account_analytic_id', False),
                    }
            else:
                return { 
                      'date_maturity': line.get('date_maturity', False),
                        'partner_id': part,
                        'name': line['name'][:64],
                        'date': date,
                        'debit': line['price'] > 0  and line['price'],
                        'credit': line['price'] < 0 and -line['price'],
                        'account_id': line['account_id'],
                        'analytic_lines': line.get('analytic_lines', []),
                        'amount_currency': line['price'] > 0 and abs(line.get('amount_currency', False)) or -abs(line.get('amount_currency', False)),
                        'currency_id': line.get('currency_id', False),
                        'tax_code_id': line.get('tax_code_id', False),
                        'tax_amount': line.get('tax_amount', False),
                        'ref': line.get('ref', False),
                        'quantity': line.get('quantity', 1.00),
                        'product_id': line.get('product_id', False),
                        'product_uom_id': line.get('uos_id', False),
                        'analytic_account_id': line.get('account_analytic_id', False),
                      }

    @api.one
    @api.depends('invoice_line_ids.price_subtotal', 'tax_line_ids.amount', 'payment_term_id')
    def _compute_amount(self, flag=1):
        self.amount_untaxed = sum(line.price_subtotal for line in self.invoice_line_ids)
        self.amount_tax = sum(line.amount for line in self.tax_line_ids)
        apt_per = self.env['account.payment.term']
        apt_per_record = apt_per.browse(self.payment_term_id.id)
        per = apt_per_record.interest_percentage
        if self.type in('out_invoice'):
            if flag == 0:
                int_per = 0.0 
                self.write({'interest':int_per})
                self.amount_total = self.amount_untaxed + self.amount_tax + self.interest
                return
            if self.date_due and self.payment_term_id:
                date1 = datetime.strptime(self.date_due, '%Y-%m-%d')
                date2 = datetime.strptime(str(datetime.now().date()), '%Y-%m-%d')   
                r = relativedelta.relativedelta(date2, date1)
                no_of_months = r.months
                # no_of_days  = r.days
                no_of_days = (date2 - date1).days
                if date1 and date2:
                    if date2 > date1 :
                        self.show_intrest = True
                        if apt_per_record.interest_type == 'monthly':
                            if no_of_months == 0 :
                                no_of_months = 1
                            no_of_months = no_of_months 
                            int_per = (self.amount_untaxed + self.amount_tax) * (per / 100) * (no_of_months)
                            self.write({'interest':int_per})
                            self.amount_total = self.amount_untaxed + self.amount_tax + self.interest 
                        if apt_per_record.interest_type == 'daily':
                            int_per = (self.amount_untaxed + self.amount_tax) * (per / 100) * (no_of_days)
                            self.write({'interest':int_per})
                            self.amount_total = self.amount_untaxed + self.amount_tax + self.interest
                    else:
                         self.amount_total = self.amount_untaxed + self.amount_tax




    show_intrest = fields.Boolean('is_intrest', default=False)
    interest = fields.Float(string="Interest", readonly=True)
    amount_untaxed = fields.Float(string='Subtotal', digits=dp.get_precision('Account'),
                                  store=True    , readonly=True, compute='_compute_amount', track_visibility='always')
    amount_tax = fields.Float(string='Tax', digits=dp.get_precision('Account'),
                              store=True    , readonly=True, compute='_compute_amount')
    amount_total = fields.Float(string='Total', digits=dp.get_precision('Account'),
                                store=True , readonly=True, compute='_compute_amount')    

    @api.onchange('date_due')
    def _onchange_date_due(self):
        if self.date_due :
            date1 = datetime.strptime(self.date_due, '%Y-%m-%d')
            date2 = datetime.strptime(str(datetime.now().date()), '%Y-%m-%d')   
            if date2 > date1:
                self.show_intrest = True
            else:
                self.show_intrest = False    

    @api.one
    def button_add_interest(self):
        self.compute_taxes()
        self._compute_amount(1)

    @api.one
    def button_reset_interest(self):
        self.compute_taxes()
        self._compute_amount(0)
        self.interest = 0.0
