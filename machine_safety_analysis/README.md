# Machine Safety Analysis — submission-ready synthetic project

A deterministic, end-to-end synthetic machine-safety analytics workflow. It models plant master data, machine/zones/interlocks, alarm definitions/events, operator shifts, acknowledgements, incidents and corrective actions. It identifies repeated unsafe operating conditions, delayed acknowledgements, nuisance clusters and replay duplicates while retaining explicit event history and anomaly traceability.

## Requirements
- Windows 10/11 or another Python-capable OS.
- Python 3.9+ (standard library only; no `pip install` required).
- No credentials, external datasets, network access or manual source-code edits.

## Run (Windows)
1. Extract the ZIP.
2. Open the extracted `machine_safety_analysis` folder in VS Code.
3. Double-click `run_project.bat`, or run this in the terminal:

```powershell
python src/safety_project.py --scale full --seed 20261022 --output output
```

A successful run exits with code 0 and prints `Validation: PASS`. A failed validation exits non-zero and lists errors. For a quick test, use `--scale starter`.

## Run automated tests
```powershell
python -m unittest discover -s tests -v
```

## Run full-scale reproducibility acceptance test
This intentionally generates two independent 50,000-baseline-event datasets and compares SHA-256 hashes of the CSV/JSON source outputs:

```powershell
python tests/reproducibility_check.py
```

Expected final line: `PASS: two full-scale runs produced identical CSV/JSON SHA-256 checksums`.

## Dataset scope
Full scale: 4 plants, 60 machines, 200 alarm definitions and 50,000 baseline alarm events over 30 UTC days. One extra replay event is deliberately included, so the exported alarm-event table contains 50,001 rows. The generator also creates timestamped machine-state events, shifts, acknowledgements, incidents and corrective actions. A fixed seed (`20261022`) is used by default.

## Output files
- `*_*.csv` / entity CSV files: source entities and bridge/event tables.
- `data.json`: consolidated operational data; no ground-truth labels.
- `ground_truth.csv`, `ground_truth.json`: five expected exception labels, kept separate from analytical inputs.
- `machine_safety.db`: SQLite database with PK/FK constraints and indexes.
- `seed.sql`: portable SQL dump.
- `analytics_summary.json`: derived metrics, unsafe-condition counts, nuisance clusters, severity and acknowledgement metrics.
- `validation_summary.json`: business/data checks and detected exception decisions.
- `database_validation.json`: SQLite integrity, FK and table-count checks.
- `execution_report.json`: concise run metadata, row counts and validation status.
- `source_manifest.json`: synthetic provenance, seed, date window and table row counts.
- `checksums.sha256`: SHA-256 fingerprints for generated CSV/JSON source exports.

## Business rules and exception handling
- Unsafe operating combination: `machine_state=RUNNING` and `interlock_state!=ENGAGED`.
- Unsafe state records must be traceable to an incident; a separately labelled impossible-state test is detected as an exception.
- HIGH/CRITICAL alarm definitions require acknowledgement and have severity-specific acknowledgement SLAs.
- Acknowledgement timestamps must not precede the alarm event; response durations are stored in minutes.
- An incident must retain triggering alarm context, except for the explicitly labelled missing-context test.
- A corrective action cannot be CLOSED unless verification is VERIFIED and a verification timestamp exists.
- Replay events retain their source event reference and are excluded from unique-event counts.
- The five deliberately injected edge cases are: acknowledgement before alarm, impossible interlock state, missing incident trigger context, replay duplicate, and action closed without verification. The validator detects each and reports its expected decision. These examples are intentional test fixtures, not silent data corruption.

## Data model
See `DATA_DICTIONARY.md` for field-level types, requiredness, allowed values, units, uniqueness, validation rules, optional relationships, cardinality and effective dates. `PROJECT_STRUCTURE.txt` describes the folder layout.

## Reproducibility and provenance
All records are synthetic. No external data or personal information is used. The fixed-seed generator uses Python's standard `random.Random(seed)`. Reproducibility compares CSV/JSON hashes; SQLite binary files are not used for byte-for-byte comparisons because SQLite metadata can vary by runtime/version.

## Scope limitation
This is an analytics/demo project using synthetic data. It does not connect to PLC/SCADA/OT networks, issue machine-control commands, or certify real-world plant safety.
