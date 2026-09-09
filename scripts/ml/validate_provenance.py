# scripts/ml/validate_provenance.py
"""Provenance Validation Script for LUMINA ML Datasets.

Validates that training data has proper provenance, licensing, and consent.
Run before any training to ensure legal and ethical compliance.

USAGE:
    python -m scripts.ml.validate_provenance --dataset-dir ./data/v1.0.0
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of provenance validation."""
    check: str
    passed: bool
    message: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class ProvenanceReport:
    """Complete provenance validation report."""
    dataset_version: str
    total_checks: int = 0
    passed_checks: int = 0
    failed_checks: int = 0
    results: List[ValidationResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return self.failed_checks == 0

    def add_result(self, result: ValidationResult) -> None:
        self.results.append(result)
        self.total_checks += 1
        if result.passed:
            self.passed_checks += 1
        else:
            self.failed_checks += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_version": self.dataset_version,
            "total_checks": self.total_checks,
            "passed_checks": self.passed_checks,
            "failed_checks": self.failed_checks,
            "all_passed": self.all_passed,
            "results": [
                {"check": r.check, "passed": r.passed, "message": r.message}
                for r in self.results
            ],
        }


def validate_manifest_exists(dataset_dir: Path) -> ValidationResult:
    """Check that dataset manifest exists."""
    manifest_path = dataset_dir / "dataset_manifest.json"
    if manifest_path.exists():
        return ValidationResult(
            check="manifest_exists",
            passed=True,
            message=f"Manifest found at {manifest_path}",
        )
    return ValidationResult(
        check="manifest_exists",
        passed=False,
        message=f"Manifest not found at {manifest_path}",
    )


def validate_provenance_records(dataset_dir: Path) -> ValidationResult:
    """Check that provenance records exist and are complete."""
    manifest_path = dataset_dir / "dataset_manifest.json"
    if not manifest_path.exists():
        return ValidationResult(
            check="provenance_records",
            passed=False,
            message="Cannot validate provenance without manifest",
        )

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    provenance = manifest.get("provenance", [])
    if not provenance:
        return ValidationResult(
            check="provenance_records",
            passed=False,
            message="No provenance records found in manifest",
        )

    # Check each provenance record
    issues = []
    for i, record in enumerate(provenance):
        required_fields = ["source_name", "license", "commercial_use", "training_use"]
        for field_name in required_fields:
            if field_name not in record:
                issues.append(f"Record {i}: missing '{field_name}'")

    if issues:
        return ValidationResult(
            check="provenance_records",
            passed=False,
            message=f"Provenance issues: {'; '.join(issues)}",
            details={"issues": issues},
        )

    return ValidationResult(
        check="provenance_records",
        passed=True,
        message=f"Found {len(provenance)} complete provenance records",
    )


def validate_licensing(dataset_dir: Path) -> ValidationResult:
    """Check that licensing is verified and permits production use."""
    manifest_path = dataset_dir / "dataset_manifest.json"
    if not manifest_path.exists():
        return ValidationResult(
            check="licensing",
            passed=False,
            message="Cannot validate licensing without manifest",
        )

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    provenance = manifest.get("provenance", [])
    license_issues = []

    for record in provenance:
        source = record.get("source_name", "unknown")
        commercial = record.get("commercial_use", False)
        training = record.get("training_use", False)

        if not commercial:
            license_issues.append(f"{source}: commercial use NOT permitted")
        if not training:
            license_issues.append(f"{source}: training use NOT permitted")

    if license_issues:
        return ValidationResult(
            check="licensing",
            passed=False,
            message=f"License issues: {'; '.join(license_issues)}",
            details={"issues": license_issues},
        )

    return ValidationResult(
        check="licensing",
        passed=True,
        message="All sources permit commercial and training use",
    )


def validate_data_files(dataset_dir: Path) -> ValidationResult:
    """Check that data files exist and are non-empty."""
    required_files = ["train.jsonl", "val.jsonl", "test.jsonl"]
    missing = []
    empty = []

    for filename in required_files:
        filepath = dataset_dir / filename
        if not filepath.exists():
            missing.append(filename)
        elif filepath.stat().st_size == 0:
            empty.append(filename)

    if missing:
        return ValidationResult(
            check="data_files",
            passed=False,
            message=f"Missing data files: {', '.join(missing)}",
        )

    if empty:
        return ValidationResult(
            check="data_files",
            passed=False,
            message=f"Empty data files: {', '.join(empty)}",
        )

    return ValidationResult(
        check="data_files",
        passed=True,
        message="All required data files exist and are non-empty",
    )


def validate_checksums(dataset_dir: Path) -> ValidationResult:
    """Check that checksums exist and match."""
    checksums_path = dataset_dir / "checksums.json"
    if not checksums_path.exists():
        return ValidationResult(
            check="checksums",
            passed=False,
            message="No checksums file found",
        )

    with open(checksums_path, "r", encoding="utf-8") as f:
        checksums = json.load(f)

    # Verify each checksum
    import hashlib
    mismatches = []
    for filename, expected_checksum in checksums.items():
        filepath = dataset_dir / filename
        if not filepath.exists():
            mismatches.append(f"{filename}: file not found")
            continue

        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        actual = f"sha256:{sha256.hexdigest()}"

        if actual != expected_checksum:
            mismatches.append(f"{filename}: checksum mismatch")

    if mismatches:
        return ValidationResult(
            check="checksums",
            passed=False,
            message=f"Checksum issues: {'; '.join(mismatches)}",
        )

    return ValidationResult(
        check="checksums",
        passed=True,
        message=f"All {len(checksums)} checksums verified",
    )


def run_validation(dataset_dir: Path) -> ProvenanceReport:
    """Run all provenance validation checks."""
    report = ProvenanceReport(dataset_version="unknown")

    # Load version from manifest if available
    manifest_path = dataset_dir / "dataset_manifest.json"
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        report.dataset_version = manifest.get("version", "unknown")

    # Run checks
    checks = [
        validate_manifest_exists,
        validate_provenance_records,
        validate_licensing,
        validate_data_files,
        validate_checksums,
    ]

    for check_fn in checks:
        result = check_fn(dataset_dir)
        report.add_result(result)
        status = "✓" if result.passed else "✗"
        logger.info(f"  {status} {result.check}: {result.message}")

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate dataset provenance")
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        required=True,
        help="Path to dataset version directory",
    )
    args = parser.parse_args()

    if not args.dataset_dir.exists():
        logger.error(f"Dataset directory not found: {args.dataset_dir}")
        sys.exit(1)

    logger.info(f"Validating provenance for: {args.dataset_dir}")
    report = run_validation(args.dataset_dir)

    logger.info(f"\n{'='*60}")
    logger.info(f"Provenance Validation Report")
    logger.info(f"{'='*60}")
    logger.info(f"Dataset version: {report.dataset_version}")
    logger.info(f"Total checks: {report.total_checks}")
    logger.info(f"Passed: {report.passed_checks}")
    logger.info(f"Failed: {report.failed_checks}")
    logger.info(f"Result: {'ACCEPTED' if report.all_passed else 'REJECTED'}")

    if not report.all_passed:
        logger.error("\nFailed checks:")
        for result in report.results:
            if not result.passed:
                logger.error(f"  - {result.check}: {result.message}")
        sys.exit(1)

    logger.info("\nAll provenance checks passed.")


if __name__ == "__main__":
    main()
