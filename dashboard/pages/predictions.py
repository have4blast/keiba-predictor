"""予測結果ページ

今日・明日の出走予定馬に対するモデルスコアを表示する。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
from pathlib import Path

st.set_page_config(
    page_title="予測結果 - 競馬予想AI",
    page_icon="📊",
    layout="wide",
)

# ─────────────────────────────────────────────
# キャッシュ付きロード関数
# ─────────────────────────────────────────────

@st.cache_resource
def load_predictor():
    """Predictor をキャッシュロードする"""
    model_dir = Path("models")
    if not (model_dir / "lgbm_win.pkl").exists():
        return None
    from model.predictor import Predictor
    return Predictor(str(model_dir))


@st.cache_resource
def load_explainer():
    """KeibaExplainer をキャッシュロードする"""
    model_dir = Path("models")
    if not (model_dir / "lgbm_win.pkl").exists():
        return None
    from model.explainer import KeibaExplainer
    return KeibaExplainer(str(model_dir))


@st.cache_data(ttl=60)
def get_upcoming_races(target_date: str) -> pd.DataFrame:
    """指定日の出走予定レース一覧を取得する"""
    from db import crud
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    db_path = Path("data/keiba.db")
    if not db_path.exists():
        return pd.DataFrame()

    engine = create_engine(f"sqlite:///{db_path}")
    with Session(engine) as session:
        return crud.get_upcoming_races(session, target_date)


@st.cache_data(ttl=60)
def get_race_entries(race_id: str) -> pd.DataFrame:
    """特定レースの出走馬一覧を取得する"""
    from db import crud
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    db_path = Path("data/keiba.db")
    if not db_path.exists():
        return pd.DataFrame()

    engine = create_engine(f"sqlite:///{db_path}")
    with Session(engine) as session:
        return crud.get_race_entries(session, race_id)


# ─────────────────────────────────────────────
# サイドバー
# ─────────────────────────────────────────────
with st.sidebar:
    st.title("🏇 競馬予想AI")
    st.markdown("---")
    st.page_link("dashboard/app.py",               label="🏠 ホーム",       icon="🏠")
    st.page_link("dashboard/pages/predictions.py", label="📊 予測結果",     icon="📊")
    st.page_link("dashboard/pages/backtest.py",    label="📈 バックテスト", icon="📈")
    st.page_link("dashboard/pages/data_status.py", label="🗄️ データ状況",   icon="🗄️")

    st.markdown("---")
    # 日付選択
    today = date.today()
    target_date = st.date_input(
        "対象日",
        value=today,
        min_value=today - timedelta(days=7),
        max_value=today + timedelta(days=1),
    )
    date_str = target_date.strftime("%Y%m%d")

# ─────────────────────────────────────────────
# メインコンテンツ
# ─────────────────────────────────────────────
st.title("📊 予測結果")
st.caption(f"対象日: {target_date.strftime('%Y年%m月%d日')}")

predictor = load_predictor()
if predictor is None:
    st.warning("モデルファイルが見つかりません。先にモデルを学習してください。")
    st.code("python scripts/train_model.py", language="bash")
    st.stop()

# レース一覧取得
races_df = get_upcoming_races(date_str)
if races_df.empty:
    st.info(f"{target_date.strftime('%Y年%m月%d日')} の出走予定データがありません。")
    st.markdown("以下のコマンドで出走表を取得してください：")
    st.code(f"python scripts/scrape_upcoming.py --date {target_date.strftime('%Y-%m-%d')}", language="bash")
    st.stop()

# レース選択
race_options = {
    f"{row.get('venue', '')} {row.get('race_num', '')}R - {row.get('race_name', row['race_id'])}": row["race_id"]
    for _, row in races_df.iterrows()
}
selected_label = st.selectbox("レースを選択", list(race_options.keys()))
selected_race_id = race_options[selected_label]

# 出走馬取得
entries_df = get_race_entries(selected_race_id)
if entries_df.empty:
    st.warning("出走馬データが取得できませんでした。")
    st.stop()

# ─────────────────────────────────────────────
# 予測実行
# ─────────────────────────────────────────────
with st.spinner("予測中..."):
    try:
        scores_df = predictor.predict(entries_df)
    except Exception as e:
        st.error(f"予測エラー: {e}")
        st.stop()

# スコアカラム存在確認
if "win_score" not in scores_df.columns:
    st.error("予測スコアが計算できませんでした。特徴量を確認してください。")
    st.stop()

# 表示用DF整形
display_cols = [
    "post_position", "horse_name", "jockey_name",
    "win_odds", "win_score", "place_score",
]
display_cols = [c for c in display_cols if c in scores_df.columns]
result_df = scores_df[display_cols].copy()

# カラム名を日本語化
col_map = {
    "post_position": "枠番",
    "horse_name":    "馬名",
    "jockey_name":   "騎手",
    "win_odds":      "単勝オッズ",
    "win_score":     "勝利スコア",
    "place_score":   "複勝スコア",
}
result_df = result_df.rename(columns={k: v for k, v in col_map.items() if k in result_df.columns})

# スコアで降順ソート
if "勝利スコア" in result_df.columns:
    result_df = result_df.sort_values("勝利スコア", ascending=False)

# ─────────────────────────────────────────────
# 上位馬ハイライト
# ─────────────────────────────────────────────
col1, col2, col3 = st.columns(3)
if len(result_df) >= 1:
    top1 = result_df.iloc[0]
    with col1:
        horse_name = top1.get("馬名", "不明")
        score = top1.get("勝利スコア", 0)
        st.metric("🥇 本命", horse_name, f"スコア: {score:.4f}")
if len(result_df) >= 2:
    top2 = result_df.iloc[1]
    with col2:
        horse_name = top2.get("馬名", "不明")
        score = top2.get("勝利スコア", 0)
        st.metric("🥈 対抗", horse_name, f"スコア: {score:.4f}")
if len(result_df) >= 3:
    top3 = result_df.iloc[2]
    with col3:
        horse_name = top3.get("馬名", "不明")
        score = top3.get("勝利スコア", 0)
        st.metric("🥉 単穴", horse_name, f"スコア: {score:.4f}")

st.markdown("---")

# ─────────────────────────────────────────────
# スコアテーブル
# ─────────────────────────────────────────────
st.subheader("出走馬スコア一覧")


def _highlight_top3(s: pd.Series):
    """上位3行を色付けする"""
    colors = []
    for i in range(len(s)):
        if i == 0:
            colors.append("background-color: #FFD700; color: black")
        elif i == 1:
            colors.append("background-color: #C0C0C0; color: black")
        elif i == 2:
            colors.append("background-color: #CD7F32; color: black")
        else:
            colors.append("")
    return colors


styled = result_df.style.apply(_highlight_top3, axis=0)
if "勝利スコア" in result_df.columns:
    styled = styled.format({"勝利スコア": "{:.4f}", "複勝スコア": "{:.4f}"}, na_rep="-")
if "単勝オッズ" in result_df.columns:
    styled = styled.format({"単勝オッズ": "{:.1f}"}, na_rep="-")

st.dataframe(styled, use_container_width=True, hide_index=True)

# ─────────────────────────────────────────────
# 勝利スコア棒グラフ
# ─────────────────────────────────────────────
st.subheader("勝利スコア グラフ")
if "勝利スコア" in result_df.columns and "馬名" in result_df.columns:
    chart_df = result_df[["馬名", "勝利スコア"]].copy()
    # 枠番があれば馬名に付加
    if "枠番" in result_df.columns:
        chart_df["ラベル"] = result_df["枠番"].astype(str) + "." + result_df["馬名"]
    else:
        chart_df["ラベル"] = result_df["馬名"]

    fig = px.bar(
        chart_df,
        x="勝利スコア",
        y="ラベル",
        orientation="h",
        color="勝利スコア",
        color_continuous_scale="RdYlGn",
        labels={"ラベル": "馬名", "勝利スコア": "スコア"},
    )
    fig.update_layout(
        yaxis={"categoryorder": "total ascending"},
        showlegend=False,
        height=max(300, len(result_df) * 35),
        margin=dict(l=0, r=0, t=20, b=0),
    )
    st.plotly_chart(fig, use_container_width=True)

# ─────────────────────────────────────────────
# SHAP 特徴量寄与グラフ
# ─────────────────────────────────────────────
st.markdown("---")
st.subheader("SHAP 予測根拠")

explainer = load_explainer()
if explainer is not None and "馬名" in scores_df.columns:
    horse_options = scores_df["horse_name"].tolist() if "horse_name" in scores_df.columns else []
    if not horse_options and "馬名" in result_df.columns:
        horse_options = result_df["馬名"].tolist()

    if horse_options:
        selected_horse = st.selectbox("馬を選択", horse_options, key="shap_horse_select")

        with st.spinner("SHAP 値を計算中..."):
            try:
                shap_target = st.radio("対象モデル", ["win", "place"],
                                       format_func=lambda x: "勝利モデル" if x == "win" else "複勝モデル",
                                       horizontal=True, key="shap_target")
                explained_df = explainer.explain(scores_df, target=shap_target, top_n=10)

                # 選択馬の行を取得
                if "horse_name" in explained_df.columns:
                    horse_row = explained_df[explained_df["horse_name"] == selected_horse]
                else:
                    horse_row = explained_df.iloc[[horse_options.index(selected_horse)]]

                if not horse_row.empty:
                    row = horse_row.iloc[0]
                    feats, vals = [], []
                    for rank in range(10, 0, -1):
                        f = row.get(f"shap_feat_{rank}")
                        v = row.get(f"shap_val_{rank}")
                        if pd.notna(f) and pd.notna(v):
                            feats.append(str(f))
                            vals.append(float(v))

                    if feats:
                        colors = ["#e74c3c" if v < 0 else "#2ecc71" for v in vals]
                        fig_shap = go.Figure(go.Bar(
                            x=vals,
                            y=feats,
                            orientation="h",
                            marker_color=colors,
                        ))
                        base_val = row.get("shap_base_value", 0)
                        fig_shap.update_layout(
                            title=f"{selected_horse} の予測根拠（SHAP値）— ベースライン: {base_val:.3f}",
                            xaxis_title="SHAP 値（正=勝利寄与 / 負=敗北寄与）",
                            yaxis_title="特徴量",
                            height=400,
                            margin=dict(l=0, r=0, t=40, b=0),
                        )
                        fig_shap.add_vline(x=0, line_dash="dash", line_color="gray")
                        st.plotly_chart(fig_shap, use_container_width=True)
            except Exception as e:
                st.info(f"SHAP 計算をスキップしました: {e}")
else:
    st.info("SHAP はモデル学習後に利用可能です。")

st.markdown("---")

# ─────────────────────────────────────────────
# 複勝スコアグラフ
# ─────────────────────────────────────────────
if "複勝スコア" in result_df.columns and "馬名" in result_df.columns:
    st.subheader("複勝スコア グラフ")
    chart_df2 = result_df[["馬名", "複勝スコア"]].copy()
    if "枠番" in result_df.columns:
        chart_df2["ラベル"] = result_df["枠番"].astype(str) + "." + result_df["馬名"]
    else:
        chart_df2["ラベル"] = result_df["馬名"]

    fig2 = px.bar(
        chart_df2,
        x="複勝スコア",
        y="ラベル",
        orientation="h",
        color="複勝スコア",
        color_continuous_scale="Blues",
        labels={"ラベル": "馬名", "複勝スコア": "スコア"},
    )
    fig2.update_layout(
        yaxis={"categoryorder": "total ascending"},
        showlegend=False,
        height=max(300, len(result_df) * 35),
        margin=dict(l=0, r=0, t=20, b=0),
    )
    st.plotly_chart(fig2, use_container_width=True)
