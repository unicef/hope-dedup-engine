from collections import defaultdict

from constance import config


class DuplicateGroupsBuilder:
    @staticmethod
    def build(checked: set[tuple[str, str, float]]) -> list[list[str]]:
        """
        Transform a set of tuples with distances into a tuple of grouped duplicate paths.

        Args:
            checked (set[tuple[str, str, float]]): A set of tuples containing the paths and their distances.

        Returns:
            list[list[str]]: A list of grouped duplicate paths.
        """
        # Dictionary to store connections between paths where distances are less than the threshold
        groups = []
        connections = defaultdict(set)
        for path1, path2, dist in checked:
            if dist < config.FACE_DISTANCE_THRESHOLD:
                connections[path1].add(path2)
                connections[path2].add(path1)
        # Iterate over each path and form groups
        for path, neighbors in connections.items():
            # Check if the path has already been included in any group
            if not any(path in group for group in groups):
                new_group = {path}
                queue = list(neighbors)
                # Try to expand the group ensuring each new path is duplicated to all in the group
                while queue:
                    neighbor = queue.pop(0)
                    if neighbor not in new_group and all(
                        neighbor in connections[member] for member in new_group
                    ):
                        new_group.add(neighbor)
                        # Add neighbors of the current neighbor, excluding those already in the group
                        queue.extend(
                            [n for n in connections[neighbor] if n not in new_group]
                        )
                # Add the newly formed group to the list of groups
                groups.append(new_group)
        return list(map(list, groups))
