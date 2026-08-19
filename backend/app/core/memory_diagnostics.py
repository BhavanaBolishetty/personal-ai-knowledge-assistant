import sys


def log_memory(label: str) -> None:
    """Prints the process's peak resident memory so far, tagged with a
    label (e.g. "after_embedding_model_load"). Diagnostic only — no
    behavior depends on this. Uses the stdlib `resource` module (POSIX
    only), so it's a no-op on Windows rather than adding a dependency
    (e.g. psutil) just to debug a memory problem. Printed directly
    (not via `logging`) so it always reaches Render's log stream
    regardless of the app's logging configuration.
    """
    if not sys.platform.startswith("linux"):
        return

    import resource

    peak_rss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    print(f"[memory] {label}: peak RSS {peak_rss_mb:.1f} MB", flush=True)
