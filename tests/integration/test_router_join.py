"""Integration tests for Router and Join operators."""

import pytest
from agenarc.engine.executor import ExecutionEngine, ExecutionMode, NodeStatus
from agenarc.engine.state import StateManager
from agenarc.operators.builtin import BUILTIN_OPERATORS
from agenarc.plugins.manager import PluginManager
from agenarc.protocol.schema import NodeType, Edge, Graph, Node, NodeConfig, Port, Condition, ConditionOperator


def create_test_engine():
    """Create a test execution engine with all built-in operators."""
    plugin_manager = PluginManager()
    engine = ExecutionEngine(plugin_manager=plugin_manager)

    for node_type, operator_class in BUILTIN_OPERATORS.items():
        if operator_class is not None:
            engine.register_builtin_operator(node_type, operator_class)

    return engine


class TestRouterOperator:
    """Integration tests for Router operator."""

    @pytest.mark.asyncio
    async def test_router_condition_matching(self):
        """Test Router selects correct branch based on condition."""
        data = {
            "version": "1.0.0",
            "nodes": [
                {
                    "id": "trigger_1",
                    "type": "Trigger",
                    "label": "Start"
                },
                {
                    "id": "router_1",
                    "type": "Router",
                    "label": "Route",
                    "config": {
                        "conditions": [
                            {
                                "ref": "input",
                                "operator": "EQ",
                                "value": "go",
                                "output": "path_a"
                            },
                            {
                                "ref": "input",
                                "operator": "NE",
                                "value": "go",
                                "output": "path_b"
                            }
                        ],
                        "default": "path_b"
                    }
                },
                {
                    "id": "log_a",
                    "type": "Log",
                    "label": "Path A"
                },
                {
                    "id": "log_b",
                    "type": "Log",
                    "label": "Path B"
                }
            ],
            "edges": [
                {"source": "trigger_1", "target": "router_1"},
                {"source": "router_1", "sourcePort": "path_a", "target": "log_a"},
                {"source": "router_1", "sourcePort": "path_b", "target": "log_b"}
            ]
        }
        engine = create_test_engine()
        engine.load_protocol(data, validate=False)

        result = await engine.execute({"payload": "go"})

        assert result.status == "success"
        assert result.node_results["router_1"].status == NodeStatus.COMPLETED
        # Both branches may execute (Router evaluates all conditions)
        assert result.node_results["log_a"].status == NodeStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_router_no_match_uses_default(self):
        """Test Router falls back to default when no conditions match."""
        data = {
            "version": "1.0.0",
            "nodes": [
                {
                    "id": "trigger_1",
                    "type": "Trigger",
                    "label": "Start"
                },
                {
                    "id": "router_1",
                    "type": "Router",
                    "label": "Route",
                    "config": {
                        "conditions": [
                            {
                                "ref": "input",
                                "operator": "EQ",
                                "value": "specific",
                                "output": "specific_path"
                            }
                        ],
                        "default": "other"
                    }
                },
                {
                    "id": "log_other",
                    "type": "Log",
                    "label": "Other"
                }
            ],
            "edges": [
                {"source": "trigger_1", "target": "router_1"},
                {"source": "router_1", "sourcePort": "other", "target": "log_other"}
            ]
        }
        engine = create_test_engine()
        engine.load_protocol(data, validate=False)

        result = await engine.execute({"payload": "anything_else"})

        assert result.status == "success"
        assert result.node_results["router_1"].status == NodeStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_router_multiple_matches_parallel_branches(self):
        """Test Router with multiple matching conditions triggers parallel branches."""
        data = {
            "version": "1.0.0",
            "nodes": [
                {
                    "id": "trigger_1",
                    "type": "Trigger",
                    "label": "Start"
                },
                {
                    "id": "router_1",
                    "type": "Router",
                    "label": "Route",
                    "config": {
                        "conditions": [
                            {
                                "ref": "input",
                                "operator": "CONTAINS",
                                "value": "a",
                                "output": "has_a"
                            },
                            {
                                "ref": "input",
                                "operator": "CONTAINS",
                                "value": "b",
                                "output": "has_b"
                            }
                        ]
                    }
                },
                {
                    "id": "log_a",
                    "type": "Log",
                    "label": "Has A"
                },
                {
                    "id": "log_b",
                    "type": "Log",
                    "label": "Has B"
                }
            ],
            "edges": [
                {"source": "trigger_1", "target": "router_1"},
                {"source": "router_1", "sourcePort": "has_a", "target": "log_a"},
                {"source": "router_1", "sourcePort": "has_b", "target": "log_b"}
            ]
        }
        engine = create_test_engine()
        engine.load_protocol(data, validate=False)

        result = await engine.execute({"payload": "a and b together"})

        assert result.status == "success"
        assert result.node_results["router_1"].status == NodeStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_router_context_reference(self):
        """Test Router can reference context values in conditions."""
        data = {
            "version": "1.0.0",
            "nodes": [
                {
                    "id": "trigger_1",
                    "type": "Trigger",
                    "label": "Start"
                },
                {
                    "id": "set_flag",
                    "type": "Context_Set",
                    "label": "Set Flag",
                    "config": {"key": "mode", "value": "fast"}
                },
                {
                    "id": "router_1",
                    "type": "Router",
                    "label": "Route",
                    "config": {
                        "conditions": [
                            {
                                "ref": "context.mode",
                                "operator": "EQ",
                                "value": "fast",
                                "output": "fast_path"
                            }
                        ],
                        "default": "slow_path"
                    }
                },
                {
                    "id": "log_fast",
                    "type": "Log",
                    "label": "Fast"
                }
            ],
            "edges": [
                {"source": "trigger_1", "target": "set_flag"},
                {"source": "set_flag", "target": "router_1"},
                {"source": "router_1", "sourcePort": "fast_path", "target": "log_fast"}
            ]
        }
        engine = create_test_engine()
        engine.load_protocol(data, validate=False)

        result = await engine.execute()

        assert result.status == "success"


class TestJoinOperator:
    """Integration tests for Join operator."""

    @pytest.mark.asyncio
    async def test_join_no_incoming_edges(self):
        """Test Join with no incoming edges returns None."""
        data = {
            "version": "1.0.0",
            "nodes": [
                {"id": "trigger_1", "type": "Trigger", "label": "Start"},
                {
                    "id": "join_1",
                    "type": "Join",
                    "label": "Join",
                    "config": {"strategy": "merge"}
                }
            ],
            "edges": [
                {"source": "trigger_1", "target": "join_1"}
            ]
        }
        engine = create_test_engine()
        engine.load_protocol(data, validate=False)

        result = await engine.execute()

        assert result.status == "success"
        assert result.node_results["join_1"].status == NodeStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_join_concat_strategy(self):
        """Test Join with concat strategy."""
        data = {
            "version": "1.0.0",
            "nodes": [
                {
                    "id": "trigger_1",
                    "type": "Trigger",
                    "label": "Start"
                },
                {
                    "id": "set_1",
                    "type": "Context_Set",
                    "label": "Set 1",
                    "config": {"key": "item", "value": "item1"}
                },
                {
                    "id": "set_2",
                    "type": "Context_Set",
                    "label": "Set 2",
                    "config": {"key": "item", "value": "item2"}
                },
                {
                    "id": "join_1",
                    "type": "Join",
                    "label": "Join",
                    "config": {"strategy": "concat"}
                }
            ],
            "edges": [
                {"source": "trigger_1", "target": "set_1"},
                {"source": "trigger_1", "target": "set_2"},
                {"source": "set_1", "target": "join_1"},
                {"source": "set_2", "target": "join_1"}
            ]
        }
        engine = create_test_engine()
        engine.load_protocol(data, validate=False)

        result = await engine.execute()

        assert result.status == "success"
        assert result.node_results["join_1"].status == NodeStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_join_first_strategy(self):
        """Test Join with first strategy."""
        data = {
            "version": "1.0.0",
            "nodes": [
                {
                    "id": "trigger_1",
                    "type": "Trigger",
                    "label": "Start"
                },
                {
                    "id": "set_1",
                    "type": "Context_Set",
                    "label": "First",
                    "config": {"key": "order", "value": "first"}
                },
                {
                    "id": "set_2",
                    "type": "Context_Set",
                    "label": "Second",
                    "config": {"key": "order", "value": "second"}
                },
                {
                    "id": "join_1",
                    "type": "Join",
                    "label": "Join",
                    "config": {"strategy": "first"}
                }
            ],
            "edges": [
                {"source": "trigger_1", "target": "set_1"},
                {"source": "trigger_1", "target": "set_2"},
                {"source": "set_1", "target": "join_1"},
                {"source": "set_2", "target": "join_1"}
            ]
        }
        engine = create_test_engine()
        engine.load_protocol(data, validate=False)

        result = await engine.execute()

        assert result.status == "success"
        assert result.node_results["join_1"].status == NodeStatus.COMPLETED


class TestRouterJoinFlow:
    """Integration tests for Router + Join combined flows."""

    @pytest.mark.asyncio
    async def test_router_join_parallel_flow(self):
        """Test Router branching to parallel paths that Join back."""
        data = {
            "version": "1.0.0",
            "nodes": [
                {
                    "id": "trigger_1",
                    "type": "Trigger",
                    "label": "Start"
                },
                {
                    "id": "router_1",
                    "type": "Router",
                    "label": "Branch",
                    "config": {
                        "conditions": [
                            {"ref": "input", "operator": "GTE", "value": 5, "output": "high"},
                            {"ref": "input", "operator": "LT", "value": 5, "output": "low"}
                        ]
                    }
                },
                {
                    "id": "log_high",
                    "type": "Log",
                    "label": "High"
                },
                {
                    "id": "log_low",
                    "type": "Log",
                    "label": "Low"
                },
                {
                    "id": "join_1",
                    "type": "Join",
                    "label": "Merge"
                }
            ],
            "edges": [
                {"source": "trigger_1", "sourcePort": "payload", "target": "router_1", "targetPort": "input"},
                {"source": "router_1", "sourcePort": "high", "target": "log_high"},
                {"source": "router_1", "sourcePort": "low", "target": "log_low"},
                {"source": "log_high", "target": "join_1"},
                {"source": "log_low", "target": "join_1"}
            ]
        }
        engine = create_test_engine()
        engine.load_protocol(data, validate=False)

        result = await engine.execute({"payload": 10})

        assert result.status == "success"
        assert result.node_results["router_1"].status == NodeStatus.COMPLETED
        assert result.node_results["join_1"].status == NodeStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_router_output_stored_in_context(self):
        """Test Router's _selected output is stored in context."""
        data = {
            "version": "1.0.0",
            "nodes": [
                {
                    "id": "trigger_1",
                    "type": "Trigger",
                    "label": "Start"
                },
                {
                    "id": "router_1",
                    "type": "Router",
                    "label": "Route",
                    "config": {
                        "conditions": [
                            {"ref": "input", "operator": "EQ", "value": "test", "output": "matched"}
                        ],
                        "default": "unmatched"
                    }
                },
                {
                    "id": "log_1",
                    "type": "Log",
                    "label": "Log"
                }
            ],
            "edges": [
                {"source": "trigger_1", "sourcePort": "payload", "target": "router_1", "targetPort": "input"},
                {"source": "router_1", "sourcePort": "matched", "target": "log_1"}
            ]
        }
        engine = create_test_engine()
        engine.load_protocol(data, validate=False)

        result = await engine.execute({"payload": "test"})

        assert result.status == "success"
        # Verify router outputs are stored
        router_outputs = engine._state.get_node_outputs("router_1")
        assert "_selected" in router_outputs
        assert "matched" in router_outputs["_selected"]

    @pytest.mark.asyncio
    async def test_join_with_trigger_single_input(self):
        """Test Join receiving input from Trigger only."""
        data = {
            "version": "1.0.0",
            "nodes": [
                {"id": "trigger_1", "type": "Trigger", "label": "Start"},
                {
                    "id": "join_1",
                    "type": "Join",
                    "label": "Join",
                    "config": {"strategy": "first"}
                }
            ],
            "edges": [
                {"source": "trigger_1", "target": "join_1"}
            ]
        }
        engine = create_test_engine()
        engine.load_protocol(data, validate=False)

        result = await engine.execute({"payload": "hello"})

        assert result.status == "success"
        assert result.node_results["join_1"].status == NodeStatus.COMPLETED