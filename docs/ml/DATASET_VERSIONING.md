# LUMINA ML — Dataset Versioning Protocol

**Document Version:** 1.0  
**Created:** 2026-09-07  
**Purpose:** Ensure reproducibility and traceability of dataset versions.  
**Status:** FINAL

---

## Overview

Every dataset version is immutable and traceable. Once frozen, a version never changes. This ensures:
- Model checkpoints can be traced to exact dataset versions
- Experiments are reproducible
- Provenance is maintained
- Legal compliance is documented

---

## Version Format

Dataset versions follow semantic versioning:

```
MAJOR.MINOR.PATCH
```

- **MAJOR:** Taxonomy changes, fundamental restructuring
- **MINOR:** New data added, annotations updated
- **PATCH:** Bug fixes, documentation updates

**Example:** `1.2.3` = Major version 1, Minor version 2, Patch 3

---

## Version Components

Every dataset version includes:

| Component | Description | Example |
|-----------|-------------|---------|
| dataset_version | Overall version | `1.0.0` |
| source_version | Source data version | `ftc_ppone_20260907` |
| annotation_version | Annotation protocol version | `1.0` |
| taxonomy_version | Tactic taxonomy version | `1.0` |
| preprocessing_version | Preprocessing pipeline version | `1.0` |
| split_seed | Random seed for splits | `42` |
| split_ratios | Train/val/test ratios | `[0.8, 0.1, 0.1]` |

---

## Version Manifest

Every frozen dataset version produces a manifest:

```json
{
  "dataset_version": "1.0.0",
  "created_at": "2026-09-07T00:00:00Z",
  "source_version": "ftc_ppone_20260907",
  "annotation_version": "1.0",
  "taxonomy_version": "1.0",
  "preprocessing_version": "1.0",
  "split_seed": 42,
  "split_ratios": [0.8, 0.1, 0.1],
  "total_conversations": 1200,
  "total_segments": 18000,
  "train_segments": 14400,
  "val_segments": 1800,
  "test_segments": 1800,
  "label_distribution": {
    "AUTHORITY_CLAIM": 3200,
    "THREAT_PRESENTATION": 2800,
    "TIME_PRESSURE": 2100,
    "ISOLATION_TACTIC": 900,
    "CREDENTIAL_REQUEST": 1800,
    "FINANCIAL_REQUEST": 2500,
    "REMOTE_ACCESS_REQUEST": 600,
    "IDENTITY_REQUEST": 1200,
    "BENIGN_CONVERSATION": 4500,
    "USER_RESISTANCE": 800,
    "ADVICE_OR_WARNING": 400
  },
  "checksums": {
    "train": "sha256:abc123...",
    "val": "sha256:def456...",
    "test": "sha256:ghi789...",
    "manifest": "sha256:jkl012..."
  },
  "provenance": [
    {
      "source_name": "ftc_robocall_ppone",
      "license": "public_domain",
      "commercial_use": true,
      "training_use": true
    }
  ],
  "license_records": [
    {
      "source": "ftc_robocall_ppone",
      "license": "public_domain",
      "verified_date": "2026-09-07",
      "verified_by": "legal_team"
    }
  ],
  "changelog": [
    {
      "version": "1.0.0",
      "date": "2026-09-07",
      "changes": "Initial dataset release"
    }
  ]
}
```

---

## Checksums

### File Checksums

Every data file is checksummed:

```python
import hashlib

def compute_checksum(file_path: str) -> str:
    """Compute SHA-256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return f"sha256:{sha256.hexdigest()}"
```

### Manifest Checksum

The manifest itself is checksummed to detect tampering.

---

## Provenance Records

### Source Provenance

Every data source must have:

```json
{
  "source_name": "ftc_robocall_ppone",
  "source_url": "https://github.com/wspr-ncsu/robocall-audio-dataset",
  "license": "public_domain",
  "commercial_use": true,
  "training_use": true,
  "redistribution": true,
  "language": "en",
  "modality": "audio_transcript",
  "download_date": "2026-09-07",
  "verification_status": "VERIFIED",
  "notes": "FTC government data, public domain"
}
```

### License Records

Every license must be verified and recorded:

```json
{
  "source": "ftc_robocall_ppone",
  "license": "public_domain",
  "license_text": "This data is in the public domain...",
  "verified_date": "2026-09-07",
  "verified_by": "legal_team",
  "commercial_use": true,
  "training_use": true,
  "redistribution": true,
  "notes": "FTC Project Point of No Entry data"
}
```

---

## Changelog

Every version change is documented:

```json
{
  "changelog": [
    {
      "version": "1.0.0",
      "date": "2026-09-07",
      "changes": "Initial dataset release",
      "author": "ml_team"
    },
    {
      "version": "1.1.0",
      "date": "2026-10-15",
      "changes": "Added 500 new annotated segments from user consent program",
      "author": "ml_team",
      "impact": "Re-annotation of 50 ambiguous segments"
    }
  ]
}
```

---

## Model-Dataset Traceability

Every trained model checkpoint must reference:

```json
{
  "model_version": "1.0.0",
  "dataset_version": "1.0.0",
  "training_date": "2026-10-01",
  "training_config": {
    "model_name": "microsoft/deberta-v3-base",
    "learning_rate": 3e-5,
    "epochs": 3,
    "batch_size": 16
  },
  "evaluation_metrics": {
    "macro_f1": 0.82,
    "per_class_f1": {}
  }
}
```

This ensures every model can be traced back to:
1. The exact dataset version used
2. The exact training configuration
3. The exact evaluation results
4. The exact provenance of all training data

---

## Version Lifecycle

### 1. Development

- Dataset is being built
- Version: `0.x.x` (pre-release)
- Changes are expected

### 2. Frozen

- Dataset is complete and validated
- Version: `1.0.0` (first release)
- Changes require new version

### 3. Archived

- Dataset is superseded by newer version
- Version remains available for reproducibility
- No new models should be trained on it

---

## Directory Structure

```
data/
├── v1.0.0/
│   ├── manifest.json
│   ├── train.jsonl
│   ├── val.jsonl
│   ├── test.jsonl
│   ├── provenance.json
│   ├── licenses.json
│   └── checksums.json
├── v1.1.0/
│   ├── manifest.json
│   ├── train.jsonl
│   ├── val.jsonl
│   ├── test.jsonl
│   ├── provenance.json
│   ├── licenses.json
│   └── checksums.json
└── current -> v1.1.0/  (symlink to latest)
```
