"""
Export JSONL data to CSV format
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class CDVLExporter:
    """Export JSONL data to CSV format"""

    def __init__(
        self, input_file: str, output_file: str, columns: Optional[list[str]] = None
    ):
        """
        Initialize the exporter.

        Args:
            input_file: Path to input JSONL file
            output_file: Path to output CSV file
            columns: List of columns to export (None = all columns)
        """
        self.input_file = Path(input_file)
        self.output_file = Path(output_file)
        self.columns = columns

    def _flatten_value(self, value: object) -> str:
        """
        Flatten a value to a string suitable for CSV.

        Args:
            value: Any JSON value

        Returns:
            String representation of the value
        """
        if value is None:
            return ""
        elif isinstance(value, bool):
            return str(value).lower()
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, str):
            return value
        elif isinstance(value, list):
            # For lists, join with semicolons or serialize as JSON
            if all(isinstance(item, str) for item in value):
                return "; ".join(value)
            else:
                return json.dumps(value, ensure_ascii=False)
        elif isinstance(value, dict):
            return json.dumps(value, ensure_ascii=False)
        else:
            return str(value)

    def _get_all_columns(self, records: list[dict]) -> list[str]:
        """
        Get all unique columns from records in consistent order.

        Args:
            records: List of record dictionaries

        Returns:
            List of column names
        """
        # Use a dict to preserve insertion order while ensuring uniqueness
        columns_seen: dict[str, None] = {}

        # Preferred order for common columns
        preferred_order = [
            "id",
            "url",
            "title",
            "content_type",
            "filename",
            "file_size",
            "paragraphs",
            "links",
            "media",
            "tables_count",
            "extracted_at",
        ]

        for col in preferred_order:
            columns_seen[col] = None

        # Add any remaining columns from records
        for record in records:
            for key in record.keys():
                if key not in columns_seen:
                    columns_seen[key] = None

        # Filter to only columns that actually exist in records
        all_keys: set[str] = set()
        for record in records:
            all_keys.update(record.keys())

        return [col for col in columns_seen if col in all_keys]

    def export(self) -> bool:
        """
        Export JSONL to CSV.

        Returns:
            True if export was successful, False otherwise
        """
        # Check input file exists
        if not self.input_file.exists():
            logger.error(f"Input file not found: {self.input_file}")
            return False

        # Load all records
        records: list[dict] = []
        try:
            with open(self.input_file, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        records.append(record)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Skipping invalid JSON on line {line_num}: {e}")
        except OSError as e:
            logger.error(f"Failed to read input file: {e}")
            return False

        if not records:
            logger.error("No valid records found in input file")
            return False

        # Determine columns
        if self.columns:
            columns = self.columns
        else:
            columns = self._get_all_columns(records)

        # Create output directory if needed
        self.output_file.parent.mkdir(parents=True, exist_ok=True)

        # Write CSV
        try:
            with open(self.output_file, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)

                # Write header
                writer.writerow(columns)

                # Write data rows
                for record in records:
                    row = [self._flatten_value(record.get(col)) for col in columns]
                    writer.writerow(row)

            logger.info(f"Exported {len(records)} records to {self.output_file}")
            return True

        except OSError as e:
            logger.error(f"Failed to write output file: {e}")
            return False
