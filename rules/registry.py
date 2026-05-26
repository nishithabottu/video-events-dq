from dataclasses import dataclass
from typing import Callable

REGISTRY = []                                # ← Where every rule lives

@dataclass
class Rule:
    id: str                                  # ← Unique name (e.g. "UNIQ_001")
    category: str                            # ← Schema, Enum, Nullability, etc.
    severity: str                            # ← critical / warning / info
    description: str
    downstream_impact: str                   # ← Which dashboard/metric breaks
    check: Callable                          # ← The function that finds bad rows

def register_rule(id, category, severity, description, downstream_impact):
    def decorator(func):                     # ← Wraps the check function
        REGISTRY.append(Rule(
            id=id, category=category, severity=severity,
            description=description, downstream_impact=downstream_impact,
            check=func
        ))
        return func
    return decorator

if __name__ == '__main__':
    print(f"Registry has {len(REGISTRY)} rules")   # ← Should be 0 (no rules yet)
