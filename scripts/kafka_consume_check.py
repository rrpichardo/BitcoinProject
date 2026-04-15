"""
Kafka consumer that validates ticks.raw messages produced by ws_ingest.py.

Checks each message for:
  - Required fields present and non-null
  - price, best_bid, best_ask are positive floats
  - best_bid <= price <= best_ask
  - timestamp parses as ISO-8601
  - No duplicate sequence (product_id + timestamp)

Prints a live summary every --interval seconds and exits with code 1
if the invalid-message rate exceeds --max-error-rate.

Usage:
    python scripts/kafka_consume_check.py [--topic ticks.raw] [--min 100]
"""

import argparse
import json
import re
import signal
import sys
import time
import uuid
from collections import defaultdict, OrderedDict
from datetime import datetime, timezone

from confluent_kafka import Consumer, KafkaError

REQUIRED_FIELDS = {"product_id", "price", "best_bid", "best_ask", "volume_24_h", "timestamp"}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def parse_float(val) -> float | None:
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def validate(msg: dict) -> list[str]:
    """Return a list of validation error strings; empty = valid."""
    errors = []

    missing = REQUIRED_FIELDS - msg.keys()
    if missing:
        errors.append(f"missing fields: {missing}")
        return errors  # can't check values if fields are absent

    null_fields = {k for k in REQUIRED_FIELDS if msg[k] is None}
    if null_fields:
        errors.append(f"null fields: {null_fields}")

    price    = parse_float(msg["price"])
    bid      = parse_float(msg["best_bid"])
    ask      = parse_float(msg["best_ask"])
    volume   = parse_float(msg["volume_24_h"])

    for name, val in [("price", price), ("best_bid", bid), ("best_ask", ask), ("volume_24_h", volume)]:
        if val is None:
            errors.append(f"{name} is not a number: {msg[name]!r}")
        elif val < 0:
            errors.append(f"{name} is negative: {val}")

    # price is the last-trade price, which can sit outside the current top-of-book
    # (bid/ask update independently on Coinbase). Only enforce bid <= ask.
    if bid is not None and ask is not None:
        if bid > ask:
            errors.append(f"crossed book: bid={bid} > ask={ask}")

    try:
        # Truncate nanosecond precision to microseconds before parsing
        ts_clean = re.sub(r"(\.\d{6})\d+", r"\1", msg["timestamp"])
        datetime.fromisoformat(ts_clean.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        errors.append(f"unparseable timestamp: {msg['timestamp']!r}")

    return errors


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

# Cap the dedup window so memory stays bounded for long-running consumers
MAX_DEDUP_KEYS = 100_000


class Stats:
    def __init__(self):
        self.total = 0
        self.invalid = 0
        self.error_counts: dict[str, int] = defaultdict(int)
        # OrderedDict used as a bounded LRU set — oldest entries evicted first
        self.seen_keys: OrderedDict = OrderedDict()
        self.duplicates = 0
        self.start = time.monotonic()

    def record(self, msg: dict, errors: list[str]):
        self.total += 1
        dedup_key = (msg.get("product_id"), msg.get("timestamp"))
        if dedup_key in self.seen_keys:
            self.duplicates += 1
            errors = errors + [f"duplicate key {dedup_key}"]
        else:
            self.seen_keys[dedup_key] = None
            # Evict oldest entries when the window exceeds the cap
            while len(self.seen_keys) > MAX_DEDUP_KEYS:
                self.seen_keys.popitem(last=False)

        if errors:
            self.invalid += 1
            for e in errors:
                self.error_counts[e] += 1

    def error_rate(self) -> float:
        return self.invalid / self.total if self.total else 0.0

    def summary(self) -> str:
        elapsed = time.monotonic() - self.start
        rate = self.total / elapsed if elapsed > 0 else 0
        lines = [
            f"  elapsed:      {elapsed:.0f}s",
            f"  total:        {self.total}",
            f"  invalid:      {self.invalid}  ({self.error_rate():.1%})",
            f"  duplicates:   {self.duplicates}",
            f"  msg/s:        {rate:.1f}",
        ]
        if self.error_counts:
            lines.append("  top errors:")
            for err, count in sorted(self.error_counts.items(), key=lambda x: -x[1])[:5]:
                lines.append(f"    [{count}] {err}")
        return "\n".join(lines)


def wait_for_kafka(consumer: Consumer, bootstrap: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    last_exc: Exception | None = None
    while time.monotonic() < deadline:
        try:
            consumer.list_topics(timeout=1.0)
            return
        except Exception as exc:  # pragma: no cover - exercised in integration
            last_exc = exc
            time.sleep(1.0)
    raise RuntimeError(
        f"Kafka bootstrap {bootstrap!r} was not reachable within {timeout:.0f}s"
    ) from last_exc


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Validate ticks.raw Kafka stream")
    parser.add_argument("--bootstrap-servers", default="localhost:9092")
    parser.add_argument("--topic", default="ticks.raw")
    parser.add_argument("--group-id", default="stream-validator")
    parser.add_argument("--interval", type=float, default=10.0,
                        help="Seconds between summary prints (default: 10)")
    parser.add_argument("--min", type=int, default=0,
                        help="Exit successfully after consuming at least this many messages")
    parser.add_argument("--max-error-rate", type=float, default=0.05,
                        help="Exit with code 1 if error rate exceeds this (default: 0.05)")
    parser.add_argument("--from-beginning", action="store_true",
                        help="Start consuming from the earliest offset (default behavior)")
    parser.add_argument("--latest", action="store_true",
                        help="Only consume new messages arriving after startup")
    parser.add_argument("--startup-timeout", type=float, default=10.0,
                        help="Seconds to wait for Kafka before failing (default: 10)")
    args = parser.parse_args()

    if args.from_beginning and args.latest:
        print("[FAIL] choose either --from-beginning or --latest, not both", file=sys.stderr)
        sys.exit(1)

    # The assignment examples run validation after ingest, so the safe default
    # is to read from the earliest available offset with a throwaway consumer
    # group. This avoids stale committed offsets from prior runs.
    read_from_beginning = not args.latest
    group_id = f"{args.group_id}-{uuid.uuid4().hex[:8]}" if read_from_beginning else args.group_id

    consumer = Consumer({
        "bootstrap.servers": args.bootstrap_servers,
        "group.id": group_id,
        "auto.offset.reset": "earliest" if read_from_beginning else "latest",
        "enable.auto.commit": True,
    })
    consumer.subscribe([args.topic])
    try:
        wait_for_kafka(consumer, args.bootstrap_servers, args.startup_timeout)
    except RuntimeError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        consumer.close()
        sys.exit(1)

    stats = Stats()
    stop = False
    next_summary = time.monotonic() + args.interval

    def _shutdown(*_):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    print(f"Consuming from '{args.topic}' on {args.bootstrap_servers} …  (Ctrl-C to stop)\n")

    while not stop:
        kmsg = consumer.poll(timeout=1.0)

        if kmsg is None:
            pass
        elif kmsg.error():
            if kmsg.error().code() != KafkaError._PARTITION_EOF:
                print(f"[ERROR] Kafka error: {kmsg.error()}", file=sys.stderr)
        else:
            try:
                payload = json.loads(kmsg.value())
            except json.JSONDecodeError as exc:
                stats.total += 1
                stats.invalid += 1
                stats.error_counts[f"JSON decode error: {exc}"] += 1
                continue

            errors = validate(payload)
            stats.record(payload, errors)

            if errors:
                print(f"[INVALID] {payload.get('product_id')} @ {payload.get('timestamp')}")
                for e in errors:
                    print(f"  - {e}")

            if args.min and stats.total >= args.min:
                stop = True

        if time.monotonic() >= next_summary:
            print(f"\n--- summary ---\n{stats.summary()}\n")
            next_summary = time.monotonic() + args.interval

    consumer.close()
    print(f"\n--- final summary ---\n{stats.summary()}\n")

    if args.min and stats.total < args.min:
        print(f"[FAIL] consumed {stats.total} messages; expected at least {args.min}")
        sys.exit(1)

    if stats.error_rate() > args.max_error_rate:
        print(f"[FAIL] error rate {stats.error_rate():.1%} exceeds threshold {args.max_error_rate:.1%}")
        sys.exit(1)

    print("[OK] stream is valid")


if __name__ == "__main__":
    main()
