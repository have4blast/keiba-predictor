"""バックテストページ

過去データにおけるROI曲線・月別成績・競馬場別成績を表示する。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

st.set_page_config(
    page_title="バックテスト - 競馬予想AI",
    page_icon="📈",
    layout="wide",
)

# ─────────────────────────────────────────────
# キャッシュ付きロード関数
# ─────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_report() -> dict | None:
    """training_report.json を読み込む"""
    import json
    p = Path("models/training_report.json")
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


@st.cache_data(ttl=300)
def load_backtest_detail() -> pd.DataFrame:
    """
    バックテスト詳細データを取得する。

    training_report に含まれる場合はそれを使い、
    なければ特徴量 Parquet + モデルから再計算する。
    """
    report = load_report()
    if report and "backtest_records" in report:
        return pd.DataFrame(report["backtest_records"])

    # Parquet + モデルから再計算
    feat_path = Path("data/features/train.parquet")
    model_dir  = Path("models")
    if not feat_path.exists() or not (model_dir / "lgbm_win.pkl").exists():
        return pd.DataFrame()

    try:
        from model.predictor import Predictor
        from model.evaluate import run_backtest

        predictor = Predictor(str(model_dir))
        df = pd.read_parquet(feat_path)
        scores = predictor.predict(df)
        bt_df  = run_backtest(scores)
        return bt_df
    except Exception:
        return pd.DataFrame()


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
    report = load_report()
    if report:
        cv = report.get("cv_results", {})
        st.metric("Win AUC",   f"{cv.get('win_auc_mean', 0):.4f}")
        st.metric("Place AUC", f"{cv.get('place_auc_mean', 0):.4f}")
        st.caption(f"学習日: {report.get('trained_at', '不明')[:10]}")
    else:
        st.warning("モデル未学習")

# ─────────────────────────────────────────────
# メインコンテンツ
# ─────────────────────────────────────────────
st.title("📈 バックテスト")

report = load_report()
if report is None:
    st.warning("training_report.json が見つかりません。先にモデルを学習してください。")
    st.code("python scripts/train_model.py", language="bash")
    st.stop()

# ─────────────────────────────────────────────
# CV結果サマリー
# ─────────────────────────────────────────────
st.subheader("クロスバリデーション結果")
cv = report.get("cv_results", {})

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric(
        "Win AUC (平均)",
        f"{cv.get('win_auc_mean', 0):.4f}",
        f"± {cv.get('win_auc_std', 0):.4f}",
    )
with col2:
    st.metric(
        "Place AUC (平均)",
        f"{cv.get('place_auc_mean', 0):.4f}",
        f"± {cv.get('place_auc_std', 0):.4f}",
    )

bt_summary = report.get("backtest", {})
with col3:
    st.metric(
        "単勝的中率",
        f"{bt_summary.get('win_accuracy', 0):.1%}",
    )
with col4:
    roi_val = bt_summary.get("win_roi", 0)
    delta_color = "normal" if roi_val >= 0 else "inverse"
    st.metric(
        "単勝ROI",
        f"{roi_val:.1%}",
        delta=f"{roi_val:.1%}",
        delta_color=delta_color,
    )

st.markdown(f"学習日時: `{report.get('trained_at', '不明')}`　総レース数: `{bt_summary.get('total_races', 0):,}`")

st.markdown("---")

# ─────────────────────────────────────────────
# ROI曲線
# ─────────────────────────────────────────────
st.subheader("ROI 累積曲線")

bt_df = load_backtest_detail()

if bt_df.empty:
    st.info("バックテスト詳細データがありません。training_report.json に backtest_records キーを含めるか、特徴量 Parquet とモデルを用意してください。")
else:
    # 日付でソート
    if "date" in bt_df.columns:
        bt_df = bt_df.sort_values("date").reset_index(drop=True)

    # 累積利益・ROI の再計算（上書き）
    bt_df["cumulative_profit"]     = bt_df["profit"].cumsum()
    bt_df["cumulative_investment"] = bt_df["investment"].cumsum()
    bt_df["roi_curve"] = (
        bt_df["cumulative_profit"] / bt_df["cumulative_investment"]
    )
    bt_df["race_index"] = range(1, len(bt_df) + 1)

    # タブ
    tab_roi, tab_profit = st.tabs(["ROI推移", "累積利益推移"])

    with tab_roi:
        fig_roi = go.Figure()
        fig_roi.add_trace(go.Scatter(
            x=bt_df["race_index"],
            y=bt_df["roi_curve"] * 100,
            mode="lines",
            name="ROI (%)",
            line=dict(color="royalblue", width=2),
        ))
        fig_roi.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="損益分岐点")
        fig_roi.update_layout(
            xaxis_title="レース数",
            yaxis_title="ROI (%)",
            hovermode="x unified",
            height=400,
            margin=dict(l=0, r=0, t=20, b=0),
        )
        st.plotly_chart(fig_roi, use_container_width=True)

    with tab_profit:
        fig_profit = go.Figure()
        fig_profit.add_trace(go.Scatter(
            x=bt_df["race_index"],
            y=bt_df["cumulative_profit"],
            mode="lines",
            name="累積利益 (円)",
            line=dict(color="green", width=2),
            fill="tozeroy",
            fillcolor="rgba(0,200,0,0.1)",
        ))
        fig_profit.add_hline(y=0, line_dash="dash", line_color="red")
        fig_profit.update_layout(
            xaxis_title="レース数",
            yaxis_title="累積利益 (円)",
            hovermode="x unified",
            height=400,
            margin=dict(l=0, r=0, t=20, b=0),
        )
        st.plotly_chart(fig_profit, use_container_width=True)

    st.markdown("---")

    # ─────────────────────────────────────────────
    # 月別成績
    # ─────────────────────────────────────────────
    from model.evaluate import compute_monthly_stats, compute_venue_stats

    st.subheader("月別成績")
    monthly_df = compute_monthly_stats(bt_df)
    if not monthly_df.empty:
        col_m1, col_m2 = st.columns([2, 1])
        with col_m1:
            fig_monthly = px.bar(
                monthly_df,
                x="month",
                y="roi",
                color="roi",
                color_continuous_scale="RdYlGn",
                labels={"month": "月", "roi": "ROI"},
                title="月別 ROI",
            )
            fig_monthly.add_hline(y=0, line_dash="dash", line_color="gray")
            fig_monthly.update_layout(
                height=350,
                margin=dict(l=0, r=0, t=40, b=0),
                showlegend=False,
            )
            st.plotly_chart(fig_monthly, use_container_width=True)

        with col_m2:
            disp_monthly = monthly_df.copy()
            disp_monthly["的中率"] = disp_monthly["accuracy"].map("{:.1%}".format)
            disp_monthly["ROI"]    = disp_monthly["roi"].map("{:.1%}".format)
            disp_monthly["利益"]   = disp_monthly["profit"].map("{:,.0f}円".format)
            st.dataframe(
                disp_monthly[["month", "races", "hits", "的中率", "ROI", "利益"]].rename(
                    columns={"month": "月", "races": "レース数", "hits": "的中"}
                ),
                use_container_width=True,
                hide_index=True,
            )

    st.markdown("---")

    # ─────────────────────────────────────────────
    # 競馬場別成績
    # ─────────────────────────────────────────────
    st.subheader("競馬場別成績")
    venue_df = compute_venue_stats(bt_df)
    if not venue_df.empty:
        col_v1, col_v2 = st.columns([2, 1])
        with col_v1:
            fig_venue = px.bar(
                venue_df,
                x="venue",
                y="roi",
                color="roi",
                color_continuous_scale="RdYlGn",
                labels={"venue": "競馬場", "roi": "ROI"},
                title="競馬場別 ROI",
            )
            fig_venue.add_hline(y=0, line_dash="dash", line_color="gray")
            fig_venue.update_layout(
                height=350,
                margin=dict(l=0, r=0, t=40, b=0),
                showlegend=False,
            )
            st.plotly_chart(fig_venue, use_container_width=True)

        with col_v2:
            disp_venue = venue_df.copy()
            disp_venue["的中率"] = disp_venue["accuracy"].map("{:.1%}".format)
            disp_venue["ROI"]    = disp_venue["roi"].map("{:.1%}".format)
            disp_venue["利益"]   = disp_venue["profit"].map("{:,.0f}円".format)
            st.dataframe(
                disp_venue[["venue", "races", "hits", "的中率", "ROI", "利益"]].rename(
                    columns={"venue": "競馬場", "races": "レース数", "hits": "的中"}
                ),
                use_container_width=True,
                hide_index=True,
            )
