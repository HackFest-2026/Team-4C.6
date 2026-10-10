from typing import List, Dict, Any, Set, Tuple
from collections import defaultdict, deque


class CircularDependencyError(Exception):
    """Raised when circular dependencies exist between features."""
    pass


class DependencyGraph:
    """
    Validates and analyzes dependencies between features using Directed Acyclic Graphs (DAG).
    Calculates upstream/downstream nodes, topological sort, graph depth, and critical path.
    """

    def __init__(self, features: List[Dict[str, Any]]):
        self.features = features
        self.feature_map = {}
        for f in features:
            f_id = str(f.get("id") or f.get("name") or f.get("feature_name"))
            self.feature_map[f_id] = f

        self.adj_list: Dict[str, List[str]] = defaultdict(list)
        self.in_degree: Dict[str, int] = defaultdict(int)
        self.all_nodes: Set[str] = set(self.feature_map.keys())

        for node in self.all_nodes:
            self.in_degree[node] = 0

        self._build_graph()

    def _build_graph(self) -> None:
        for node_id, f in self.feature_map.items():
            deps = f.get("dependencies", []) or []
            for dep in deps:
                dep_id = str(dep)
                if dep_id in self.all_nodes and dep_id != node_id:
                    self.adj_list[dep_id].append(node_id)
                    self.in_degree[node_id] += 1

    def detect_cycles(self) -> List[str]:
        """
        Uses Kahn's algorithm to detect cycles.
        Returns a non-empty list of cyclic nodes if a cycle exists.
        """
        in_deg = dict(self.in_degree)
        queue = deque([node for node in self.all_nodes if in_deg[node] == 0])
        visited_count = 0

        while queue:
            curr = queue.popleft()
            visited_count += 1
            for neighbor in self.adj_list[curr]:
                in_deg[neighbor] -= 1
                if in_deg[neighbor] == 0:
                    queue.append(neighbor)

        if visited_count < len(self.all_nodes):
            cyclic_nodes = [node for node, deg in in_deg.items() if deg > 0]
            return cyclic_nodes
        return []

    def validate(self) -> None:
        """Validates that the graph is an acyclic DAG. Raises CircularDependencyError if not."""
        cyclic_nodes = self.detect_cycles()
        if cyclic_nodes:
            raise CircularDependencyError(
                f"Circular dependency detected involving features: {cyclic_nodes}. "
                f"Please ensure features do not depend on each other directly or indirectly."
            )

    def calculate_critical_path(self, effort_key: str = "expected_effort_hours") -> Tuple[float, List[str], int]:
        """
        Calculates the longest path through the DAG (Critical Path) in hours.
        Returns (critical_path_hours, critical_path_nodes, max_graph_depth).
        """
        self.validate()

        # Topological sort
        in_deg = dict(self.in_degree)
        queue = deque([node for node in self.all_nodes if in_deg[node] == 0])
        topo_order = []

        while queue:
            curr = queue.popleft()
            topo_order.append(curr)
            for neighbor in self.adj_list[curr]:
                in_deg[neighbor] -= 1
                if in_deg[neighbor] == 0:
                    queue.append(neighbor)

        # Longest path dynamic programming
        earliest_finish: Dict[str, float] = {}
        depth: Dict[str, int] = {}
        predecessor: Dict[str, str] = {}

        for node in self.all_nodes:
            feat = self.feature_map[node]
            hours = float(feat.get(effort_key, feat.get("most_likely_effort_hours", 16.0)))
            earliest_finish[node] = hours
            depth[node] = 1
            predecessor[node] = None

        for curr in topo_order:
            curr_finish = earliest_finish[curr]
            curr_depth = depth[curr]
            for neighbor in self.adj_list[curr]:
                neigh_hours = float(
                    self.feature_map[neighbor].get(effort_key, self.feature_map[neighbor].get("most_likely_effort_hours", 16.0))
                )
                if curr_finish + neigh_hours > earliest_finish[neighbor]:
                    earliest_finish[neighbor] = curr_finish + neigh_hours
                    predecessor[neighbor] = curr
                if curr_depth + 1 > depth[neighbor]:
                    depth[neighbor] = curr_depth + 1

        if not earliest_finish:
            return 0.0, [], 0

        # Find terminal node with max finish time
        crit_end_node = max(earliest_finish.keys(), key=lambda k: earliest_finish[k])
        crit_hours = earliest_finish[crit_end_node]
        max_depth = max(depth.values()) if depth else 0

        # Backtrack critical path
        path = []
        curr = crit_end_node
        while curr:
            path.append(curr)
            curr = predecessor[curr]
        path.reverse()

        return round(crit_hours, 1), path, max_depth
