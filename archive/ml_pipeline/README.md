# archive/ml_pipeline

These scripts are **historical / experimental** artifacts from earlier phases of LUMINA's ML work. They are **not** part of the active production or demo training pipeline.

The one active training entrypoint that writes the deployed artifacts
(`models/saved/risk_classifier.pkl`, `scaler.pkl`, `features.pkl`) is
`notebooks/train_simple_model.py`; its synthetic benchmark is produced by
`notebooks/audit_model.py`.

| Script | What it was for |
|---|---|
| `train_call_model.py` | Early Phase-1 prototype using a 6-feature call schema (superseded by the 11-feature model). |
| `train_model.py` | Attempt to train on the real Hinglish text dataset with 7 text-derived features (keyword score, word count, phone/UPI flags, urgency/language maps). |
| `train_realistic_model.py` | Experimental 11-feature variant with a train/val/test split, early stopping, and class weighting. |
| `process_all_datasets.py` | Experimental 2-feature model combining the Hinglish text dataset with Fraudzen call records. |
| `check_model_performance.py` | Superseded evaluation harness; replaced by `notebooks/audit_model.py`. |

To restore any of these from git history:

```bash
git show <commit>:notebooks/<script_name> > archive/ml_pipeline/<script_name>
```

None of these scripts are imported by `app/` or by the active pipeline.
