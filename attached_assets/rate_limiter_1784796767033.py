"""
Rate limiter for the Ad Library scraper.
Meta actively rate-limits and fingerprints scraping traffic, so this
enforces a minimum delay + random jitter between requests, plus a hard
session budget so a runaway loop can't hammer the site for hours.
"""
import random
import time


class RateLimiter:
    def __init__(self, min_delay_s: float = 4.0, max_delay_s: float = 9.0,
                 max_requests_per_session: int = 40):
        self.min_delay_s = min_delay_s
        self.max_delay_s = max_delay_s
        self.max_requests_per_session = max_requests_per_session
        self.request_count = 0
        self._last_request_ts = None

    def wait(self):
        """Call this immediately before each page.goto / scroll action."""
        if self.request_count >= self.max_requests_per_session:
            raise SessionBudgetExceeded(
                f"Hit session budget of {self.max_requests_per_session} requests. "
                "Stop and start a fresh browser context/session rather than continuing."
            )
        delay = random.uniform(self.min_delay_s, self.max_delay_s)
        time.sleep(delay)
        self.request_count += 1
        self._last_request_ts = time.time()
        return delay


class SessionBudgetExceeded(Exception):
    pass


if __name__ == "__main__":
    # self-test: confirm budget enforcement fires exactly at the limit,
    # and delay values stay in the configured range across many draws
    rl = RateLimiter(min_delay_s=0.01, max_delay_s=0.02, max_requests_per_session=5)
    delays = []
    for i in range(5):
        d = rl.wait()
        delays.append(d)
        assert 0.01 <= d <= 0.02, f"delay {d} out of range"

    try:
        rl.wait()
        raise AssertionError("Expected SessionBudgetExceeded to fire on the 6th call")
    except SessionBudgetExceeded:
        pass

    print(f"Request count after budget test: {rl.request_count}")
    print(f"Delay samples: {[round(d, 4) for d in delays]}")
    print("Rate limiter tests passed.")
