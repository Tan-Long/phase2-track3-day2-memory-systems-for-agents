from agent.state import MemoryState, make_initial_state


class SkeletonGraph:
    def __init__(self):
        self._nodes: dict[str, callable] = {}
        self._edges: list[tuple[str, str]] = []
        self._entry_point: str | None = None
        self._node_order: list[str] = []

    def add_node(self, name: str, func: callable) -> None:
        self._nodes[name] = func
        self._node_order.append(name)

    def add_edge(self, from_node: str, to_node: str) -> None:
        self._edges.append((from_node, to_node))

    def set_entry_point(self, name: str) -> None:
        self._entry_point = name

    def run(self, state: MemoryState, **kwargs) -> MemoryState:
        order = self._resolve_order()
        for node_name in order:
            func = self._nodes[node_name]
            state = func(state, **kwargs)
        return state

    def _resolve_order(self) -> list[str]:
        if self._edges:
            order = [self._entry_point] if self._entry_point else [self._edges[0][0]]
            current = order[0]
            visited = {current}
            while True:
                next_node = None
                for src, dst in self._edges:
                    if src == current and dst not in visited:
                        next_node = dst
                        break
                if next_node is None:
                    break
                order.append(next_node)
                visited.add(next_node)
                current = next_node
            return order
        return self._node_order