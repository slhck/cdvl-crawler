"""
Tests for cdvl_crawler.generator module
"""

from cdvl_crawler.generator import CDVLSiteGenerator


class TestCDVLSiteGenerator:
    """Tests for CDVLSiteGenerator"""

    def test_escape_json_prevents_xss(self):
        """Angle brackets are escaped to prevent XSS"""
        gen = CDVLSiteGenerator()
        result = gen.escape_json([{"html": "<script>alert('xss')</script>"}])
        assert "<" not in result
        assert "\\u003c" in result

    def test_load_videos(self, sample_videos_jsonl, temp_dir):
        """Loading videos from JSONL"""
        gen = CDVLSiteGenerator(input_file=str(sample_videos_jsonl))
        videos = gen.load_videos()
        assert len(videos) == 2
        assert videos[0]["id"] == 42

        # Missing file returns empty list
        gen = CDVLSiteGenerator(input_file=str(temp_dir / "missing.jsonl"))
        assert gen.load_videos() == []

    def test_generate_html(self, sample_video_data):
        """HTML generation includes required elements"""
        gen = CDVLSiteGenerator()
        html = gen.generate_html([sample_video_data])

        assert "<!DOCTYPE html>" in html
        assert "<title>CDVL // VIDEO ARCHIVE</title>" in html
        assert "const videos =" in html
        assert "1</span> videos loaded" in html  # Video count

    def test_generate_end_to_end(self, sample_videos_jsonl, temp_dir):
        """Full generation pipeline"""
        output_path = temp_dir / "output.html"
        gen = CDVLSiteGenerator(
            input_file=str(sample_videos_jsonl), output_file=str(output_path)
        )

        assert gen.generate() is True
        assert output_path.exists()
        assert "<!DOCTYPE html>" in output_path.read_text()

    def test_generate_fails_on_empty_input(self, temp_dir):
        """Returns False for empty input file"""
        empty = temp_dir / "empty.jsonl"
        empty.write_text("")
        gen = CDVLSiteGenerator(
            input_file=str(empty), output_file=str(temp_dir / "out.html")
        )
        assert gen.generate() is False
