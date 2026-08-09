import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # populate os.environ from .env BEFORE importing config/settings

from fastapi import FastAPI  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from db.reads import load_active_tickers  # noqa: E402
from market.cache import PriceCache  # noqa: E402
from market.factory import make_source  # noqa: E402
from market.feed import MarketFeed  # noqa: E402
from market.routes import router as market_router  # noqa: E402
from portfolio.routes import router as portfolio_router  # noqa: E402
from snapshots.task import SnapshotTask  # noqa: E402
from watchlist.routes import router as watchlist_router  # noqa: E402

log = logging.getLogger("finally.main")

# Populated by the Dockerfile with the Next.js static export; absent in local
# development, where the frontend runs on its own dev server.
STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    cache = PriceCache()
    source = make_source()
    feed = MarketFeed(source, cache, get_active_tickers=load_active_tickers)
    snapshots = SnapshotTask(cache)

    app.state.price_cache = cache
    app.state.market_source = source
    app.state.market_feed = feed
    app.state.snapshot_task = snapshots

    await feed.prime()   # one synchronous fill so the first request has data
    feed.start()         # then the background loop takes over
    snapshots.start()
    try:
        yield
    finally:
        await snapshots.stop()
        await feed.stop()


app = FastAPI(lifespan=lifespan)
app.include_router(market_router)
app.include_router(portfolio_router)
app.include_router(watchlist_router)

try:
    from chat.routes import router as chat_router

    app.include_router(chat_router)
except ImportError:
    log.warning("chat router unavailable; /api/chat is not served")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# Mounted last so every /api route above wins; html=True serves index.html at
# the root and for directory paths.
if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
