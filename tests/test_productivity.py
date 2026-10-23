"""Unit tests for the Workplace Productivity Evaluation Module."""
import pytest
from backend.services.productivity_service import productivity_service

def test_efficiency_metrics_formula():
    """Verifies that the time savings formula ((Manual - AI) / Manual) * 100 calculates accurately."""
    metrics = productivity_service.calculate_efficiency_metrics(
        manual_time_minutes=240.0,
        ai_execution_time_minutes=0.5,
        human_oversight_time_minutes=3.5,
        manual_error_rate_pct=16.0,
        ai_error_rate_pct=2.0,
    )
    # Total AI time = 0.5 + 3.5 = 4.0 minutes
    # Time saved = 240.0 - 4.0 = 236.0 minutes
    # Time savings % = (236.0 / 240.0) * 100 = 98.33%
    # Speedup = 240 / 4 = 60.0x
    assert metrics["total_ai_assisted_time_minutes"] == 4.0
    assert metrics["time_saved_minutes"] == 236.0
    assert metrics["time_savings_pct"] == 98.33
    assert metrics["speedup_factor"] == 60.0
    assert metrics["error_reduction_pct"] == 87.5
    assert metrics["ai_accuracy_pct"] == 98.0

def test_evaluate_task_productivity():
    """Verifies task productivity trial generation."""
    trial = productivity_service.evaluate_task_productivity(
        task_id="task-prod-001",
        sources_count=3,
        evidence_count=6,
        benchmark_key="general_research",
    )
    assert trial["task_id"] == "task-prod-001"
    assert trial["speedup_factor"] > 10.0
    assert trial["time_savings_pct"] > 80.0
    assert trial["error_reduction_pct"] > 50.0
