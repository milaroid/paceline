"""Pace math: end-of-window projection and the runway clock."""

PROJECTION_FLOOR = 0.02
SAMPLE_EVERY = 30
MIN_SPAN = 60
MAX_PROJECTION = 999


def project(used, resets_at, window, now):
    """Projected usage at window end from the share of the window already gone.

    Returns None when a value is missing or when less than 2% of the window has gone.
    """
    if used is None or not resets_at or not window:
        return None
    elapsed = window - (float(resets_at) - now)
    if elapsed <= window * PROJECTION_FLOOR:
        return None
    return min(used * window / elapsed, MAX_PROJECTION)


def record(samples, used, now, horizon):
    """samples with a new [now, used] point and points older than horizon seconds removed.

    A point is added when the value changed or SAMPLE_EVERY seconds have gone since the last one.
    """
    kept = [s for s in samples if s[0] >= now - horizon]
    if not kept or kept[-1][1] != used or now - kept[-1][0] >= SAMPLE_EVERY:
        kept.append([now, used])
    return kept


def burn_rate(samples, now, horizon):
    """Usage percent per second over the last horizon seconds, or None.

    None when the samples span less than MIN_SPAN seconds or usage did not rise.
    """
    recent = [s for s in samples if s[0] >= now - horizon]
    if len(recent) < 2:
        return None
    span = recent[-1][0] - recent[0][0]
    if span < MIN_SPAN:
        return None
    rate = (recent[-1][1] - recent[0][1]) / span
    return rate if rate > 0 else None


def runway(window, samples, now, horizon):
    """Seconds until window reaches 100% at the recent burn, or None.

    Shown only when the projection passes 100% and the limit hits before the reset.
    """
    proj = project(window.used, window.resets_at, window.seconds, now)
    if proj is None or proj <= 100:
        return None
    rate = burn_rate(samples, now, horizon)
    if rate is None:
        return None
    secs = (100 - window.used) / rate
    return secs if secs < float(window.resets_at) - now else None


def _expired(key, now):
    try:
        return float(key.rsplit(":", 1)[1]) <= now
    except (IndexError, ValueError):
        return True


def update_runways(store, reading, now, horizon):
    """Record the windows of reading in store and return ({label: runway seconds or None}, changed).

    Samples live under store["runway"], keyed by agent, window label, and reset time,
    so a new window starts with no samples. Keys of windows that have reset are removed.
    """
    samples = store.get("runway")
    if not isinstance(samples, dict):
        samples = store["runway"] = {}
    changed = _prune(samples, now)
    out = {}
    for win in reading.windows:
        if win.used is not None and win.resets_at:
            key = "%s:%s:%d" % (reading.agent, win.label, int(win.resets_at))
            new = record(samples.get(key) or [], win.used, now, horizon)
            changed = changed or new != samples.get(key)
            samples[key] = new
            out[win.label] = runway(win, new, now, horizon)
    return out, changed


def _prune(samples, now):
    stale = [k for k in samples if _expired(k, now)]
    for key in stale:
        del samples[key]
    return bool(stale)
