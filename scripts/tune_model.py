"""ハイパーパラメータ自動チューニングスクリプト

使用例:
    python scripts/tune_model.py
    python scripts/tune_model.py --trials 100 --target place
    python scripts/tune_model.py --trials 50 --target win --train
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import click
import pandas as pd
from loguru import logger


@click.command()
@click.option("--features", default="data/features/train.parquet",
              help="学習データ Parquet パス")
@click.option("--models",   default="models/",
              help="モデル保存ディレクトリ")
@click.option("--trials",   default=50, type=int,
              help="Optuna トライアル数")
@click.option("--target",   default="win", type=click.Choice(["win", "place"]),
              help="最適化対象モデル")
@click.option("--splits",   default=3, type=int,
              help="GroupKFold の分割数")
@click.option("--train/--no-train", default=True,
              help="チューニング後に最適パラメータで再学習するか")
def main(features: str, models: str, trials: int, target: str, splits: int, train: bool) -> None:
    """Optuna でハイパーパラメータを自動探索し、最適パラメータで再学習する"""
    logger.add("logs/tune_model.log", rotation="10 MB")
    logger.info(f"チューニング開始: target={target}, trials={trials}")

    df = pd.read_parquet(features)
    logger.info(f"学習データ: {len(df):,} rows")

    from model.tuner import tune
    report = tune(df, target=target, n_trials=trials, n_splits=splits, output_dir=models)

    print("\n=== チューニング結果 ===")
    print(f"  対象モデル : {target}")
    print(f"  最良 AUC  : {report['best_auc']:.4f}")
    print(f"  トライアル : {report['n_trials']}")
    print(f"\n  最適パラメータ:")
    for k, v in report["best_params"].items():
        print(f"    {k}: {v}")
    print(f"\n  保存先: {models}tuning_report.json")

    # チューニング後に最適パラメータで再学習
    if train:
        print("\n=== 最適パラメータで再学習 ===")
        from model.trainer import KeibaTrainer
        trainer = KeibaTrainer(
            feature_path=features,
            model_dir=models,
            n_splits=5,
        )
        # 最適パラメータを trainer に反映
        best = report["best_params"]
        if target == "win":
            trainer.WIN_PARAMS.update(best)
        else:
            trainer.PLACE_PARAMS.update(best)

        train_report = trainer.run()
        cv = train_report["cv_results"]
        print(f"  Win AUC  : {cv['win_auc_mean']:.4f} ± {cv['win_auc_std']:.4f}")
        print(f"  Place AUC: {cv['place_auc_mean']:.4f} ± {cv['place_auc_std']:.4f}")


if __name__ == "__main__":
    main()
