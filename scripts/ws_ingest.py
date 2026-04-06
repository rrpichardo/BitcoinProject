"""
WebSocket ingestor — streams Coinbase ticker data into Kafka topic ticks.raw.

Two concurrent tasks run per invocation:
  • ticker    — price/volume updates → Kafka + optional file mirror
  • heartbeats — keeps the connection alive; tracks counter to detect gaps

Usage:
    python scripts/ws_ingest.py [--pair BTC-USD] [--minutes 0] [--no-mirror]
"""

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path

from confluent_kafka import Producer
from dotenv import load_dotenv
import websockets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

WS_URL = "wss://advanced-trade-ws.coinbase.com"
load_dotenv()

KAFKA_BOOTSTRAP = (
    os.getenv("KAFKA_BOOTSTRAP")
    or os.getenv("KAFKA_BOOTSTRAP_SERVERS")
    or "localhost:9092"
)
TOPIC = "ticks.raw"
BACKOFF_MIN = 0.5
BACKOFF_MAX = 60.0


# ---------------------------------------------------------------------------
# Kafka helpers
# ---------------------------------------------------------------------------

def make_producer() -> Producer:
    return Producer({"bootstrap.servers": KAFKA_BOOTSTRAP})


def delivery_report(err, msg):
    if err:
        log.error("Delivery failed for %s: %s", msg.key(), err)


# ---------------------------------------------------------------------------
# File mirror helper
# ---------------------------------------------------------------------------

def mirror_paths(pair: str) -> list[Path]:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    paths = [
        Path("data/raw") / f"{pair}_{today}.ndjson",
        Path("data/raw") / pair / f"{today}.ndjson",
    ]
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
    return paths


def mirror_tick(pair: str, value: str) -> None:
    for path in mirror_paths(pair):
        with path.open("a") as fh:
            fh.write(value + "\n")


# ---------------------------------------------------------------------------
# Heartbeat task
# ---------------------------------------------------------------------------

async def heartbeat_task(pair: str, stop_event: asyncio.Event):
    """Subscribe to the heartbeats channel and track sequence gaps."""
    channel = "heartbeats"
    subscribe_msg = json.dumps({
        "type": "subscribe",
        "product_ids": [pair],
        "channel": channel,
    })

    backoff = BACKOFF_MIN
    last_seq: int | None = None

    try:
        while not stop_event.is_set():
            try:
                async for ws in websockets.connect(WS_URL):
                    try:
                        await ws.send(subscribe_msg)
                        log.info("[heartbeats] subscribed for %s", pair)
                        backoff = BACKOFF_MIN  # reset on successful connect

                        async for raw in ws:
                            if stop_event.is_set():
                                return

                            msg = json.loads(raw)
                            if msg.get("channel") != channel:
                                continue

                            seq = msg.get("sequence_num")
                            if seq is not None:
                                if last_seq is not None and seq != last_seq + 1:
                                    log.warning(
                                        "[heartbeats] gap detected: expected %d, got %d",
                                        last_seq + 1,
                                        seq,
                                    )
                                last_seq = seq

                    except websockets.ConnectionClosed as exc:
                        log.warning("[heartbeats] connection closed: %s — reconnecting in %.1fs", exc, backoff)
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * 2, BACKOFF_MAX)

            except Exception as exc:
                log.error("[heartbeats] unexpected error: %s — reconnecting in %.1fs", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, BACKOFF_MAX)
    except asyncio.CancelledError:
        return


# ---------------------------------------------------------------------------
# Ticker task
# ---------------------------------------------------------------------------

async def ticker_task(
    pair: str,
    producer: Producer,
    stop_event: asyncio.Event,
    mirror: bool,
):
    """Subscribe to the ticker channel; produce each tick to Kafka."""
    channel = "ticker"
    subscribe_msg = json.dumps({
        "type": "subscribe",
        "product_ids": [pair],
        "channel": channel,
    })

    backoff = BACKOFF_MIN

    try:
        while not stop_event.is_set():
            try:
                async for ws in websockets.connect(WS_URL):
                    try:
                        await ws.send(subscribe_msg)
                        log.info("[ticker] subscribed for %s → topic '%s'", pair, TOPIC)
                        backoff = BACKOFF_MIN

                        async for raw in ws:
                            if stop_event.is_set():
                                return

                            msg = json.loads(raw)
                            if msg.get("channel") != channel:
                                continue

                            ts = msg.get("timestamp", "")
                            for event in msg.get("events", []):
                                for tick in event.get("tickers", []):
                                    payload = {
                                        "product_id":  tick.get("product_id", pair),
                                        "price":        tick.get("price"),
                                        "best_bid":     tick.get("best_bid"),
                                        "best_ask":     tick.get("best_ask"),
                                        "volume_24_h":  tick.get("volume_24_h"),
                                        "timestamp":    ts,
                                    }
                                    value = json.dumps(payload)

                                    producer.produce(
                                        TOPIC,
                                        key=payload["product_id"],
                                        value=value,
                                        callback=delivery_report,
                                    )
                                    producer.poll(0)
                                    log.debug("[ticker] produced: %s", payload)

                                    if mirror:
                                        mirror_tick(pair, value)

                    except websockets.ConnectionClosed as exc:
                        log.warning("[ticker] connection closed: %s — reconnecting in %.1fs", exc, backoff)
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * 2, BACKOFF_MAX)

            except Exception as exc:
                log.error("[ticker] unexpected error: %s — reconnecting in %.1fs", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, BACKOFF_MAX)
    except asyncio.CancelledError:
        return


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Coinbase WebSocket → Kafka ingestor")
    parser.add_argument("--pair", default="BTC-USD", help="Trading pair (default: BTC-USD)")
    parser.add_argument("--minutes", type=float, default=0,
                        help="Run duration in minutes; 0 = run forever (default: 0)")
    parser.add_argument("--no-mirror", dest="mirror", action="store_false",
                        help="Disable NDJSON file mirror under data/raw/")
    args = parser.parse_args()

    producer = make_producer()
    stop_event = asyncio.Event()

    async def run():
        loop = asyncio.get_running_loop()

        def _shutdown(*_):
            log.info("Shutdown signal received")
            loop.call_soon_threadsafe(stop_event.set)

        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)

        tasks = [
            asyncio.create_task(ticker_task(args.pair, producer, stop_event, args.mirror)),
            asyncio.create_task(heartbeat_task(args.pair, stop_event)),
        ]
        try:
            if args.minutes > 0:
                log.info("Will run for %.1f minute(s)", args.minutes)
                await asyncio.wait_for(stop_event.wait(), timeout=args.minutes * 60)
            else:
                await stop_event.wait()
        except asyncio.TimeoutError:
            stop_event.set()
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            producer.flush()
            log.info("Ingestor stopped — Kafka buffer flushed.")

    asyncio.run(run())
    sys.exit(0)


if __name__ == "__main__":
    main()
