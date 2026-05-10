"""Debug: simulate frontend add/delete node then execute."""
from agenarc.engine.executor import ExecutionEngine
from agenarc.operators.builtin import BUILTIN_OPERATORS
from agenarc.visualization.server import VisualizationServer
from agenarc.protocol.schema import Graph, Node, NodeConfig, NodeType, Edge
from agenarc.graph.traversal import GraphTraversal
import asyncio, json

engine = ExecutionEngine()
for t, c in BUILTIN_OPERATORS.items():
    if c:
        engine.register_builtin_operator(t, c)
engine.load_protocol("examples/my_first_agent.agrc")

async def run_one(msg, label):
    result = await engine.execute({"payload": msg}, mode="sync")
    desc = result.final_outputs.get("response", "no-response")[:50] if result.final_outputs else "none"
    print(f"[{label}] status={result.status}, duration={result.duration_ms:.0f}ms, response={desc}")
    return result

async def main():
    # First execution — should work
    r1 = await run_one("你好", "first")
    
    # Simulate add/delete: saveGraph -> _save_graph rebuilds engine graph
    # Same data as frontend sends
    data = {
        "nodes": [
            {"id": "trigger_1", "type": "Trigger", "label": "入口", "config": {}},
            {"id": "pb_user", "type": "Prompt_Builder", "label": "用户输入", "config": {"history": "chat_history"}},
            {"id": "llm_1", "type": "LLM_Task", "label": "LLM 处理", "config": {"model": "", "system_prompt": ""}},
            {"id": "pb_assistant", "type": "Prompt_Builder", "label": "助理响应", "config": {"history": "chat_history"}},
            {"id": "log_1", "type": "Log", "label": "日志", "config": {}},
        ],
        "edges": [
            {"s": "trigger_1", "sp": "payload", "t": "pb_user", "tp": "user", "flowType": "data"},
            {"s": "pb_user", "sp": "messages", "t": "llm_1", "tp": "messages", "flowType": "data"},
            {"s": "llm_1", "sp": "response", "t": "pb_assistant", "tp": "assistant", "flowType": "data"},
            {"s": "llm_1", "sp": "response", "t": "log_1", "tp": "message", "flowType": "data"},
            {"s": "pb_assistant", "t": "trigger_1", "flowType": "control"},
        ],
    }
    
    # Rebuild graph (like _save_graph does)
    type_map = {t.value: t for t in NodeType}
    converted_nodes = []
    for n in data["nodes"]:
        ntype = type_map.get(n.get("type", ""))
        if not ntype: continue
        converted_nodes.append(Node(id=n["id"], type=ntype, label=n.get("label", n["id"]), config=NodeConfig(data=n.get("config", {}))))
    
    from collections import defaultdict
    by_pair = defaultdict(list)
    for e in data["edges"]:
        by_pair[(e["s"], e["t"])].append(e)
    
    converted_edges = []
    for (src, tgt), pair in by_pair.items():
        de = next((e for e in pair if e.get("flowType") == "data"), None)
        if de:
            converted_edges.append(Edge(source=src, sourcePort=de.get("sp", ""), target=tgt, targetPort=de.get("tp", "")))
        else:
            ce = next((e for e in pair if e.get("flowType") == "control"), None)
            if ce:
                converted_edges.append(Edge(source=src, target=tgt))
    
    new_graph = Graph(version=engine._graph.version if engine._graph else "1.0.0", nodes=converted_nodes, edges=converted_edges)
    engine._graph = new_graph
    engine._traversal = GraphTraversal(new_graph)
    
    # Second execution — does it work?
    r2 = await run_one("你是谁", "after-add-delete")
    
    print(f"\nFirst execution: {'OK' if 'Hello' in str(r1.final_outputs) else 'EMPTY'}")
    print(f"Second execution: {'OK' if r2.duration_ms > 100 else '0ms bug - no real execution'}")

asyncio.run(main())
