"""特徴量パイプライン（データリーク防止が最重要）

処理フロー:
  1. SQLite から全データを JOIN で読み込む
  2. race_date 昇順でソート（時系列保証）
  3. 各特徴量モジュールを順次適用
  4. カテゴリエンコード
  5. Parquet 保存
"""
import os
from pathlib import Path

import pandas as pd
from loguru import logger
from sqlalchemy import text

from db import get_session
from features.horse_features import compute_horse_features
from features.jockey_features import compute_jockey_features
from features.trainer_features import compute_trainer_features
from features.race_features import compute_race_features
from features.odds_features import compute_odds_features
from features.relative_features import compute_relative_features
from features.interaction_features import compute_interaction_features
from features.encoder import KeibaEncoder


_LOAD_SQL = """
SELECT
    re.race_id,
    re.horse_id,
    re.jockey_id,
    re.trainer_id,
    re.post_position,
    re.finish_position,
    re.time,
    re.last_3f_time,
    re.win_odds,
    re.place_odds,
    re.horse_weight,
    re.weight_diff,
    re.handicap_weight,
    re.running_style,
    re.corner_positions,
    r.date,
    r.venue,
    r.course_id,
    r.distance,
    r.surface,
    r.weather,
    r.going,
    r.grade,
    r.field_size,
    r.lap_times,
    r.straight_length,
    r.num_curves,
    h.name        AS horse_name,
    h.sex,
    h.birth_date,
    h.sire_id,
    h.dam_id,
    h.broodmare_sire_id,
    j.name        AS jockey_name,
    t.name        AS trainer_name,
    t.stable
FROM race_entries re
JOIN  races   r ON re.race_id   = r.race_id
JOIN  horses  h ON re.horse_id  = h.horse_id
LEFT JOIN jockeys  j ON re.jockey_id  = j.jockey_id
LEFT JOIN trainers t ON re.trainer_id = t.trainer_id
ORDER BY r.date ASC, re.race_id, re.post_position
"""


class FeaturePipeline:
    """特徴量生成パイプライン"""

    def __init__(
        self,
        mode: str = "train",
        encoder_path: str = "models/encoder.pkl",
    ) -> None:
        """
        mode: 'train' (エンコーダをfit+save) / 'predict' (エンコーダをload)
        """
        self.mode = mode
        self.encoder_path = encoder_path
        self.encoder: KeibaEncoder | None = None

    def run(self, output_path: str = "data/features/train.parquet") -> pd.DataFrame:
        """パイプラインを実行して Parquet を出力する"""
        logger.info("特徴量パイプライン開始")

        # 1. DBから読み込み
        df = self._load_from_db()
        logger.info(f"読み込み完了: {len(df)} rows")

        # 2. 時系列ソート（必須）
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values(["date", "race_id", "post_position"]).reset_index(drop=True)

        # 3. 各特徴量を計算
        logger.info("馬特徴量計算中...")
        df = compute_horse_features(df)

        logger.info("騎手特徴量計算中...")
        df = compute_jockey_features(df)

        logger.info("調教師特徴量計算中...")
        df = compute_trainer_features(df)

        logger.info("レース条件特徴量計算中...")
        df = compute_race_features(df)

        logger.info("オッズ特徴量計算中...")
        df = compute_odds_features(df)

        logger.info("相対特徴量計算中...")
        df = compute_relative_features(df)

        logger.info("馬間インタラクション特徴量計算中...")
        df = compute_interaction_features(df)

        # 4. エンコード
        if self.mode == "train":
            self.encoder = KeibaEncoder().fit(df)
            Path(self.encoder_path).parent.mkdir(parents=True, exist_ok=True)
            self.encoder.save(self.encoder_path)
        else:
            self.encoder = KeibaEncoder.load(self.encoder_path)

        df = self.encoder.transform(df)

        # 5. 学習モードでは出走予定（finish_position=NULL）を除外
        if self.mode == "train":
            df = df[df["finish_position"].notna()].copy()

        # 6. 保存
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(output_path, index=False)
        logger.info(f"Parquet 保存完了: {output_path} ({len(df)} rows)")

        return df

    def _load_from_db(self) -> pd.DataFrame:
        """SQLite から全データを JOIN で読み込む"""
        db_path = Path("data/keiba.db")
        if not db_path.exists():
            raise FileNotFoundError(
                f"DB が見つかりません ({db_path})。"
                "scrape_historical.py を実行してデータを収集してください。"
            )

        session = get_session()
        try:
            result = session.execute(text(_LOAD_SQL))
            df = pd.DataFrame(result.fetchall(), columns=result.keys())
        except Exception as exc:
            if "no such table" in str(exc).lower():
                raise RuntimeError(
                    "DB にテーブルが存在しません。"
                    "scrape_historical.py を実行してデータを収集してください。"
                ) from exc
            raise
        finally:
            session.close()

        if len(df) == 0:
            raise RuntimeError(
                "DB にレースデータが存在しません。"
                "scrape_historical.py を実行してデータを収集してください。"
            )

        finished = df["finish_position"].notna().sum()
        if finished == 0:
            raise RuntimeError(
                "DB に終了済みレースが存在しません（finish_position=NULL のみ）。"
                "scrape_historical.py で過去レースデータを収集してください。"
            )

        logger.info(f"DB 読み込み: 全{len(df):,}行 (終了済み: {finished:,}行)")
        return df
