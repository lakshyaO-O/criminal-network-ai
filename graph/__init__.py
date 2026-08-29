"""Graph analysis module for criminal network analysis.

Provides network construction and analysis over the canonical
entity/relationship model. Optional submodules are imported lazily so a
partial implementation never breaks package import.
"""

from . import graph_construction

try:  # optional, may not exist in early milestones
    from . import community_detection  # noqa: F401
except ImportError:
    community_detection = None  # type: ignore[assignment]

try:  # optional, may not exist in early milestones
    from . import path_analysis  # noqa: F401
except ImportError:
    path_analysis = None  # type: ignore[assignment]

__all__ = [
    "graph_construction",
    "community_detection",
    "path_analysis",
]
