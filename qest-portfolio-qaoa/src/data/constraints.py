from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from itertools import combinations


@dataclass(frozen=True)
class PortfolioConstraints:
    num_to_select: int = 5
    max_per_sector: int = 2

    def is_valid(
        self,
        selected_indices: Iterable[int],
        sector_indices: dict[str, list[int]],
    ) -> tuple[bool, list[str]]:
        selected = list(selected_indices)
        selected_set = set(selected)
        issues: list[str] = []

        if len(selected) != self.num_to_select:
            issues.append(
                f"Selected {len(selected)} stocks instead of {self.num_to_select}."
            )

        for sector, indices in sector_indices.items():
            count = sum(1 for i in indices if i in selected_set)
            if count > self.max_per_sector:
                issues.append(
                    f"Sector {sector} exceeded limit with {count} stocks."
                )

        return len(issues) == 0, issues

    def binding_sectors(self, sector_indices: dict[str, list[int]]) -> dict[str, list[int]]:
        return {
            sector: indices
            for sector, indices in sector_indices.items()
            if len(indices) > self.max_per_sector
        }

    def violation_combinations(
        self, sector_indices: dict[str, list[int]]
    ) -> Iterator[tuple[int, ...]]:
        for indices in self.binding_sectors(sector_indices).values():
            yield from combinations(indices, self.max_per_sector + 1)


DEFAULT_CONSTRAINTS = PortfolioConstraints()
