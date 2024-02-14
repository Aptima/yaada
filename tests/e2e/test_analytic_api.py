import jsonschema
import pytest

from yaada.core.analytic.context import make_analytic_context

context = make_analytic_context("test", "test")
context.wait_for_ready()


def test_noop_analytic():
    r = context.sync_exec_analytic("yaada.core.analytic.builtin.noop.NoOp",parameters={'input':'foo'})
    assert r['return'] == 'foo'

