"""v0.3.0-beta 长期记忆 6 种 fact_type Pydantic schema

参考 spec 第 643-661 行的 _EXTRACT_PROMPT 设计:
- user_attribute: 用户固有属性(数学不好 / 目标清华)
- preference: 偏好(避开 985 / 喜欢表格)
- conversation_outcome: 对话结论(决定考清华)
- open_question: 未解决问题(下次继续)
- person_mention: 提到的人/校/专业
- timeline_event: 时间事件(10 月报名)

extractor 用这些 schema 引导 LLM 输出结构化 JSON。
"""
from __future__ import annotations

from typing import Literal, Union

from pydantic import BaseModel, Field

FactType = Literal[
    "user_attribute",
    "preference",
    "conversation_outcome",
    "open_question",
    "person_mention",
    "timeline_event",
]


class FactBase(BaseModel):
    """所有 fact 共享的字段"""

    fact_type: FactType
    text: str = Field(..., min_length=1, max_length=500, description="事实的简短描述")
    subject: str = Field("", max_length=200, description="涉及的人/校/专业(可选)")
    keywords: list[str] = Field(default_factory=list, description="检索关键词")
    confidence: float = Field(0.8, ge=0.0, le=1.0, description="抽取置信度")


class UserAttributeFact(FactBase):
    fact_type: Literal["user_attribute"] = "user_attribute"


class PreferenceFact(FactBase):
    fact_type: Literal["preference"] = "preference"


class ConversationOutcomeFact(FactBase):
    fact_type: Literal["conversation_outcome"] = "conversation_outcome"


class OpenQuestionFact(FactBase):
    fact_type: Literal["open_question"] = "open_question"


class PersonMentionFact(FactBase):
    fact_type: Literal["person_mention"] = "person_mention"
    # subject 是必填(提到具体的人/校/专业)
    subject: str = Field(..., min_length=1, max_length=200, description="人/校/专业名称")


class TimelineEventFact(FactBase):
    fact_type: Literal["timeline_event"] = "timeline_event"


FactUnion = Union[
    UserAttributeFact,
    PreferenceFact,
    ConversationOutcomeFact,
    OpenQuestionFact,
    PersonMentionFact,
    TimelineEventFact,
]


# confidence 阈值(低于此值不入库,spec M-3 风险)
MIN_CONFIDENCE = 0.7
