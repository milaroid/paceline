"""The identity line: folder, git branch, pull request, and prompt cache."""

import os

PR_WORDS = {"draft": "draft", "pending": "review", "changes_requested": "changes", "approved": "approved"}


def link(text, url):
    """text wrapped in an OSC 8 hyperlink, or the plain text when url is empty."""
    return "\033]8;;%s\a%s\033]8;;\a" % (url, text) if url else text


def folder(theme, cwd):
    """The current folder name in bold, or None when cwd is unknown."""
    name = os.path.basename(os.path.normpath(cwd)) if cwd else ""
    return "%s%s%s" % (theme.bold, name, theme.reset) if name else None


def repo_url(workspace, branch):
    """The web URL of branch in the origin repository, or None."""
    repo = workspace.get("repo") or {}
    if not (repo.get("host") and repo.get("owner") and repo.get("name") and branch):
        return None
    return "https://%s/%s/%s/tree/%s" % (repo["host"], repo["owner"], repo["name"], branch)


def git_segment(theme, state, url=None):
    """⎇ branch with worktree, dirty, ahead, and behind marks, or None outside a repo."""
    if not state:
        return None
    if state["detached"]:
        head = "%s⎇ %s%s" % (theme.dim, state["branch"], theme.reset)
    else:
        head = link("%s⎇ %s%s" % (theme.accent, state["branch"], theme.reset), url)
    marks = [
        (state.get("worktree"), theme.dim, "⌂%s"),
        (state.get("dirty"), theme.amber, "●%s"),
        (state.get("ahead"), theme.green, "↑%s"),
        (state.get("behind"), theme.red, "↓%s"),
    ]
    extra = [color + (fmt % value) + theme.reset for value, color, fmt in marks if value]
    return " ".join([head] + extra)


def pr_segment(theme, pr):
    """The open pull request as 'PR #6 review', linked to its page, or None."""
    pr = pr or {}
    if not pr.get("number"):
        return None
    state = pr.get("review_state")
    colors = {"pending": theme.amber, "changes_requested": theme.red, "approved": theme.green}
    kind = "MR" if pr.get("kind") == "mr" else "PR"
    text = "%s%s #%s%s" % (theme.accent, kind, pr["number"], theme.reset)
    if state in PR_WORDS:
        text += " %s%s%s" % (colors.get(state, theme.dim), PR_WORDS[state], theme.reset)
    return link(text, pr.get("url"))


def cache_segment(theme, cache):
    """The prompt cache hit ratio: dim while warm, amber once cold. None before caching is seen."""
    cache = cache or {}
    ratio = cache.get("hit_ratio")
    if not cache.get("caching_observed") or ratio is None:
        return None
    color = theme.dim if cache.get("warm") else theme.amber
    return "%scache%s %s%.0f%%%s" % (theme.dim, theme.reset, color, ratio * 100, theme.reset)
