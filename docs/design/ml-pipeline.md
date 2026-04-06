# ML学習・予測パイプライン設計 — 競馬予想AI

## 1. 学習パイプライン全体フロー

```
data/features/train.parquet
         │
         ▼
model/trainer.py
    │
    ├── 1. データ読み込み・前処理
    │      - 目的変数: win_flag (finish_pos==1), place_flag (finish_pos<=3)
    │      - finish_position IS NULL を除外（出走予定データ）
    │      - 特徴量リストを features.md から読み込み
    │
    ├── 2. GroupKFold クロスバリデーション
    │      - n_splits=5, groups=race_id
    │      - 同一レースが学習/検証にまたがらない
    │
    ├── 3. LightGBM 学習（勝利モデル）
    │      - objective: binary
    │      - metric: auc, binary_logloss
    │      - 不均衡対応: scale_pos_weight
    │
    ├── 4. LightGBM 学習（複勝モデル）
    │      - 同上
    │
    ├── 5. モデル保存
    │      - models/lgbm_win.pkl
    │      - models/lgbm_place.pkl
    │      - models/encoder.pkl
    │
    └── 6. 評価レポート出力
           - models/training_report.json
```

---

## 2. 目的変数定義

| モデル | 目的変数 | 正例条件 | 正例率（参考） |
|--------|---------|---------|-------------|
| lgbm_win | `win_flag` | `finish_position == 1` | 約6〜7%（18頭立て時） |
| lgbm_place | `place_flag` | `finish_position <= 3` | 約17〜18% |

---

## 3. LightGBM ハイパーパラメータ

```python
WIN_PARAMS = {
    "objective": "binary",
    "metric": ["auc", "binary_logloss"],
    "boosting_type": "gbdt",
    "num_leaves": 63,
    "max_depth": -1,
    "learning_rate": 0.05,
    "n_estimators": 1000,
    "min_child_samples": 20,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "scale_pos_weight": 14,    # 1/勝率 ≈ 14
    "random_state": 42,
    "n_jobs": -1,
    "verbose": -1,
}

PLACE_PARAMS = {
    **WIN_PARAMS,
    "scale_pos_weight": 4,     # 1/複勝率 ≈ 4〜5
}
```

**Early Stopping:** `early_stopping_rounds=50` でバリデーションロスが50ラウンド改善なしで停止

---

## 4. GroupKFold 設計

```python
from sklearn.model_selection import GroupKFold

kf = GroupKFold(n_splits=5)
groups = df["race_id"]   # 同一レースは同じfoldに入る

for fold, (train_idx, val_idx) in enumerate(kf.split(X, y, groups)):
    X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
    y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
    # 学習・評価...
```

**注意**: GroupKFold は時系列分割ではないが、`groups=race_id` により同一レース内での情報リークを防止する。  
厳密な時系列分割が必要な場合は `TimeSeriesSplit` を別途検討する。

---

## 5. 評価指標

| 指標 | 計算方法 | 目標 |
|------|---------|------|
| AUC (win) | `roc_auc_score(y_true, y_pred_proba)` | > 0.75 |
| AUC (place) | 同上 | > 0.70 |
| 単勝的中率 | 最高スコア馬が1着の割合 | > 人気1番人気的中率（約30%） |
| 複勝的中率 | 最高スコア馬が3着以内の割合 | > 35% |
| 単勝ROI | 回収額 / 投票額 - 1 | > -20% |
| 複勝ROI | 同上 | > -10% |

---

## 6. バックテスト設計（`model/evaluate.py`）

```
バックテスト戦略: 各レースで予測スコア最高の馬に100円単勝投票と仮定

for each race in val_set:
    predicted_winner = horse with max(win_score)
    actual_winner = horse with finish_position == 1
    if predicted_winner == actual_winner:
        profit += win_odds * 100 - 100
    else:
        profit -= 100
    roi_curve.append(cumulative_profit / cumulative_investment)
```

---

## 7. 予測パイプライン（`model/predictor.py`）

```python
class Predictor:
    def __init__(self, model_dir: str = "models/"):
        self.win_model = joblib.load(f"{model_dir}/lgbm_win.pkl")
        self.place_model = joblib.load(f"{model_dir}/lgbm_place.pkl")
        self.encoder = joblib.load(f"{model_dir}/encoder.pkl")
        self.feature_cols: list[str] = ...  # training_report.json から読み込み

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        df: 出走予定馬の特徴量DataFrame (finish_position=NULL)
        returns: df with 'win_score', 'place_score' columns added
        """
        X = self.encoder.transform(df[self.feature_cols])  # 再fitしない
        df["win_score"] = self.win_model.predict_proba(X)[:, 1]
        df["place_score"] = self.place_model.predict_proba(X)[:, 1]
        return df
```

---

## 8. モデル保存形式

```
models/
├── lgbm_win.pkl           # joblib.dump(lgbm_win_model)
├── lgbm_place.pkl         # joblib.dump(lgbm_place_model)
├── encoder.pkl            # joblib.dump(fitted_encoder)
└── training_report.json   # 評価指標・特徴量リスト・学習日時
```

**training_report.json 形式:**
```json
{
  "trained_at": "2024-01-15T10:30:00",
  "train_period": {"start": "2022-01-01", "end": "2024-12-31"},
  "feature_cols": ["horse_age_months", "last_3f_avg_5", ...],
  "cv_results": {
    "win_auc_mean": 0.763,
    "win_auc_std": 0.012,
    "place_auc_mean": 0.712,
    "place_auc_std": 0.009
  },
  "backtest": {
    "win_accuracy": 0.312,
    "win_roi": -0.142,
    "place_accuracy": 0.387,
    "place_roi": -0.063
  }
}
```

---

## 9. SHAP 特徴量重要度

```python
import shap

explainer = shap.TreeExplainer(win_model)
shap_values = explainer.shap_values(X_val)

# ダッシュボード用に上位20特徴量を保存
feature_importance = pd.DataFrame({
    "feature": feature_cols,
    "shap_mean_abs": np.abs(shap_values).mean(axis=0)
}).sort_values("shap_mean_abs", ascending=False).head(20)
```
