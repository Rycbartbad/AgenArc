from agenarc.protocol.loader import ProtocolLoader
from pathlib import Path

# Test 1: Direct load_file
l = ProtocolLoader()
l._parent_path = Path("examples/my_first_agent.agrc")
print(f"parent_path set to: {l._parent_path}")
print(f"parent_path is_dir: {l._parent_path.is_dir()}")
print(f"sub/euchea exists: {(l._parent_path / 'sub' / 'euchea.agrc').exists()}")

# Test 2: Try the resolution
try:
    p = l._resolve_bundle_ref("euchea.agrc", l._parent_path)
    print(f"Resolved bundle: {p}")
except Exception as e:
    print(f"Resolve error: {e}")

# Test 3: Test actual port resolution
print("\n--- Testing port resolution ---")
l2 = ProtocolLoader()
result = l2.load_file("examples/my_first_agent.agrc")
for n in result.nodes:
    if n.type.value == "SubGraph":
        print(f"SubGraph {n.id}: inputs=[{','.join(p.name for p in n.inputs)}], outputs=[{','.join(p.name for p in n.outputs)}]")
