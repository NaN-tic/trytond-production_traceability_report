# This file is part production_traceability_report module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
import unittest
from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import suite as test_suite


class ProductionTraceabilityReportTestCase(ModuleTestCase):
    'Test Production Traceability Report module'
    module = 'production_traceability_report'


def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            ProductionTraceabilityReportTestCase))
    return suite
