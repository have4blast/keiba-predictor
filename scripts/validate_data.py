"""データ品質チェック CLI

使用例:
    python scripts/validate_data.py
    python scripts/validate_data.py --db data/keiba.db --race 202301010101
    python scripts/validate_data.py --strict   # エラー時に exit 1

終了コード:
    0 — エラーなし（警告のみ含む）
    1 — エラーあり
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import click
from loguru import logger
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from db.validator import DataValidator


@click.command()
@click.option("--db",     default="data/keiba.db", help="SQLite DB パス")
@click.option("--race",   default=None,             help="特定レースIDのみ検証")
@click.option("--strict", is_flag=True,             help="警告もエラーとして扱い exit 1 を返す")
def main(db: str, race: str | None, strict: bool) -> None:
    """DB 全体のデータ品質を検証してレポートを出力する"""
    log_path = Path("logs/validation.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger.add(str(log_path), rotation="5 MB", level="WARNING")

    db_path = Path(db)
    if not db_path.exists():
        print(f"ERROR: DB が見つかりません: {db}", file=sys.stderr)
        sys.exit(1)

    engine = create_engine(f"sqlite:///{db_path}")
    with Session(engine) as session:
        validator = DataValidator(session)

        if race:
            logger.info(f"レース個別検証: race_id={race}")
            report = validator.validate_race(race)
        else:
            logger.info("全テーブル検証開始")
            report = validator.validate()

    print(report.summary())

    if report.errors:
        logger.error(f"バリデーションエラー {len(report.errors)} 件")
        sys.exit(1)

    if strict and report.warnings:
        logger.warning(f"strict モード: 警告 {len(report.warnings)} 件")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
