import os
import sys
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from analytics.cashflow_intelligence import detect_distress, detect_deleveraging


def test_detect_distress_true():
    row = {"operating_activity": -50.0, "financing_activity": 100.0}
    assert detect_distress(row) == True


def test_detect_distress_false_when_cfo_positive():
    row = {"operating_activity": 50.0, "financing_activity": 100.0}
    assert detect_distress(row) == False


def test_detect_distress_false_when_cff_negative():
    row = {"operating_activity": -50.0, "financing_activity": -20.0}
    assert detect_distress(row) == False


def test_detect_deleveraging_true():
    g = pd.DataFrame([
        {"financing_activity": -10.0, "total_debt_cr": 500.0},
        {"financing_activity": -30.0, "total_debt_cr": 400.0},  # debt declined, CFF negative
    ])
    assert detect_deleveraging(g) == True


def test_detect_deleveraging_false_when_debt_rising():
    g = pd.DataFrame([
        {"financing_activity": -10.0, "total_debt_cr": 400.0},
        {"financing_activity": -30.0, "total_debt_cr": 500.0},  # debt rose
    ])
    assert detect_deleveraging(g) == False


def test_detect_deleveraging_false_with_one_year():
    g = pd.DataFrame([{"financing_activity": -30.0, "total_debt_cr": 400.0}])
    assert detect_deleveraging(g) == False
