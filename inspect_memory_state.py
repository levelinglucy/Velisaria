#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only, local inspection of two Velisaria memory generations.

Reports structural validity and session-prefix relationships, never session
contents. It does not choose, repair, copy, rename or delete either file.
Use on owner-made *copies* in an isolated directory. See DEV_NOTES.md.
"""
import argparse
import json
import os
import stat

MAX_BYTES = 32 * 1024 * 1024


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("non-standard JSON constant")


def _json_number_token(token):
    """Keep number spelling and type distinct for conservative copy comparisons.

    No JSON value becomes a Python tuple, so tagged tuples cannot collide
    with JSON strings, booleans, arrays or objects when comparing histories.
    """
    return ("json-number", token)


def _inspect(path):
    """Return metadata and a private decoded value, without writing anything."""
    try:
        before = os.lstat(path)
    except FileNotFoundError:
        return {"status": "absent"}, None
    except OSError:
        return {"status": "unreadable"}, None

    # Reject links, directories, sockets and devices even when an ordinary
    # open might follow or block on them. O_NOFOLLOW closes the final-link race.
    if not stat.S_ISREG(before.st_mode):
        return {"status": "not_regular_file"}, None
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        return {"status": "no_safe_open_support"}, None

    flags = os.O_RDONLY | nofollow | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(path, flags)
        with os.fdopen(fd, "rb") as src:
            first = os.fstat(src.fileno())
            if not stat.S_ISREG(first.st_mode):
                return {"status": "not_regular_file"}, None
            if (before.st_dev, before.st_ino) != (first.st_dev, first.st_ino):
                return {"status": "changed_during_open"}, None
            if first.st_size > MAX_BYTES:
                return {"status": "too_large"}, None
            raw = src.read(MAX_BYTES + 1)
            last = os.fstat(src.fileno())
    except OSError:
        return {"status": "unreadable"}, None

    if len(raw) > MAX_BYTES:
        return {"status": "too_large"}, None
    # A concurrent writer can change either generation while inspecting it.
    # Do not present a detected changing file as validated recovery evidence.
    attrs = ("st_dev", "st_ino", "st_size", "st_mtime_ns")
    if any(getattr(first, a) != getattr(last, a) for a in attrs):
        return {"status": "changed_during_read"}, None

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
            parse_int=_json_number_token,
            parse_float=_json_number_token,
        )
    except (UnicodeError, ValueError, RecursionError):
        return {"status": "invalid_json"}, None
    if not isinstance(value, dict) or not isinstance(value.get("sessions"), list):
        return {"status": "invalid_shape"}, None
    return {"status": "valid", "sessions": len(value["sessions"])}, value


def inspect(state_path):
    """Summarise copied state and adjacent .tmp without exposing records."""
    primary, p = _inspect(state_path)
    temporary, t = _inspect(state_path + ".tmp")

    if primary["status"] == "absent" and temporary["status"] == "absent":
        relation = "nothing_found"
    elif primary["status"] == "valid" and temporary["status"] == "absent":
        relation = "primary_only"
    elif primary["status"] == "absent" and temporary["status"] == "valid":
        relation = "temporary_only"
    elif primary["status"] != "valid" or temporary["status"] != "valid":
        relation = "undetermined"
    elif p == t:
        relation = "equivalent_data"
    else:
        # Unknown top-level fields can carry data; do not report a clean
        # extension when metadata differs.
        p_other = {k: v for k, v in p.items() if k != "sessions"}
        t_other = {k: v for k, v in t.items() if k != "sessions"}
        ps, ts = p["sessions"], t["sessions"]
        if p_other != t_other:
            relation = "divergent"
        elif len(ps) < len(ts) and ps == ts[:len(ps)]:
            relation = "primary_sessions_prefix_of_temporary"
        elif len(ts) < len(ps) and ts == ps[:len(ts)]:
            relation = "temporary_sessions_prefix_of_primary"
        else:
            relation = "divergent"

    return {
        "primary": primary, "temporary": temporary, "relationship": relation,
        "decision": "inspection_only_no_recovery_authorized",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Inspect COPIES of local Velisaria state and its .tmp; no writes."
    )
    parser.add_argument("--state", default="sanctified_state.json",
                        help="path to the copied primary state (default: sanctified_state.json)")
    args = parser.parse_args(argv)
    print(json.dumps(inspect(args.state), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
