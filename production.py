# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import os
from datetime import datetime
from collections import OrderedDict
from trytond.config import config
from trytond.model import fields, ModelView
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval, If
from trytond.wizard import Wizard, StateView, StateReport, Button
from trytond.transaction import Transaction
from trytond.modules.html_report.html_report import HTMLReport


__all__ = ['Production', 'PrintProductionTraceabilityStart',
    'PrintProductionTraceability', 'PrintProductionTraceabilityReport']

BASE_URL = config.get('web', 'base_url')
_ZERO = 0.0


class Production(metaclass=PoolMeta):
    __name__ = 'production'

    def traceability_report_data(self, requested_product, direction, lot=None):
        Uom = Pool().get('product.uom')

        quantity = 0.0
        for move in getattr(self, 'outputs' if direction == 'backward' else 'inputs'):
            if move.product == requested_product:
                quantity += Uom.compute_qty(move.unit, move.quantity, move.product.default_uom, False)

        moves = {}
        for move in getattr(self, 'inputs' if direction == 'backward' else 'outputs'):
            product = move.product
            lot = move.lot or None if hasattr(move, 'lot') else None
            mqty = Uom.compute_qty(
                move.unit, move.quantity, move.product.default_uom, False)
            if moves.get(product):
                if moves[product].get(lot):
                    moves[product][lot] += mqty
                else:
                    moves[product][lot] = mqty
            else:
                moves[product] = {lot: mqty}

        res = {}
        for product, values in moves.items():
            item = res.setdefault(product, {})
            for lot, qty in values.items():
                if direction == 'backward':
                    traceability_quantity = quantity
                    traceability_consumption = qty
                    traceability_quantity_uom = requested_product.default_uom
                    traceability_consumption_uom = product.default_uom
                else:
                    traceability_quantity = qty
                    traceability_consumption = quantity
                    traceability_quantity_uom = product.default_uom
                    traceability_consumption_uom = requested_product.default_uom
                vals = {
                    'production': self,
                    'traceability_quantity': traceability_quantity,
                    'traceability_consumption': traceability_consumption,
                    'traceability_quantity_uom': traceability_quantity_uom,
                    'traceability_consumption_uom': traceability_consumption_uom,
                    }
                item[lot] = vals
        return res


class PrintProductionTraceabilityStart(ModelView):
    'Print Production Traceability Start'
    __name__ = 'production.traceability.start'
    product = fields.Many2One('product.product', 'Product', required=True)
    from_date = fields.Date('From Date',
        domain = [
            If(Bool(Eval('from_date')) & Bool(Eval('to_date')),
                ('from_date', '<=', Eval('to_date')), ())],
        states={
            'required': Bool(Eval('to_date', False)),
        })
    to_date = fields.Date('To Date',
        domain = [
            If(Bool(Eval('from_date')) & Bool(Eval('to_date')),
                ('from_date', '<=', Eval('to_date')), ())],
        states={
            'required': Bool(Eval('from_date', False)),
        })
    direction = fields.Selection([
        ('backward', 'Backward'),
        ('forward', 'Forward'),
        ], 'Direction', required=True)

    @classmethod
    def __setup__(cls):
        super(PrintProductionTraceabilityStart, cls).__setup__()
        try:
            Lot = Pool().get('stock.lot')
        except:
            Lot = None
        if Lot:
            cls.lot = fields.Many2One('stock.lot', 'Lot',
                domain=[
                    ('product', '=', Eval('product')),
                    ])

    @staticmethod
    def default_direction():
        return 'backward'


class PrintProductionTraceability(Wizard):
    'Print Production Traceability'
    __name__ = 'production.print_traceability'
    start = StateView('production.traceability.start',
        'production_traceability_report.print_production_traceability_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Print', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateReport('production.traceability.report')

    def default_start(self, fields):
        context = Transaction().context

        res = {}
        if context.get('active_model'):
            Model = Pool().get(context['active_model'])
            id = Transaction().context['active_id']
            if Model.__name__ == 'product.template':
                template = Model(id)
                if template.products:
                    res['product'] = template.products[0].id
            elif Model.__name__ == 'product.product':
                res['product'] = id
            elif Model.__name__ == 'stock.lot':
                lot = Model(id)
                res['lot'] = lot.id
                res['product'] = lot.product.id
        return res

    def do_print_(self, action):
        context = Transaction().context
        data = {
            'direction': self.start.direction,
            'from_date': self.start.from_date,
            'to_date': self.start.to_date,
            'product': self.start.product.id,
            'model': context.get('active_model'),
            'ids': context.get('active_ids') or [],
            }
        try:
            Lot = Pool().get('stock.lot')
        except:
            Lot = None
        if Lot:
            data['lot'] = self.start.lot.id if self.start.lot else None
        return action, data


class PrintProductionTraceabilityReport(HTMLReport):
    __name__ = 'production.traceability.report'

    @classmethod
    def get_context(cls, records, data):
        pool = Pool()
        Company = pool.get('company.company')
        t_context = Transaction().context

        context = super().get_context(records, data)
        context['company'] = Company(t_context['company'])
        return context

    @classmethod
    def prepare(cls, data):
        pool = Pool()
        Product = pool.get('product.product')
        Company = pool.get('company.company')
        Production = pool.get('production')

        try:
            Lot = pool.get('stock.lot')
        except:
            Lot = None

        t_context = Transaction().context
        company_id = t_context.get('company')
        from_date = data.get('from_date') or datetime.min.date()
        to_date = data.get('to_date') or datetime.max.date()

        requested_product = Product(data['product'])
        direction = data['direction']
        lot = Lot(data['lot']) if data.get('lot') else None

        parameters = {}
        parameters['direction'] = direction
        parameters['from_date'] = from_date
        parameters['to_date'] = to_date
        parameters['show_date'] = bool(data.get('from_date'))
        parameters['requested_product'] = requested_product
        parameters['lot'] = lot

        # TODO get url from trytond.url issue8767
        if BASE_URL:
            base_url = '%s/#%s' % (
                BASE_URL, Transaction().database.name)
        else:
            base_url = '%s://%s/#%s' % (
                t_context['_request']['scheme'],
                t_context['_request']['http_host'],
                Transaction().database.name
                )
        parameters['base_url'] = base_url
        parameters['company'] = Company(company_id)

        records = OrderedDict()

        if direction == 'backward':
            domain = [
                    ('outputs.product', '=', requested_product),
                    ('outputs.effective_date', '>=', from_date),
                    ('outputs.effective_date', '<=', to_date),
                    ('outputs.state', '=', 'done'),
                    ('company', '=', company_id),
                    ]
            if lot:
                domain += [('outputs.lot', '=', lot)]
        else:
            domain = [
                    ('inputs.product', '=', requested_product),
                    ('inputs.effective_date', '>=', from_date),
                    ('inputs.effective_date', '<=', to_date),
                    ('inputs.state', '=', 'done'),
                    ('company', '=', company_id),
                    ]
            if lot:
                domain += [('inputs.lot', '=', lot)]

        productions = Production.search(domain)

        records = {}
        totals = {}
        for production in productions:
            res = production.traceability_report_data(requested_product,
                    direction, lot)

            for key, values in res.items():
                if not records.get(key):
                    records.setdefault(key, {})

                for k, v in values.items():
                    # records
                    if k in records[key]:
                        records[key][k].append(v)
                    else:
                        records[key][k] = [v]

                    # totals
                    if not key in totals:
                        item = totals.setdefault(key, {})
                        item.setdefault('quantity', 0.0)
                        item.setdefault('consumption', 0.0)
                        item.setdefault('quantity_uom', v['traceability_quantity_uom'])
                        item.setdefault('consumption_uom', v['traceability_consumption_uom'])
                    totals[key]['quantity'] += v['traceability_quantity']
                    totals[key]['consumption'] += v['traceability_consumption']

        return records, totals, parameters

    @classmethod
    def execute(cls, ids, data):
        context = Transaction().context.copy()
        context['report_lang'] = Transaction().language
        context['report_translations'] = os.path.join(
            os.path.dirname(__file__), 'report', 'translations')

        with Transaction().set_context(**context):
            records, totals, parameters = cls.prepare(data)
            return super(PrintProductionTraceabilityReport, cls).execute(ids, {
                    'name': 'production.traceability.report',
                    'model': data['model'],
                    'records': records,
                    'totals': totals,
                    'parameters': parameters,
                    'output_format': 'html',
                    'report_options': {
                        'now': datetime.now(),
                        }
                    })
