import logging
from contextlib import asynccontextmanager
from typing import Optional, Set

from fastapi import FastAPI, Path, Query

import tibiapy
from tibiapy import VocationSpellFilter, SpellGroup, SpellType, SpellSorting, TibiaResponse, NewsType, NewsCategory
from tibiapy.models import World, WorldOverview, Spell, SpellsSection
from tibiapy.models.news import NewsArchive, News

logging_formatter = logging.Formatter('[%(asctime)s][%(levelname)s] %(message)s')
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging_formatter)
log = logging.getLogger("tibiapy")
log.addHandler(console_handler)
log.setLevel(logging.DEBUG)

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.client = tibiapy.Client()
    yield
    await app.state.client.session.close()

app = FastAPI(lifespan=lifespan)


@app.get("/news/recent/{days}")
async def get_recent_news(
    days: int = Path(...),
    types: Set[NewsType] = Query(None, alias="type"),
    categories: Set[NewsCategory] = Query(None, alias="category"),
) -> TibiaResponse[NewsArchive]:
    return await app.state.client.fetch_recent_news(days=days, types=types, categories=categories)


@app.get("/news/{news_id}")
async def get_news_article(
    news_id: int = Path(...)
) -> TibiaResponse[Optional[News]]:
    return await app.state.client.fetch_news(news_id=news_id)


@app.get("/spells")
async def get_spells(
        vocation: VocationSpellFilter = Query(None),
        group: SpellGroup = Query(None),
        type: SpellType = Query(None),
        premium: bool = Query(None),
        sort: SpellSorting = Query(None),
) -> TibiaResponse[SpellsSection]:
    return await app.state.client.fetch_spells(vocation=vocation, group=group, spell_type=type, premium=premium, sort=sort)


@app.get("/spells/{identifier}")
async def get_spell(
    identifier: str = Path(...)
) -> TibiaResponse[Optional[Spell]]:
    return await app.state.client.fetch_spell(identifier)


@app.get("/worlds")
async def get_worlds() -> TibiaResponse[WorldOverview]:
    return await app.state.client.fetch_world_list()


@app.get("/worlds/{name}")
async def get_world(name: str = Path(...)) -> TibiaResponse[Optional[World]]:
    return await app.state.client.fetch_world(name)

