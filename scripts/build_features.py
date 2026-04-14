"""特徴量生成スクリプト

使用例:
    python scripts/build_features.py
    python scripts/build_features.py --output data/features/train.parquet
    python scripts/build_features.py --mode predict --output data/features/predict.parquet
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import click
from loguru import logger
from features.pipeline import FeaturePipeline


@click.command()
@click.option("--output", default="data/features/train.parquet",
              help="出力 Parquet パス")
@click.option("--mode", default="train", type=click.Choice(["train", "predict"]),
              help="train: エンコーダをfit保存 / predict: エンコーダをload")
@click.option("--encoder", default="models/encoder.pkl",
              help="エンコーダの保存/読み込みパス")
def main(output: str, mode: str, encoder: str) -> None:
    """特徴量を生成して Parquet に保存する"""
    logger.add("logs/build_features.log", rotation="10 MB")
    logger.info(f"特徴量生成開始: mode={mode}, output={output}")

    pipeline = FeaturePipeline(mode=mode, encoder_path=encoder)
    df = pipeline.run(output_path=output)

    logger.info(f"完了: {len(df)} rows, {len(df.columns)} features")
    print(f"\n特徴量生成完了")
    print(f"  行数   : {len(df):,}")
    print(f"  列数   : {len(df.columns)}")
    print(f"  出力先 : {output}")


if __name__ == "__main__":
    main()
