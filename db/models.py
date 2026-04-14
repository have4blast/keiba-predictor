"""SQLAlchemy ORM モデル定義（8テーブル）"""
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Date, DateTime,
    Boolean, Text, ForeignKey, Index,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Race(Base):
    """レース基本情報"""
    __tablename__ = "races"

    race_id         = Column(String, primary_key=True)   # 例: 202401010101
    date            = Column(Date, nullable=False)
    venue           = Column(String, nullable=False)      # 東京・中山等
    course_id       = Column(String, ForeignKey("courses.course_id"), nullable=True)
    distance        = Column(Integer, nullable=False)     # メートル
    surface         = Column(String, nullable=False)      # 芝/ダート/障害
    weather         = Column(String, nullable=True)       # 晴/曇/雨/小雨/雪
    going           = Column(String, nullable=True)       # 良/稍重/重/不良
    grade           = Column(String, nullable=True)       # G1/G2/G3/OP/新馬 等
    field_size      = Column(Integer, nullable=True)
    lap_times       = Column(Text, nullable=True)         # JSON配列
    straight_length = Column(Float, nullable=True)
    num_curves      = Column(Integer, nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    entries = relationship("RaceEntry", back_populates="race")


class RaceEntry(Base):
    """出走・結果"""
    __tablename__ = "race_entries"

    race_id          = Column(String, ForeignKey("races.race_id"), primary_key=True)
    horse_id         = Column(String, ForeignKey("horses.horse_id"), primary_key=True)
    jockey_id        = Column(String, ForeignKey("jockeys.jockey_id"), nullable=True)
    trainer_id       = Column(String, ForeignKey("trainers.trainer_id"), nullable=True)
    post_position    = Column(Integer, nullable=True)     # 枠番
    finish_position  = Column(Integer, nullable=True)     # NULL=出走予定
    time             = Column(Float, nullable=True)       # タイム（秒）
    last_3f_time     = Column(Float, nullable=True)       # 上がり3F（秒）
    win_odds         = Column(Float, nullable=True)
    place_odds       = Column(Float, nullable=True)
    quinella_odds    = Column(Text, nullable=True)        # JSON
    trifecta_odds    = Column(Text, nullable=True)        # JSON
    horse_weight     = Column(Integer, nullable=True)     # 馬体重（kg）
    weight_diff      = Column(Integer, nullable=True)     # 前走比増減
    handicap_weight  = Column(Float, nullable=True)       # 斤量（kg）
    running_style    = Column(String, nullable=True)      # 逃/先/差/追/マ
    corner_positions = Column(Text, nullable=True)        # JSON [1,2,3,4]
    created_at       = Column(DateTime, default=datetime.utcnow)
    updated_at       = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    race    = relationship("Race", back_populates="entries")
    horse   = relationship("Horse", back_populates="entries")
    jockey  = relationship("Jockey", back_populates="entries")
    trainer = relationship("Trainer", back_populates="entries")

    __table_args__ = (
        Index("idx_race_entries_horse",   "horse_id",   "race_id"),
        Index("idx_race_entries_jockey",  "jockey_id",  "race_id"),
        Index("idx_race_entries_trainer", "trainer_id", "race_id"),
    )


class Horse(Base):
    """馬マスタ"""
    __tablename__ = "horses"

    horse_id          = Column(String, primary_key=True)
    name              = Column(String, nullable=False)
    sex               = Column(String, nullable=True)    # 牡/牝/セン
    birth_date        = Column(Date, nullable=True)
    trainer_id        = Column(String, ForeignKey("trainers.trainer_id"), nullable=True)
    sire_id           = Column(String, ForeignKey("stallions.horse_id"), nullable=True)
    dam_id            = Column(String, ForeignKey("stallions.horse_id"), nullable=True)
    broodmare_sire_id = Column(String, ForeignKey("stallions.horse_id"), nullable=True)
    created_at        = Column(DateTime, default=datetime.utcnow)
    updated_at        = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    entries = relationship("RaceEntry", back_populates="horse")


class Jockey(Base):
    """騎手マスタ"""
    __tablename__ = "jockeys"

    jockey_id  = Column(String, primary_key=True)
    name       = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    entries = relationship("RaceEntry", back_populates="jockey")


class Trainer(Base):
    """調教師マスタ"""
    __tablename__ = "trainers"

    trainer_id = Column(String, primary_key=True)
    name       = Column(String, nullable=False)
    stable     = Column(String, nullable=True)   # 栗東/美浦
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    entries = relationship("RaceEntry", back_populates="trainer")


class Stallion(Base):
    """血統マスタ（父・母・母父）"""
    __tablename__ = "stallions"

    horse_id   = Column(String, primary_key=True)
    name       = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class OddsHistory(Base):
    """オッズ変動履歴"""
    __tablename__ = "odds_history"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    race_id    = Column(String, ForeignKey("races.race_id"), nullable=False)
    horse_id   = Column(String, ForeignKey("horses.horse_id"), nullable=False)
    timestamp  = Column(DateTime, nullable=False)
    win_odds   = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_odds_history_race_horse", "race_id", "horse_id"),
    )


class Course(Base):
    """コース特性マスタ"""
    __tablename__ = "courses"

    course_id       = Column(String, primary_key=True)  # 例: tokyo_turf_2000
    venue           = Column(String, nullable=False)
    surface         = Column(String, nullable=False)
    distance        = Column(Integer, nullable=False)
    straight_length = Column(Float, nullable=True)
    num_curves      = Column(Integer, nullable=True)
    has_slope       = Column(Boolean, default=False)
    course_note     = Column(Text, nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
