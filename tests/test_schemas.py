"""Unit tests for schema enums and threshold validation"""
import pytest


class TestEnums:
    def test_frequency_enum_values(self):
        """Test that frequency enum has expected values"""
        from schemas import FrequencyEnum
        
        assert FrequencyEnum.daily.value == "daily"
        assert FrequencyEnum.weekly.value == "weekly"
        assert FrequencyEnum.monthly.value == "monthly"
    
    def test_threshold_is_float(self):
        """Test that threshold is now a float field not an enum"""
        from schemas import ProfileCreate
        import inspect
        
        fields = ProfileCreate.model_fields
        assert 'threshold' in fields
        assert fields['threshold'].default == 0.6
    
    def test_source_enum_values(self):
        """Test that source enum has expected values"""
        from schemas import SourceEnum
        
        assert SourceEnum.user.value == "user"
        assert SourceEnum.arxiv.value == "arxiv"
    
    def test_mode_enum_values(self):
        """Test that mode enum has expected values"""
        from schemas import ModeEnum
        
        assert ModeEnum.abstract.value == "abstract"
        assert ModeEnum.full.value == "full"
    
    def test_type_enum_values(self):
        """Test that type enum has expected values"""
        from schemas import TypeEnum
        
        assert TypeEnum.abstract.value == "abstract"
        assert TypeEnum.section.value == "section"
    
    def test_status_enum_values(self):
        """Test that status enum has expected values"""
        from schemas import StatusEnum
        
        assert StatusEnum.sent.value == "sent"
        assert StatusEnum.failed.value == "failed"


class TestThreshold:
    def test_threshold_default_value(self):
        """Test that threshold defaults to 0.6"""
        from schemas import ProfileCreate
        profile = ProfileCreate(
            user_id=1,
            name="test",
            keywords=["ml"],
            categories=["cs.LG"],
            frequency="weekly"
        )
        assert profile.threshold == 0.6

    def test_threshold_accepts_float(self):
        """Test that threshold accepts a float value"""
        from schemas import ProfileCreate
        profile = ProfileCreate(
            user_id=1,
            name="test",
            keywords=["ml"],
            categories=["cs.LG"],
            frequency="weekly",
            threshold=0.55
        )
        assert profile.threshold == 0.55

    def test_threshold_range(self):
        """Test threshold values across expected range"""
        from schemas import ProfileCreate
        for val in [0.4, 0.5, 0.6, 0.75]:
            profile = ProfileCreate(
                user_id=1,
                name="test",
                keywords=["ml"],
                categories=["cs.LG"],
                frequency="weekly",
                threshold=val
            )
            assert profile.threshold == val


class TestEnumMembership:
    @pytest.mark.parametrize("enum_class,expected_members", [
        ("FrequencyEnum", ["daily", "weekly", "monthly"]),
        ("SourceEnum", ["user", "arxiv"]),
        ("ModeEnum", ["abstract", "full"]),
        ("TypeEnum", ["abstract", "section"]),
    ])
    def test_enum_has_all_members(self, enum_class, expected_members):
        """Test that enums have all expected members"""
        import schemas
        enum = getattr(schemas, enum_class)
        
        for member in expected_members:
            assert hasattr(enum, member)


class TestProcessingRunSchemas:
    def test_create_defaults(self):
        """Test ProcessingRunCreate defaults match the ProcessingRun model"""
        from schemas import ProcessingRunCreate
        run = ProcessingRunCreate(run_type="arxiv_ingest")
        assert run.status == "started"
        assert run.category is None
        assert run.papers_processed == 0

    def test_create_explicit_values(self):
        """Test ProcessingRunCreate preserves explicitly passed values"""
        from schemas import ProcessingRunCreate
        run = ProcessingRunCreate(
            run_type="arxiv_ingest",
            category="cs.LG",
            status="completed",
            papers_processed=12,
        )
        assert run.category == "cs.LG"
        assert run.status == "completed"
        assert run.papers_processed == 12

    def test_update_all_optional(self):
        """Test ProcessingRunUpdate fields all default to None"""
        from schemas import ProcessingRunUpdate
        update = ProcessingRunUpdate()
        assert update.status is None
        assert update.papers_processed is None
        assert update.error_message is None

    def test_update_partial(self):
        """Test ProcessingRunUpdate accepts a subset of fields"""
        from schemas import ProcessingRunUpdate
        update = ProcessingRunUpdate(status="failed", error_message="boom")
        assert update.status == "failed"
        assert update.error_message == "boom"
        assert update.papers_processed is None

    def test_response_round_trip(self):
        """Test ProcessingRunResponse accepts a full row dict"""
        from schemas import ProcessingRunResponse
        from datetime import datetime
        resp = ProcessingRunResponse(
            id=1,
            run_type="arxiv_ingest",
            category=None,
            status="completed",
            papers_processed=5,
            error_message=None,
            started_at=datetime(2026, 7, 22, 6, 0, 0),
            completed_at=datetime(2026, 7, 22, 6, 5, 0),
        )
        assert resp.id == 1
        assert resp.completed_at is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])