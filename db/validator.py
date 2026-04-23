"""データ品質バリデーター

スクレイプ後のデータ整合性を確認する。欠損率・値域外を検出するが、
処理は中断せず警告ログを出力するにとどめる。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass
class ValidationReport:
    errors:     list[str] = field(default_factory=list)
    warnings:   list[str] = field(default_factory=list)
    ok_count:   int = 0
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def summary(self) -> str:
        lines = [f"=== データ品質レポート ({self.checked_at.strftime('%Y-%m-%d %H:%M')}) ==="]
        lines.append(f"  OK チェック数 : {self.ok_count}")
        if self.warnings:
            lines.append(f"  警告          : {len(self.warnings)} 件")
            for w in self.warnings[:20]:
                lines.append(f"    WARNING: {w}")
            if len(self.warnings) > 20:
                lines.append(f"    ... 他 {len(self.warnings) - 20} 件")
        if self.errors:
            lines.append(f"  エラー        : {len(self.errors)} 件")
            for e in self.errors[:10]:
                lines.append(f"    ERROR: {e}")
        return "\n".join(lines)


# バリデーションルール定義
_RULES: dict[str, dict[str, dict[str, Any]]] = {
    "race_entries": {
        "finish_position": {"min": 1,    "max": 28,     "null_ok": True},
        "win_odds":        {"min": 1.0,  "max": 9999.9, "null_ok": True},
        "place_odds":      {"min": 1.0,  "max": 9999.9, "null_ok": True},
        "last_3f_time":    {"min": 30.0, "max": 45.0,   "null_ok": True},
        "horse_weight":    {"min": 350,  "max": 650,    "null_ok": True},
        "handicap_weight": {"min": 48.0, "max": 62.0,   "null_ok": True},
        "post_position":   {"min": 1,    "max": 28,     "null_ok": True},
    },
    "races": {
        "distance":   {"min": 800,  "max": 4000, "null_ok": False},
        "field_size": {"min": 1,    "max": 28,   "null_ok": True},
    },
    "training_times": {
        "total_time":  {"min": 40.0, "max": 90.0, "null_ok": True},
        "last_f_time": {"min": 10.0, "max": 20.0, "null_ok": True},
    },
}

# 各テーブルの主キー（エラーメッセージ用）
_PK_COLS: dict[str, list[str]] = {
    "race_entries":   ["race_id", "horse_id"],
    "races":          ["race_id"],
    "training_times": ["id"],
}

# 欠損率の警告閾値
_NULL_WARN_RATE = 0.10


class DataValidator:
    """DB 全体または特定レースのデータ品質を検証するクラス"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def validate(self) -> ValidationReport:
        """全テーブルを検証してレポートを返す"""
        report = ValidationReport()
        for table, col_rules in _RULES.items():
            self._validate_table(table, col_rules, report)
        logger.info(f"バリデーション完了: errors={len(report.errors)}, warnings={len(report.warnings)}")
        return report

    def validate_race(self, race_id: str) -> ValidationReport:
        """特定レースの出走データのみ検証する（スクレイプ直後の即時チェック用）"""
        report = ValidationReport()
        col_rules = _RULES.get("race_entries", {})
        pk_cols = _PK_COLS.get("race_entries", [])
        rows = self.session.execute(
            text("SELECT * FROM race_entries WHERE race_id = :rid"),
            {"rid": race_id},
        ).mappings().all()

        for row in rows:
            self._check_row(dict(row), col_rules, pk_cols, report)

        return report

    # ─────────────────────────────────────────────
    # 内部ロジック
    # ─────────────────────────────────────────────

    def _validate_table(
        self,
        table: str,
        col_rules: dict[str, dict[str, Any]],
        report: ValidationReport,
    ) -> None:
        try:
            rows = self.session.execute(text(f"SELECT * FROM {table}")).mappings().all()
        except Exception as e:
            report.warnings.append(f"テーブル {table} の読み込み失敗: {e}")
            return

        if not rows:
            return

        pk_cols = _PK_COLS.get(table, [])
        total = len(rows)

        # 欠損率チェック
        for col, rules in col_rules.items():
            null_count = sum(1 for r in rows if r.get(col) is None)
            null_rate  = null_count / total
            if not rules.get("null_ok") and null_count > 0:
                report.errors.append(
                    f"{table}.{col}: NULL 禁止カラムに {null_count} 件の NULL"
                )
            elif null_rate > _NULL_WARN_RATE:
                report.warnings.append(
                    f"{table}.{col}: 欠損率 {null_rate:.1%} ({null_count}/{total}件)"
                )

        # 値域チェック（最大200件サンプル）
        sample_rows = rows[:200]
        for row in sample_rows:
            self._check_row(dict(row), col_rules, pk_cols, report)

        report.ok_count += total
        logger.debug(f"{table}: {total:,} 件チェック完了")

    def _check_row(
        self,
        row: dict[str, Any],
        col_rules: dict[str, dict[str, Any]],
        pk_cols: list[str],
        report: ValidationReport,
    ) -> None:
        pk_str = ", ".join(f"{k}={row.get(k)}" for k in pk_cols)
        for col, rules in col_rules.items():
            val = row.get(col)
            if val is None:
                continue
            try:
                v = float(val)
            except (TypeError, ValueError):
                continue
            lo = rules.get("min")
            hi = rules.get("max")
            if lo is not None and v < lo:
                report.warnings.append(f"{col}={v} (下限 {lo} 未満) — {pk_str}")
            if hi is not None and v > hi:
                report.warnings.append(f"{col}={v} (上限 {hi} 超過) — {pk_str}")
