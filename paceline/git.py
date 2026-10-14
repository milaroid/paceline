"""Git state for the working folder, cached so a once-per-second refresh stays cheap."""

import subprocess

from store import load, save

GIT_TTL = 5


def _git(cwd, *args):
    try:
        out = subprocess.run(["git", "-C", cwd] + list(args),
                             capture_output=True, text=True, timeout=1.0)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def _ahead_behind(cwd):
    counts = _git(cwd, "rev-list", "--count", "--left-right", "@{u}...HEAD")
    if not counts or "\t" not in counts:
        return 0, 0
    left, right = counts.split("\t")[:2]
    return int(right or 0), int(left or 0)


def compute(cwd, worktree):
    """Branch, detached flag, dirty count, ahead and behind counts for cwd, or None outside a repo."""
    branch = _git(cwd, "symbolic-ref", "--short", "HEAD")
    detached = branch is None
    if detached:
        branch = _git(cwd, "rev-parse", "--short", "HEAD")
        if branch is None:
            return None
    porcelain = _git(cwd, "status", "--porcelain") or ""
    ahead, behind = _ahead_behind(cwd)
    return {"branch": branch, "detached": detached,
            "dirty": len([ln for ln in porcelain.splitlines() if ln.strip()]),
            "ahead": ahead, "behind": behind, "worktree": worktree}


def info(cwd, worktree, cache_path, now):
    """Git state for cwd, computed at most once per GIT_TTL seconds and cached at cache_path."""
    if not cwd:
        return None
    cache = load(cache_path)
    entry = cache.get(cwd)
    if isinstance(entry, dict) and isinstance(entry.get("ts"), (int, float)) \
            and 0 <= now - entry["ts"] < GIT_TTL:
        return entry.get("data")
    data = compute(cwd, worktree)
    cache[cwd] = {"ts": now, "data": data}
    save(cache_path, cache)
    return data
