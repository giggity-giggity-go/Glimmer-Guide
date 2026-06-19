"""SQLAlchemy ORM + Pydantic 数据模型"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import String, Integer, Float, DateTime, Text, JSON, Boolean, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


# ==================== Pydantic 模型 ====================


class PersonalInfo(BaseModel):
    """个人信息"""

    exam_year: int = Field(2026, ge=2024, le=2030, description="考研年份")
    name: str = Field("steven", description="昵称")
    study_mode: str = Field("全日制", description="学习方式:全日制/非全日制")
    degree_type: str = Field("专硕", description="学位类型:学硕/专硕")
    target_discipline_code: Optional[str] = Field(
        None, description="目标学科代码,如 095136"
    )
    target_schools: List[str] = Field(
        default_factory=list, description="目标院校列表"
    )


class ScoreRecord(BaseModel):
    """分数"""

    politics: Optional[int] = Field(None, ge=0, le=100)
    english_2: Optional[int] = Field(None, ge=0, le=100, description="英语二")
    math: Optional[int] = Field(None, ge=0, le=150, description="数学 0-150")
    specialty_1: Optional[int] = Field(None, ge=0, le=150, description="业务课一")
    specialty_2: Optional[int] = Field(None, ge=0, le=150, description="业务课二")


class UserPreferences(BaseModel):
    """偏好"""

    avoid_math: bool = Field(False, description="是否避开数学")
    avoid_985: bool = Field(False, description="是否排除 985")
    want_211: Optional[bool] = Field(None, description="是否要 211(None=随便)")
    specialty_keywords: List[str] = Field(
        default_factory=list, description="业务课关键词"
    )


class RegionPreference(BaseModel):
    """地区偏好"""

    preferred: List[str] = Field(default_factory=list, description="偏好地区")
    acceptable: List[str] = Field(default_factory=list, description="可接受地区")


class TimelineConfig(BaseModel):
    """时间轴(只到复试,不涉及录取)"""

    registration: Optional[str] = Field(None, description="预报名时间")
    online_confirm: Optional[str] = Field(None, description="网上确认时间")
    preliminary: Optional[str] = Field(None, description="初试时间")
    retest: Optional[str] = Field(None, description="复试时间")


class UserProfile(BaseModel):
    """用户画像(完整结构)"""

    personal: PersonalInfo = Field(default_factory=PersonalInfo)
    scores: ScoreRecord = Field(default_factory=ScoreRecord)
    preferences: UserPreferences = Field(default_factory=UserPreferences)
    regions: RegionPreference = Field(default_factory=RegionPreference)
    timeline: TimelineConfig = Field(default_factory=TimelineConfig)

    @model_validator(mode="after")
    def check_consistency(self):
        # 数学极低但没勾选 avoid_math → 提示
        if (
            self.scores.math is not None
            and self.scores.math < 60
            and not self.preferences.avoid_math
        ):
            # 不报错,只记录
            pass
        return self

    def to_prompt(self) -> str:
        """渲染为 LangGraph system prompt 顶部可注入的文本"""
        lines = ["[用户画像]"]
        p = self.personal
        lines.append(
            f"考试年份 {p.exam_year},学位 {p.study_mode}/{p.degree_type},"
            f"目标学科代码 {p.target_discipline_code or '未指定'}"
        )
        if p.target_schools:
            lines.append(f"目标院校: {', '.join(p.target_schools)}")
        s = self.scores
        score_parts = []
        if s.politics is not None:
            score_parts.append(f"政治 {s.politics}")
        if s.english_2 is not None:
            score_parts.append(f"英语二 {s.english_2}")
        if s.math is not None:
            score_parts.append(f"数学 {s.math}")
        if score_parts:
            lines.append(f"已知分数: {' / '.join(score_parts)}")
        prefs = self.preferences
        pref_parts = []
        if prefs.avoid_math:
            pref_parts.append("避开数学")
        if prefs.avoid_985:
            pref_parts.append("排除 985")
        if prefs.want_211 is True:
            pref_parts.append("希望 211")
        elif prefs.want_211 is False:
            pref_parts.append("不要 211")
        if prefs.specialty_keywords:
            pref_parts.append(
                f"业务课关键词: {', '.join(prefs.specialty_keywords)}"
            )
        if pref_parts:
            lines.append(f"偏好: {'; '.join(pref_parts)}")
        if self.regions.preferred:
            lines.append(f"偏好地区: {', '.join(self.regions.preferred)}")
        if self.regions.acceptable:
            lines.append(f"可接受地区: {', '.join(self.regions.acceptable)}")
        return "\n".join(lines)


# ==================== SQLAlchemy ORM(用于知识库) ====================


class Base(DeclarativeBase):
    pass


class School(Base):
    """院校表"""

    __tablename__ = "schools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(20), index=True, nullable=True)
    region: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    tier: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # 985/211/双非
    website: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Program(Base):
    """硕士专业表"""

    __tablename__ = "programs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    school_name: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    discipline_code: Mapped[str] = mapped_column(
        String(20), index=True, nullable=False
    )  # 095136
    discipline_name: Mapped[str] = mapped_column(String(200), nullable=False)
    degree_type: Mapped[str] = mapped_column(String(20), default="专硕")
    study_mode: Mapped[str] = mapped_column(String(20), default="全日制")
    research_direction: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True
    )
    enroll_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    exam_subjects: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # JSON 字符串
    retest_subjects: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    year: Mapped[int] = mapped_column(Integer, default=2026)
    source: Mapped[str] = mapped_column(String(20), default="yz.chsi.com.cn")


class Notice(Base):
    """招生简章"""

    __tablename__ = "notices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id: Mapped[Optional[int]] = mapped_column(Integer, index=True, nullable=True)
    school_name: Mapped[Optional[str]] = mapped_column(
        String(200), index=True, nullable=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    year: Mapped[int] = mapped_column(Integer, default=2026)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Reference(Base):
    """参考书目(用于复试/初试业务课)"""

    __tablename__ = "references"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_name: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    discipline_code: Mapped[Optional[str]] = mapped_column(
        String(20), index=True, nullable=True
    )
    subject_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    subject_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    stage: Mapped[str] = mapped_column(
        String(20), default="初试"
    )  # 初试/复试/加试
    book_title: Mapped[str] = mapped_column(String(500), nullable=False)
    authors: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    publisher: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    edition: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)


class UserProfileRecord(Base):
    """用户画像持久化(单行,带 version)"""

    __tablename__ = "user_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    profile_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


# ==================== v0.3.0 多会话 + 长短期记忆 ====================


class Session(Base):
    """会话元数据(侧边栏列表用)

    thread_id 是 LangGraph Checkpointer 的会话隔离键,UI 层用人类可读的 title。
    """

    __tablename__ = "sessions"

    thread_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), default="default", index=True)
    title: Mapped[str] = mapped_column(String(100), default="新会话")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), index=True
    )
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    last_tokens: Mapped[int] = mapped_column(Integer, default=0)
    compressed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    compression_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_sessions_user_updated", "user_id", "updated_at"),
        Index("ix_sessions_user_pinned", "user_id", "is_pinned", "updated_at"),
    )


class MemoryFact(Base):
    """长期记忆事实(LLM 抽取的结构化记忆)

    fact_type 取值:
    - user_attribute: 用户固有属性(数学不好 / 目标清华)
    - preference: 偏好(避开 985 / 喜欢表格)
    - conversation_outcome: 对话结论(决定考清华)
    - open_question: 未解决问题(下次继续)
    - person_mention: 提到的人/校/专业
    - timeline_event: 时间事件(10 月报名)
    """

    __tablename__ = "memory_facts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(50), default="default", index=True)
    fact_type: Mapped[str] = mapped_column(String(50), index=True)
    fact_value: Mapped[dict] = mapped_column(JSON)
    subject: Mapped[Optional[str]] = mapped_column(String(200), index=True, nullable=True)
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    source_thread: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_accessed_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    access_count: Mapped[int] = mapped_column(Integer, default=0)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    user_corrected_value: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_facts_user_subject", "user_id", "subject"),
        Index("ix_facts_user_type", "user_id", "fact_type"),
    )


class UserSetting(Base):
    """用户设置(单行 id=default,key-value 扩展)"""

    __tablename__ = "user_settings"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default="default")
    context_window_tokens: Mapped[int] = mapped_column(Integer, default=30000)
    context_keep_recent_messages: Mapped[int] = mapped_column(Integer, default=10)
    memory_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    memory_injection_count: Mapped[int] = mapped_column(Integer, default=10)
    memory_extract_every_n_turns: Mapped[int] = mapped_column(Integer, default=3)
    sidebar_default_view: Mapped[str] = mapped_column(String(20), default="recent")
    extra: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
