"""Unit tests for pure helpers: arXiv id parsing, SHA-256, category cleaning."""

from django.test import SimpleTestCase
from core.views import _compute_sha256, _parse_arxiv_ids


class ParseArxivIdsTests(SimpleTestCase):
    """Tests for _parse_arxiv_ids(), which extracts valid arXiv IDs
    from free-form user input."""

    # ── Basic bare IDs ────────────────────────────────────

    def test_bare_new_format(self):
        self.assertEqual(_parse_arxiv_ids("2301.12345"), ["2301.12345"])

    def test_bare_new_format_four_digits(self):
        self.assertEqual(_parse_arxiv_ids("2301.1234"), ["2301.1234"])

    def test_bare_new_format_five_digits(self):
        self.assertEqual(_parse_arxiv_ids("2301.12345"), ["2301.12345"])

    def test_bare_new_format_six_digits_invalid(self):
        self.assertEqual(_parse_arxiv_ids("2301.123456"), [])  # 6 digits — invalid

    def test_bare_legacy_format(self):
        self.assertEqual(_parse_arxiv_ids("hep-th/9901001"), ["hep-th/9901001"])

    def test_bare_legacy_with_subcategory(self):
        self.assertEqual(_parse_arxiv_ids("math.GT/0309136"), ["math.GT/0309136"])

    # ── Prefix stripping ──────────────────────────────────

    def test_abs_url(self):
        self.assertEqual(
            _parse_arxiv_ids("https://arxiv.org/abs/2601.19018"),
            ["2601.19018"],
        )

    def test_pdf_url(self):
        self.assertEqual(
            _parse_arxiv_ids("https://arxiv.org/pdf/2601.19018"),
            ["2601.19018"],
        )

    def test_arxiv_colon_prefix(self):
        self.assertEqual(_parse_arxiv_ids("arXiv:2601.19018"), ["2601.19018"])

    def test_arxiv_colon_case_insensitive(self):
        self.assertEqual(_parse_arxiv_ids("ARXIV:2301.12345"), ["2301.12345"])

    # ── Version suffix stripping ──────────────────────────

    def test_version_suffix(self):
        self.assertEqual(_parse_arxiv_ids("2601.19018v1"), ["2601.19018"])

    def test_version_suffix_high(self):
        self.assertEqual(_parse_arxiv_ids("2601.19018v12"), ["2601.19018"])

    def test_url_with_version(self):
        self.assertEqual(
            _parse_arxiv_ids("https://arxiv.org/abs/2601.19018v3"),
            ["2601.19018"],
        )

    # ── .pdf suffix stripping ─────────────────────────────

    def test_pdf_extension(self):
        """Versioned PDF URL — the bug that was fixed."""
        self.assertEqual(
            _parse_arxiv_ids("https://arxiv.org/pdf/2601.19018v2.pdf"),
            ["2601.19018"],
        )

    def test_pdf_extension_no_version(self):
        self.assertEqual(
            _parse_arxiv_ids("https://arxiv.org/pdf/2301.12345.pdf"),
            ["2301.12345"],
        )

    def test_pdf_extension_case_insensitive(self):
        self.assertEqual(_parse_arxiv_ids("2301.12345.PDF"), ["2301.12345"])

    # ── Query strings / fragments ─────────────────────────

    def test_query_string(self):
        self.assertEqual(
            _parse_arxiv_ids("https://arxiv.org/pdf/2601.19018v2.pdf?download"),
            ["2601.19018"],
        )

    def test_fragment(self):
        self.assertEqual(
            _parse_arxiv_ids("https://arxiv.org/abs/2601.19018#section1"),
            ["2601.19018"],
        )

    # ── Legacy IDs via URL ────────────────────────────────

    def test_legacy_id_abs_url(self):
        self.assertEqual(
            _parse_arxiv_ids("https://arxiv.org/abs/hep-th/9901001"),
            ["hep-th/9901001"],
        )

    def test_legacy_id_pdf_url_versioned(self):
        self.assertEqual(
            _parse_arxiv_ids("https://arxiv.org/pdf/hep-th/9901001v2.pdf?download"),
            ["hep-th/9901001"],
        )

    # ── Multiple IDs ──────────────────────────────────────

    def test_comma_separated(self):
        self.assertEqual(
            _parse_arxiv_ids("2301.12345, 2302.67890"),
            ["2301.12345", "2302.67890"],
        )

    def test_newline_separated(self):
        self.assertEqual(
            _parse_arxiv_ids("2301.12345\n2302.67890"),
            ["2301.12345", "2302.67890"],
        )

    def test_mixed_formats(self):
        result = _parse_arxiv_ids(
            "https://arxiv.org/abs/2601.19018, arXiv:2301.12345, 2302.67890"
        )
        self.assertEqual(result, ["2601.19018", "2301.12345", "2302.67890"])

    # ── Deduplication ─────────────────────────────────────

    def test_deduplication(self):
        self.assertEqual(
            _parse_arxiv_ids("2301.12345, 2301.12345"),
            ["2301.12345"],
        )

    def test_dedup_across_formats(self):
        """Same ID via URL and bare — should appear once."""
        self.assertEqual(
            _parse_arxiv_ids("https://arxiv.org/abs/2301.12345, 2301.12345"),
            ["2301.12345"],
        )

    # ── Invalid input ─────────────────────────────────────

    def test_empty_string(self):
        self.assertEqual(_parse_arxiv_ids(""), [])

    def test_whitespace_only(self):
        self.assertEqual(_parse_arxiv_ids("   \n  \n  "), [])

    def test_garbage(self):
        self.assertEqual(_parse_arxiv_ids("not-an-id, hello world"), [])

    def test_partial_match_ignored(self):
        """Things that look almost like IDs but aren't."""
        self.assertEqual(_parse_arxiv_ids("12345"), [])
        self.assertEqual(_parse_arxiv_ids("2301.1"), [])


class PaperStorageTests(SimpleTestCase):
    """Tests for SHA-256 hashing and hash-based file storage."""

    def test_sha256_bytes(self):
        result = _compute_sha256(b"hello world")
        self.assertEqual(len(result), 64)  # hex-encoded SHA-256
        # Known hash of "hello world"
        self.assertEqual(
            result,
            "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9",
        )

    def test_sha256_deterministic(self):
        data = b"%PDF-1.4 test content"
        self.assertEqual(_compute_sha256(data), _compute_sha256(data))

    def test_sha256_different_content(self):
        self.assertNotEqual(
            _compute_sha256(b"paper version 1"),
            _compute_sha256(b"paper version 2"),
        )

    def test_paper_storage_path_format(self):
        from core.views import _paper_storage_path
        path = _paper_storage_path("a3f7b2c9e8d1" + "0" * 52)
        self.assertIn("a3", str(path))  # first two chars as subdirectory
        self.assertTrue(str(path).endswith(".pdf"))


class CleanCategoriesTests(SimpleTestCase):
    """Tests for ProfileForm category validation."""

    def _make_form(self, categories_str):
        """Build a ProfileForm with the given categories string and
        all other fields set to valid defaults."""
        from core.forms import ProfileForm
        return ProfileForm(data={
            "name": "Test Profile",
            "frequency": "weekly",
            "threshold": "0.6",
            "top_x": "10",
            "categories": categories_str,
        })

    # ── Valid categories ──────────────────────────────────

    def test_single_valid(self):
        form = self._make_form("cs.AI")
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["categories"], ["cs.AI"])

    def test_multiple_valid(self):
        form = self._make_form("cs.AI,cs.LG,stat.ML")
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.cleaned_data["categories"],
            ["cs.AI", "cs.LG", "stat.ML"],
        )

    def test_whitespace_trimmed(self):
        form = self._make_form("  cs.AI , cs.LG  ")
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["categories"], ["cs.AI", "cs.LG"])

    def test_physics_hyphenated(self):
        """Categories like hep-th and gr-qc are valid."""
        form = self._make_form("hep-th,gr-qc,quant-ph")
        self.assertTrue(form.is_valid(), form.errors)

    def test_physics_dotted(self):
        form = self._make_form("physics.optics,cond-mat.stat-mech")
        self.assertTrue(form.is_valid(), form.errors)

    # ── Invalid categories ────────────────────────────────

    def test_empty_rejected(self):
        form = self._make_form("")
        self.assertFalse(form.is_valid())
        self.assertIn("categories", form.errors)

    def test_whitespace_only_rejected(self):
        form = self._make_form("  ,  ,  ")
        self.assertFalse(form.is_valid())
        self.assertIn("categories", form.errors)

    def test_unknown_code_rejected(self):
        form = self._make_form("cs.AI,not.real")
        self.assertFalse(form.is_valid())
        self.assertIn("categories", form.errors)
        self.assertIn("not.real", form.errors["categories"][0])

    def test_parent_group_rejected(self):
        """Parent codes like 'cs' are not leaf categories."""
        form = self._make_form("cs")
        self.assertFalse(form.is_valid())
        self.assertIn("categories", form.errors)

    def test_completely_bogus_code_rejected(self):
        form = self._make_form("fake.CATEGORY")
        self.assertFalse(form.is_valid())
        self.assertIn("categories", form.errors)

    def test_script_injection_rejected(self):
        """XSS attempt should fail validation."""
        form = self._make_form('cs.AI,</script><script>alert(1)</script>')
        self.assertFalse(form.is_valid())
        self.assertIn("categories", form.errors)
