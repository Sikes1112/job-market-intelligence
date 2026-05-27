from __future__ import annotations

from backend.monetization.segments import (
    AudienceSegmentKey,
    BuyerSegmentKey,
    SegmentCategory,
    audience_segment_definitions,
    buyer_segment_definitions,
)


def test_required_audience_segments_exist_with_metadata() -> None:
    segments = {segment.key: segment for segment in audience_segment_definitions()}

    assert set(segments) == {
        AudienceSegmentKey.STUDENTS,
        AudienceSegmentKey.EARLY_CAREER_JOB_SEEKERS,
        AudienceSegmentKey.RELOCATION_CANDIDATES,
        AudienceSegmentKey.PARENTS_ADVISORS,
    }
    for segment in segments.values():
        assert segment.category is SegmentCategory.AUDIENCE
        assert segment.label
        assert segment.description
        assert segment.use_cases


def test_required_buyer_segments_exist_and_are_distinct_from_audiences() -> None:
    buyers = {segment.key: segment for segment in buyer_segment_definitions()}
    audiences = {segment.key for segment in audience_segment_definitions()}

    assert set(buyers) == {
        BuyerSegmentKey.CAREER_CENTERS,
        BuyerSegmentKey.BOOTCAMPS,
        BuyerSegmentKey.UNIVERSITIES,
        BuyerSegmentKey.WORKFORCE_BOARDS,
    }
    assert not set(buyers).intersection(audiences)
    for segment in buyers.values():
        assert segment.category is SegmentCategory.BUYER
        assert segment.label
        assert segment.description
        assert segment.use_cases

