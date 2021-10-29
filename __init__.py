# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from . import production


def register():
    Pool.register(
        production.Production,
        production.PrintProductionTraceabilityStart,
        module='production_traceability_report', type_='model')
    Pool.register(
        production.PrintProductionTraceability,
        module='production_traceability_report', type_='wizard')
    Pool.register(
        production.PrintProductionTraceabilityReport,
        module='production_traceability_report', type_='report')
