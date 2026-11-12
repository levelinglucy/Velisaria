"""Compatibility imports for existing repository users and regressions.

The larger monolith is now self-contained. Its readable included definitions
are canonical; this facade preserves the previous import path without keeping
a second persistence implementation. The monolith never imports this file.
"""

from velisara_monolith_final_fixed_empathy import (
    SnapshotError, SnapshotLoadError, SnapshotSaveError, SnapshotStore,
    ContinuityState, strict_json_loads, encode_pairs, decode_pairs,
    encode_state, decode_state, os,
)

__all__ = [
    'SnapshotError', 'SnapshotLoadError', 'SnapshotSaveError', 'SnapshotStore',
    'ContinuityState', 'strict_json_loads', 'encode_pairs', 'decode_pairs',
    'encode_state', 'decode_state',
]
