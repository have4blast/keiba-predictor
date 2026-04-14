"""Streamlit ダッシュボード エントリポイント

起動方法:
    streamlit run dashboard/app.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
from pathlib import Path

st.set_page_config(
    page_title="競馬予想AI",
    page_icon="🏇",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def load_predictor():
    """モデルをキャッシュしてロードする"""
    model_dir = Path("models")
    if not (model_dir / "lgbm_win.pkl").exists():
        return None
    from model.predictor import Predictor
    return Predictor(str(model_dir))


@st.cache_data(ttl=300)
def load_report():
    """training_report.json を読み込む"""
    import json
    p = Path("models/training_report.json")
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


# サイドバー
with st.sidebar:
    st.title("🏇 競馬予想AI")
    st.markdown("---")
    st.page_link("dashboard/app.py",              label="🏠 ホーム",       icon="🏠")
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

# メインコンテンツ
st.title("競馬予想AI ダッシュボード")
st.markdown("""
このダッシュボードでは以下の機能を提供します：

| ページ | 説明 |
|--------|------|
| 📊 予測結果 | 今日・明日のレース出走馬スコア一覧 |
| 📈 バックテスト | 過去のROI曲線・成績グラフ |
| 🗄️ データ状況 | DB件数・スクレイピング進捗管理 |

左のサイドバーからページを選択してください。
""")

col1, col2, col3 = st.columns(3)
with col1:
    st.info("**7カテゴリ・53特徴量**\n\n馬・騎手・調教師・レース条件・オッズ・相対・馬間インタラクション")
with col2:
    st.info("**LightGBM + GroupKFold**\n\n勝利モデル・複勝モデルの2種類を提供")
with col3:
    st.info("**データリーク防止**\n\n全ローリング特徴量に shift(1) を適用")
