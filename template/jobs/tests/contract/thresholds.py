"""Pass thresholds for the connector contract suite, fixed before the first scenario ran (2026-11-25).

Every scenario asserts its observations against these numbers. Change one only with a reason in the
commit message: loosening a threshold to make a failing implementation pass defeats the suite.

Times are virtual seconds on the test clock. Each synthetic provider call costs PROVIDER_LATENCY_S.
"""

# --- Cost model of the synthetic world ---------------------------------------------------------
PROVIDER_LATENCY_S = 1.0  # every provider call advances the clock by this much

# --- Leases and heartbeats ---------------------------------------------------------------------
LEASE_S = 60.0
HEARTBEAT_FRACTION = 0.5  # heartbeat once less than this fraction of the lease is left

# --- Bounded retries (scenario 4) ---------------------------------------------------------------
MAX_ATTEMPTS = 5  # transient failures (timeout, 5xx) per run before it fails for good
MIN_RETRY_DELAY_S = 1.0  # no retry is ever scheduled sooner than this: no busy loop
RETRY_BASE_S = 2.0
RETRY_CAP_S = 300.0
RATE_LIMIT_DEFAULT_S = 30.0  # a 429 without Retry-After waits at least this long
MAX_RATE_LIMIT_WAITS = 10  # 429s per run before it fails as rate_limit_exhausted
RATE_LIMIT_JITTER_FRACTION = 0.2  # a 429 waits Retry-After plus at most this fraction of it

# --- Crash loops (scenario 2) -------------------------------------------------------------------
MAX_CLAIMS_PER_RUN = 25  # a run claimed this many times without finishing fails boundedly

# --- Reports (scenario 7) -----------------------------------------------------------------------
REPORT_POLL_INTERVAL_S = 30.0
MAX_REPORT_POLLS = 20
MAX_REPORT_REQUESTS_PER_RUN = 1  # never re-requested

# --- Fairness (scenario 6) ----------------------------------------------------------------------
BACKFILL_PAGES_PER_CLAIM = 5  # a backfill yields its stream after this many pages
MAX_INCREMENTAL_WALL_S_DURING_BACKFILL = 30.0  # enqueue to succeeded, while a backfill runs

# --- Pause (scenario 10) ------------------------------------------------------------------------
PAUSE_RECHECK_S = 300.0
MAX_PROVIDER_CALLS_WHILE_PAUSED = 0

# --- Global guards ------------------------------------------------------------------------------
MAX_PROVIDER_CALLS_PER_SCENARIO = 400
MAX_WORKER_STEPS_PER_SCENARIO = 500  # executions the fake engine runs before declaring a busy loop
MAX_MASS_DELETION = 0  # records deleted by a run whose snapshot was not complete
