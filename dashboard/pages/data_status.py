"""データ状況ページ

DBのテーブル件数・スクレイピング進捗・モデル情報を表示する。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime

st.set_page_config(
    page_title="データ状況 - 競馬予想AI",
    page_icon="🗄️",
    layout="wide",
)

# ─────────────────────────────────────────────
# キャッシュ付きロード関数
# ─────────────────────────────────────────────

@st.cache_data(ttl=30)
def get_db_stats() -> dict:
    """DB の各テーブル件数を取得する"""
    db_path = Path("data/keiba.db")
    if not db_path.exists():
        return {}

    from sqlalchemy import create_engine, text
    engine = create_engine(f"sqlite:///{db_path}")

    tables = [
        "races", "race_entries", "horses", "jockeys",
        "trainers", "stallions", "odds_history", "courses",
    ]
    stats = {}
    with engine.connect() as conn:
        for table in tables:
            try:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                stats[table] = result.scalar()
            except Exception:
                stats[table] = None
    return stats


@st.cache_data(ttl=30)
def get_date_range() -> dict:
    """レースデータの日付範囲を取得する"""
    db_path = Path("data/keiba.db")
    if not db_path.exists():
        return {}

    from sqlalchemy import create_engine, text
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT MIN(date), MAX(date), COUNT(DISTINCT date) FROM races")
            )
            row = result.fetchone()
            if row:
                return {
                    "min_date":   row[0],
                    "max_date":   row[1],
                    "total_days": row[2],
                }
    except Exception:
        pass
    return {}


@st.cache_data(ttl=30)
def get_upcoming_count() -> int:
    """finish_position が NULL の出走予定レース件数を取得する"""
    db_path = Path("data/keiba.db")
    if not db_path.exists():
        return 0

    from sqlalchemy import create_engine, text
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT COUNT(DISTINCT race_id) FROM race_entries WHERE finish_position IS NULL")
            )
            return result.scalar() or 0
    except Exception:
        return 0


@st.cache_data(ttl=300)
def load_report() -> dict | None:
    """training_report.json を読み込む"""
    import json
    p = Path("models/training_report.json")
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def get_file_size(path: Path) -> str:
    """ファイルサイズを人間が読みやすい形式で返す"""
    if not path.exists():
        return "—"
    size = path.stat().st_size
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def get_mtime(path: Path) -> str:
    """ファイルの最終更新日時を返す"""
    if not path.exists():
        return "—"
    mtime = path.stat().st_mtime
    return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")


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

    st.markdown("---")
    if st.button("🔄 データ更新", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ─────────────────────────────────────────────
# メインコンテンツ
# ─────────────────────────────────────────────
st.title("🗄️ データ状況")

# ─────────────────────────────────────────────
# DBファイル状況
# ─────────────────────────────────────────────
st.subheader("データベース状況")

db_path     = Path("data/keiba.db")
feat_path   = Path("data/features/train.parquet")
model_win   = Path("models/lgbm_win.pkl")
model_place = Path("models/lgbm_place.pkl")
encoder_p   = Path("models/encoder.pkl")

col1, col2, col3 = st.columns(3)
with col1:
    status = "✅ 存在" if db_path.exists() else "❌ なし"
    st.metric("SQLite DB", status)
    if db_path.exists():
        st.caption(f"サイズ: {get_file_size(db_path)}　更新: {get_mtime(db_path)}")

with col2:
    status = "✅ 存在" if feat_path.exists() else "❌ なし"
    st.metric("特徴量 Parquet", status)
    if feat_path.exists():
        st.caption(f"サイズ: {get_file_size(feat_path)}　更新: {get_mtime(feat_path)}")

with col3:
    model_ok = model_win.exists() and model_place.exists()
    status   = "✅ 学習済み" if model_ok else "❌ 未学習"
    st.metric("モデルファイル", status)
    if model_win.exists():
        st.caption(f"Win: {get_mtime(model_win)}")

st.markdown("---")

# ─────────────────────────────────────────────
# テーブル件数
# ─────────────────────────────────────────────
st.subheader("テーブル別レコード数")

db_stats = get_db_stats()
if not db_stats:
    st.info("DBが存在しないか、まだデータが投入されていません。")
else:
    table_labels = {
        "races":        "レース",
        "race_entries": "出走エントリ",
        "horses":       "馬",
        "jockeys":      "騎手",
        "trainers":     "調教師",
        "stallions":    "種牡馬",
        "odds_history": "オッズ履歴",
        "courses":      "コース情報",
    }
    stats_rows = [
        {"テーブル": table_labels.get(k, k), "件数": v if v is not None else "エラー"}
        for k, v in db_stats.items()
    ]
    stats_df = pd.DataFrame(stats_rows)

    # 棒グラフ
    import plotly.express as px
    numeric_df = stats_df[stats_df["件数"].apply(lambda x: isinstance(x, int))]
    if not numeric_df.empty:
        fig = px.bar(
            numeric_df,
            x="テーブル",
            y="件数",
            color="件数",
            color_continuous_scale="Blues",
            labels={"件数": "レコード数"},
        )
        fig.update_layout(
            height=350,
            showlegend=False,
            margin=dict(l=0, r=0, t=20, b=0),
        )
        st.plotly_chart(fig, use_container_width=True)

    # テーブル
    st.dataframe(
        stats_df.style.format({"件数": lambda x: f"{x:,}" if isinstance(x, int) else x}),
        use_container_width=True,
        hide_index=True,
    )

# ─────────────────────────────────────────────
# レースデータ日付範囲
# ─────────────────────────────────────────────
date_info = get_date_range()
if date_info:
    st.markdown("---")
    st.subheader("収集済みデータ期間")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("最古のレース日", date_info.get("min_date", "—"))
    with c2:
        st.metric("最新のレース日", date_info.get("max_date", "—"))
    with c3:
        st.metric("収集日数", f"{date_info.get('total_days', 0):,} 日")

# ─────────────────────────────────────────────
# 出走予定レース数
# ─────────────────────────────────────────────
upcoming = get_upcoming_count()
st.markdown("---")
st.subheader("出走予定データ")
if upcoming > 0:
    st.success(f"予測待ちレース数: **{upcoming} レース**")
else:
    st.info("出走予定データはありません。")

st.markdown("---")

# ─────────────────────────────────────────────
# モデル情報
# ─────────────────────────────────────────────
st.subheader("モデル情報")
report = load_report()
if report is None:
    st.warning("training_report.json が存在しません。")
else:
    cv = report.get("cv_results", {})
    bt = report.get("backtest", {})

    mcol1, mcol2, mcol3, mcol4 = st.columns(4)
    with mcol1:
        st.metric("Win AUC",   f"{cv.get('win_auc_mean', 0):.4f}", f"± {cv.get('win_auc_std', 0):.4f}")
    with mcol2:
        st.metric("Place AUC", f"{cv.get('place_auc_mean', 0):.4f}", f"± {cv.get('place_auc_std', 0):.4f}")
    with mcol3:
        st.metric("単勝的中率", f"{bt.get('win_accuracy', 0):.1%}")
    with mcol4:
        st.metric("単勝ROI",   f"{bt.get('win_roi', 0):.1%}")

    with st.expander("詳細情報を表示"):
        st.json({
            "学習日時":        report.get("trained_at"),
            "特徴量数":        report.get("n_features"),
            "学習データ件数":  report.get("n_samples"),
            "総レース数":      bt.get("total_races"),
            "的中数":          bt.get("hits"),
        })

# ─────────────────────────────────────────────
# コマンド一覧
# ─────────────────────────────────────────────
st.markdown("---")
st.subheader("データ管理コマンド")
with st.expander("コマンドを表示"):
    st.markdown("**過去データ収集**")
    st.code("python scripts/scrape_historical.py --start 2023-01-01 --end 2023-12-31", language="bash")

    st.markdown("**翌日出走表取得**")
    st.code("python scripts/scrape_upcoming.py --date 2024-01-01", language="bash")

    st.markdown("**特徴量生成**")
    st.code("python scripts/build_features.py", language="bash")

    st.markdown("**モデル学習**")
    st.code("python scripts/train_model.py", language="bash")

    st.markdown("**ダッシュボード起動**")
    st.code("streamlit run dashboard/app.py", language="bash")
