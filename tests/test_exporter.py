"""
Tests for cdvl_crawler.exporter module
"""

import csv
import json

from cdvl_crawler.exporter import CDVLExporter


class TestCDVLExporter:
    """Tests for CDVLExporter"""

    def test_flatten_value(self, temp_dir):
        """Value flattening for CSV output"""
        exporter = CDVLExporter(str(temp_dir / "in.jsonl"), str(temp_dir / "out.csv"))

        assert exporter._flatten_value(None) == ""
        assert exporter._flatten_value(True) == "true"
        assert exporter._flatten_value(42) == "42"
        assert exporter._flatten_value("hello") == "hello"
        assert exporter._flatten_value(["a", "b"]) == "a; b"
        # Mixed list and dict become JSON
        assert json.loads(exporter._flatten_value([1, "two"])) == [1, "two"]
        assert json.loads(exporter._flatten_value({"k": "v"})) == {"k": "v"}

    def test_export_basic(self, sample_videos_jsonl, temp_dir):
        """Basic JSONL to CSV export"""
        output_path = temp_dir / "output.csv"
        exporter = CDVLExporter(str(sample_videos_jsonl), str(output_path))
        assert exporter.export() is True

        with open(output_path) as f:
            rows = list(csv.DictReader(f))
            assert len(rows) == 2
            assert rows[0]["id"] == "42"
            assert rows[0]["title"] == "Test Video"

    def test_export_selected_columns(self, sample_videos_jsonl, temp_dir):
        """Export only specified columns"""
        output_path = temp_dir / "output.csv"
        exporter = CDVLExporter(
            str(sample_videos_jsonl), str(output_path), columns=["id", "title"]
        )
        exporter.export()

        with open(output_path) as f:
            rows = list(csv.DictReader(f))
            assert set(rows[0].keys()) == {"id", "title"}

    def test_export_handles_errors(self, temp_dir):
        """Graceful handling of missing/empty files"""
        # Missing file
        exporter = CDVLExporter(
            str(temp_dir / "missing.jsonl"), str(temp_dir / "out.csv")
        )
        assert exporter.export() is False

        # Empty file
        empty = temp_dir / "empty.jsonl"
        empty.write_text("")
        exporter = CDVLExporter(str(empty), str(temp_dir / "out.csv"))
        assert exporter.export() is False
