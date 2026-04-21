# 設計ドキュメント — モデル精度改善 (A)

## 1. SHAP 統合設計

### 1-1. `model/explainer.py`（新規）

```python
class KeibaExplainer:
    def __init__(self, model_dir: str)
    def explain(self, df: pd.DataFrame, model: str = "win") -> pd.DataFrame
        # shap.TreeExplainer(lgbm_model) で shap_values 計算
        # 各行に top10 特徴量名・SHAP値を付加した DataFrame を返す
```

- `shap.TreeExplainer` は LightGBM ネイティブ対応で高速
- キャッシュ: `explainer` オブジェクトは `@st.cache_resource` でセッション内保持
- 出力: 各馬ごとに `shap_feat_1..10`（特徴量名）+ `shap_val_1..10`（値）カラムを付加

### 1-2. `dashboard/pages/predictions.py` 拡張

既存の予測結果ページに **馬選択 → SHAP 棒グラフ** を追加:

```
[馬名セレクトボックス]
→ plotly horizontal bar chart
  - 特徴量名 (y軸)
  - SHAP値 (x軸, 正=勝利寄与・負=敗北寄与)
  - 色: 正=緑, 負=赤
```

---

## 2. Optuna チューニング設計

### 2-1. `model/tuner.py`（新規）

```python
def objective(trial: optuna.Trial, df: pd.DataFrame) -> float:
    # trial.suggest_float / suggest_int で以下を探索:
    #   num_leaves: 20–300
    #   learning_rate: 0.01–0.3 (log)
    #   min_child_samples: 5–100
    #   feature_fraction: 0.5–1.0
    #   bagging_fraction: 0.5–1.0
    #   lambda_l1, lambda_l2: 0–10
    # GroupKFold(3) で AUC 平均を返す

def tune(df, n_trials=50, target="win") -> dict:
    # study = optuna.create_study(direction="maximize")
    # study.optimize(objective, n_trials=n_trials)
    # return best_params
```

### 2-2. `scripts/tune_model.py`（新規）

```
python scripts/tune_model.py --trials 50 --target win
→ models/tuning_report.json に保存
→ 最適パラメータで train_model.py を自動実行
```

`tuning_report.json` 構造:
```json
{
  "target": "win",
  "best_auc": 0.9512,
  "best_params": { "num_leaves": 127, ... },
  "n_trials": 50,
  "tuned_at": "2026-04-21T09:00:00Z"
}
```

---

## 3. 新規特徴量設計

### 3-1. 上がり3F偏差（`relative_features.py` 追記）

```
last3f_vs_race_avg = horse.last_3f_avg_5 - race_mean(last_3f_avg_5)
```
- 同一レース出走馬の `last_3f_avg_5` 平均との差分
- 負の値 = 上がりが速い馬（有利）
- リーク防止: `last_3f_avg_5` 自体が shift(1) 済みなので追加の shift は不要

### 3-2. ペース係数改良（`race_features.py` 追記）

```
pace_ratio = first_half_avg_lap / second_half_avg_lap
```
- `lap_times` JSON から前半・後半に分割して比 (1.0=均等, >1.0=前半速い)
- コース×距離グループの過去平均 pace_ratio との差分も算出

### 3-3. 斤量×距離交差項（`interaction_features.py` 追記）

```
handicap_x_distance = handicap_weight * distance / 1000
```
- 長距離ほど斤量の影響が増すことを表現するシンプルな交差項
- スケーリング: distance を km 単位に変換して値域を揃える
