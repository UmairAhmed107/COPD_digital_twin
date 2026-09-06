"""
Structural tests for src/reliability.py.

The reliability calculation is not yet finalized (architecture.md
Section 4.3). These tests confirm the module imports, the record
schema is usable, and the scoring stub clearly signals
"not implemented".
"""

import pytest

from src import reliability


def test_module_imports():
    assert reliability is not None


def test_reliability_record_schema():
    record = reliability.ReliabilityRecord(
        observation={"fev1": 2.1},
        source="home_sensor",
        quality_information={"signal_quality": "ok"},
        reliability_score=None,
        timestamp="2026-09-02T00:00:00",
        reason_metadata={"note": "placeholder"},
    )
    assert record.observation == {"fev1": 2.1}
    assert record.source == "home_sensor"
    assert record.reliability_score is None


def test_compute_reliability_score_not_implemented():
    with pytest.raises(NotImplementedError):
        reliability.compute_reliability_score(observation={}, context={})
