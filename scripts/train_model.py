"""モデル学習スクリプト

使用例:
    python scripts/train_model.py
    python scripts/train_model.py --features data/features/train.parquet --models models/
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import click
from loguru import logger
from model.trainer import KeibaTrainer


@click.command()
@click.option("--features", default="data/features/train.parquet",
              help="学習データ Parquet パス")
@click.option("--models",   default="models/",
              help="モデル保存ディレクトリ")
@click.option("--splits",   default=5, type=int,
              help="GroupKFold の分割数")
def main(features: str, models: str, splits: int) -> None:
    """LightGBM モデルを学習してモデルファイルを保存する"""
    logger.add("logs/train_model.log", rotation="10 MB")
    logger.info(f"モデル学習開始: features={features}, models={models}")

    trainer = KeibaTrainer(
        feature_path=features,
        model_dir=models,
        n_splits=splits,
    )
    report = trainer.run()

    cv = report["cv_results"]
    bt = report["backtest"]

    print("\n=== 学習結果 ===")
    print(f"  勝利モデル AUC : {cv['win_auc_mean']:.4f} ± {cv['win_auc_std']:.4f}")
    print(f"  複勝モデル AUC : {cv['place_auc_mean']:.4f} ± {cv['place_auc_std']:.4f}")
    print(f"\n=== バックテスト（学習データ） ===")
    print(f"  単勝的中率    : {bt.get('win_accuracy', 0):.1%}")
    print(f"  単勝ROI       : {bt.get('win_roi', 0):.1%}")
    print(f"  総レース数    : {bt.get('total_races', 0):,}")
    print(f"\n保存先: {models}")


if __name__ == "__main__":
    main()
