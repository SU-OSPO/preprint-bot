import pytest
from preprint_bot.pipeline import _format_duration


class TestPipelineDurationFormatting:
    """Test the duration formatting helper used in pipeline logging."""

    @pytest.mark.parametrize(
        "seconds,expected",
        [
            (0.0, "0.00s"),
            (5.254, "5.25s"),
            (59.99, "59.99s"),
            (60.0, "1m 0.0s"),
            (125.4, "2m 5.4s"),
            (3661.0, "61m 1.0s"),
        ],
    )
    def test_format_duration(self, seconds, expected):
        assert _format_duration(seconds) == expected