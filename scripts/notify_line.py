"""LINE Notify 予測通知スクリプト

当日の全レース上位3頭を LINE Notify で送信する。
LINE_NOTIFY_TOKEN は .env または環境変数から取得する。

使用例:
    python scripts/notify_line.py
    python scripts/notify_line.py --date 2024-06-15 --max-races 8
    python scripts/notify_line.py --dry-run   # 送信せず本文を標準出力に表示
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import date
from pathlib import Path

import click
import requests
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

_LINE_API = "https://notify-api.line.me/api/notify"
_MAX_MESSAGE_LEN = 1000   # LINE Notify の上限


def _format_message(target_date: str, predictions: list[dict]) -> str:
    """通知メッセージを整形する"""
    lines = [f"\n【競馬予想AI】{target_date} の予測\n"]
    for race in predictions:
        venue    = race.get("venue", "")
        race_num = race.get("race_num", "")
        name     = race.get("race_name", "")
        horses   = race.get("horses", [])

        lines.append(f"🏇 {venue}{race_num}R {name}")
        medals = ["🥇 本命", "🥈 対抗", "🥉 単穴"]
        for i, h in enumerate(horses[:3]):
            medal      = medals[i] if i < len(medals) else f"  {i+1}."
            horse_name = h.get("name", "不明")
            score      = h.get("score", 0.0)
            lines.append(f"  {medal}: {horse_name} ({score:.4f})")
        lines.append("")

    return "\n".join(lines)[:_MAX_MESSAGE_LEN]


def send_line(token: str, message: str) -> None:
    """LINE Notify API にメッセージを送信する"""
    resp = requests.post(
        _LINE_API,
        headers={"Authorization": f"Bearer {token}"},
        data={"message": message},
        timeout=10,
    )
    resp.raise_for_status()
    logger.info(f"LINE 送信完了: status={resp.status_code}")


def _load_predictions(target_date: str, max_races: int) -> list[dict]:
    """指定日の予測スコアを DB + モデルから取得する"""
    db_path    = Path("data/keiba.db")
    model_dir  = Path("models")

    if not db_path.exists():
        logger.warning("DB が存在しません")
        return []
    if not (model_dir / "lgbm_win.pkl").exists():
        logger.warning("モデルが存在しません")
        return []

    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session
    from model.predictor import Predictor

    engine   = create_engine(f"sqlite:///{db_path}")
    predictor = Predictor(str(model_dir))

    date_str = target_date.replace("-", "")

    with Session(engine) as session:
        races = session.execute(
            text("""
                SELECT DISTINCT r.race_id, r.venue,
                       CAST(substr(r.race_id, 11, 2) AS INTEGER) AS race_num,
                       r.grade
                FROM race_entries re
                JOIN races r ON re.race_id = r.race_id
                WHERE strftime('%Y%m%d', r.date) = :d
                  AND re.finish_position IS NULL
                ORDER BY r.race_id
                LIMIT :lim
            """),
            {"d": date_str, "lim": max_races},
        ).fetchall()

    if not races:
        logger.info(f"{target_date} の出走予定レースなし")
        return []

    import pandas as pd
    result = []
    for race_row in races:
        race_id = race_row[0]
        with Session(engine) as session:
            entries = session.execute(
                text("""
                    SELECT re.*, h.name AS horse_name
                    FROM race_entries re
                    JOIN horses h ON re.horse_id = h.horse_id
                    WHERE re.race_id = :rid
                """),
                {"rid": race_id},
            ).mappings().fetchall()

        if not entries:
            continue

        df = pd.DataFrame([dict(r) for r in entries])
        try:
            scores = predictor.predict(df)
        except Exception as e:
            logger.warning(f"予測失敗 race_id={race_id}: {e}")
            continue

        if "win_score" not in scores.columns:
            continue

        top3 = scores.nlargest(3, "win_score")
        horses = [
            {"name": row.get("horse_name", "不明"), "score": float(row["win_score"])}
            for _, row in top3.iterrows()
        ]
        result.append({
            "venue":     race_row[1],
            "race_num":  race_row[2],
            "race_name": race_row[3] or "",
            "horses":    horses,
        })

    return result


@click.command()
@click.option("--date",      default=None,  help="対象日 YYYY-MM-DD（省略時は今日）")
@click.option("--max-races", default=6, type=int, help="通知する最大レース数")
@click.option("--token",     default=None,  help="LINE Notify Token（省略時は環境変数）")
@click.option("--dry-run",   is_flag=True,  help="送信せずメッセージを標準出力に表示")
def main(date: str | None, max_races: int, token: str | None, dry_run: bool) -> None:
    """当日レースの上位3頭を LINE Notify で送信する"""
    logger.add("logs/notify_line.log", rotation="5 MB")

    target_date = date or str(date.today() if date is None else date)
    if date is None:
        from datetime import date as _date
        target_date = str(_date.today())

    logger.info(f"予測通知開始: date={target_date}, max_races={max_races}")

    predictions = _load_predictions(target_date, max_races)
    if not predictions:
        logger.info("通知対象レースなし — 終了")
        return

    message = _format_message(target_date, predictions)

    if dry_run:
        print("=== DRY RUN — 送信はしません ===")
        print(message)
        return

    line_token = token or os.environ.get("LINE_NOTIFY_TOKEN")
    if not line_token:
        logger.error("LINE_NOTIFY_TOKEN が設定されていません (.env または --token)")
        sys.exit(1)

    try:
        send_line(line_token, message)
        print(f"送信完了: {len(predictions)} レース")
    except requests.HTTPError as e:
        logger.error(f"LINE 送信失敗: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
