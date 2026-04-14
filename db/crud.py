"""upsert操作（SQLite の INSERT OR REPLACE ベース）"""
from datetime import datetime
from typing import Any
from sqlalchemy.orm import Session
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from db.models import (
    Race, RaceEntry, Horse, Jockey, Trainer,
    Stallion, OddsHistory, Course,
)


def _upsert(session: Session, model: Any, data: dict, pk_cols: list[str]) -> None:
    """汎用 upsert ヘルパー"""
    data["updated_at"] = datetime.utcnow()
    stmt = sqlite_insert(model).values(**data)
    update_cols = {k: v for k, v in data.items() if k not in pk_cols + ["created_at"]}
    stmt = stmt.on_conflict_do_update(index_elements=pk_cols, set_=update_cols)
    session.execute(stmt)


def upsert_race(session: Session, data: dict) -> None:
    _upsert(session, Race, data, ["race_id"])


def upsert_race_entry(session: Session, data: dict) -> None:
    _upsert(session, RaceEntry, data, ["race_id", "horse_id"])


def upsert_horse(session: Session, data: dict) -> None:
    _upsert(session, Horse, data, ["horse_id"])


def upsert_jockey(session: Session, data: dict) -> None:
    _upsert(session, Jockey, data, ["jockey_id"])


def upsert_trainer(session: Session, data: dict) -> None:
    _upsert(session, Trainer, data, ["trainer_id"])


def upsert_stallion(session: Session, data: dict) -> None:
    stmt = sqlite_insert(Stallion).values(**data)
    stmt = stmt.on_conflict_do_nothing(index_elements=["horse_id"])
    session.execute(stmt)


def upsert_odds_history(session: Session, data: dict) -> None:
    """同一 race_id + horse_id + timestamp の重複は無視"""
    stmt = sqlite_insert(OddsHistory).values(**data)
    stmt = stmt.on_conflict_do_nothing()
    session.execute(stmt)


def upsert_course(session: Session, data: dict) -> None:
    _upsert(session, Course, data, ["course_id"])


# ── クエリ（ダッシュボード向け） ──────────────────────────────────

def get_table_counts(session: Session) -> dict[str, int]:
    """各テーブルのレコード数を返す"""
    from sqlalchemy import func, select
    counts = {}
    for model in [Race, RaceEntry, Horse, Jockey, Trainer, Stallion, OddsHistory]:
        counts[model.__tablename__] = session.execute(
            select(func.count()).select_from(model)
        ).scalar_one()
    return counts


def get_last_updated(session: Session) -> dict[str, Any]:
    """各テーブルの最終更新日を返す"""
    from sqlalchemy import func, select
    result = {}
    for model, label in [(Race, "races"), (RaceEntry, "race_entries")]:
        val = session.execute(
            select(func.max(model.updated_at)).select_from(model)
        ).scalar_one()
        result[label] = val
    return result


def get_upcoming_race_ids(session: Session) -> list[str]:
    """finish_position が NULL（出走予定）のレースIDを返す"""
    from sqlalchemy import select, distinct
    rows = session.execute(
        select(distinct(RaceEntry.race_id))
        .where(RaceEntry.finish_position.is_(None))
    ).scalars().all()
    return list(rows)


def horse_exists(session: Session, horse_id: str) -> bool:
    from sqlalchemy import select
    return session.execute(
        select(Horse.horse_id).where(Horse.horse_id == horse_id)
    ).scalar_one_or_none() is not None


def jockey_exists(session: Session, jockey_id: str) -> bool:
    from sqlalchemy import select
    return session.execute(
        select(Jockey.jockey_id).where(Jockey.jockey_id == jockey_id)
    ).scalar_one_or_none() is not None


def trainer_exists(session: Session, trainer_id: str) -> bool:
    from sqlalchemy import select
    return session.execute(
        select(Trainer.trainer_id).where(Trainer.trainer_id == trainer_id)
    ).scalar_one_or_none() is not None


def get_scraped_race_ids(session: Session) -> set[str]:
    """すでにスクレイピング済みのレースIDセットを返す（--resume 用）"""
    from sqlalchemy import select
    rows = session.execute(select(Race.race_id)).scalars().all()
    return set(rows)
