"""v0.3.0-beta 6 种 fact_type schema 验证"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from yantu.memory.schemas import (
    ConversationOutcomeFact,
    MIN_CONFIDENCE,
    OpenQuestionFact,
    PersonMentionFact,
    PreferenceFact,
    TimelineEventFact,
    UserAttributeFact,
)


class TestFactSchemas:
    """6 种 fact_type Pydantic 验证"""

    def test_user_attribute_valid(self):
        f = UserAttributeFact(
            fact_type="user_attribute",
            text="用户数学较弱,自评 60-70 分",
            subject="数学",
            keywords=["数学", "成绩"],
            confidence=0.9,
        )
        assert f.fact_type == "user_attribute"
        assert f.confidence == 0.9

    def test_preference_valid(self):
        f = PreferenceFact(
            fact_type="preference",
            text="用户希望避开 985",
            confidence=0.85,
        )
        assert f.fact_type == "preference"

    def test_conversation_outcome_valid(self):
        f = ConversationOutcomeFact(
            fact_type="conversation_outcome",
            text="用户决定考清华计算机专硕",
            confidence=0.95,
        )
        assert f.fact_type == "conversation_outcome"

    def test_open_question_valid(self):
        f = OpenQuestionFact(
            fact_type="open_question",
            text="用户还没决定是学硕还是专硕",
            confidence=0.7,
        )
        assert f.fact_type == "open_question"

    def test_person_mention_valid(self):
        f = PersonMentionFact(
            fact_type="person_mention",
            text="用户提到学长在北大读研",
            subject="北大",
            confidence=0.8,
        )
        assert f.fact_type == "person_mention"
        assert f.subject == "北大"

    def test_timeline_event_valid(self):
        f = TimelineEventFact(
            fact_type="timeline_event",
            text="用户提到 10 月开始网上报名",
            confidence=0.9,
        )
        assert f.fact_type == "timeline_event"

    def test_fact_type_mismatch_raises(self):
        """fact_type 必须匹配类名,否则 Pydantic 拒"""
        with pytest.raises(ValidationError):
            UserAttributeFact(
                fact_type="preference",  # 错的
                text="test",
                confidence=0.5,
            )

    def test_confidence_out_of_range_raises(self):
        with pytest.raises(ValidationError):
            UserAttributeFact(
                fact_type="user_attribute",
                text="test",
                confidence=1.5,  # 超出范围
            )

    def test_text_required_not_empty(self):
        with pytest.raises(ValidationError):
            UserAttributeFact(
                fact_type="user_attribute",
                text="",  # 空
                confidence=0.5,
            )

    def test_min_confidence_constant(self):
        """confidence 阈值固定 0.7(spec M-3)"""
        assert MIN_CONFIDENCE == 0.7
