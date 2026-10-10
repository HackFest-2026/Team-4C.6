import pytest
from app.services.estimation.dependency_graph import DependencyGraph, CircularDependencyError
from app.services.estimation.engine import estimation_engine


def test_circular_dependency_rejection():
    """Mandatory test 15: Circular dependencies must be detected and rejected."""
    # A -> B -> C -> A
    cyclic_features = [
        {"id": "A", "name": "Feature A", "dependencies": ["C"]},
        {"id": "B", "name": "Feature B", "dependencies": ["A"]},
        {"id": "C", "name": "Feature C", "dependencies": ["B"]},
    ]
    graph = DependencyGraph(cyclic_features)
    cycles = graph.detect_cycles()
    assert len(cycles) > 0, "Failed to detect cyclic nodes"

    with pytest.raises(CircularDependencyError, match="Circular dependency detected"):
        graph.validate()

    # Calling estimation_engine with circular dependencies should also reject
    with pytest.raises(CircularDependencyError):
        estimation_engine.estimate_project({
            "name": "Cyclic Project",
            "features": cyclic_features
        })


def test_valid_dag_critical_path():
    """Valid DAG must compute correct critical path sequence and hours."""
    # F1 (10h) -> F2 (20h) -> F3 (30h)
    # F4 (15h) independent
    features = [
        {"id": "F1", "name": "F1", "expected_effort_hours": 10.0, "dependencies": []},
        {"id": "F2", "name": "F2", "expected_effort_hours": 20.0, "dependencies": ["F1"]},
        {"id": "F3", "name": "F3", "expected_effort_hours": 30.0, "dependencies": ["F2"]},
        {"id": "F4", "name": "F4", "expected_effort_hours": 15.0, "dependencies": []},
    ]
    graph = DependencyGraph(features)
    crit_hours, crit_nodes, depth = graph.calculate_critical_path(effort_key="expected_effort_hours")
    
    assert crit_hours == 60.0  # 10 + 20 + 30
    assert crit_nodes == ["F1", "F2", "F3"]
    assert depth == 3
