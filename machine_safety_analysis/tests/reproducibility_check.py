"""Full-scale deterministic reproducibility acceptance test (two 50k-event runs)."""
import hashlib, json, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "src" / "safety_project.py"
SEED = "20261022"

def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

with tempfile.TemporaryDirectory(prefix="safety_repro_") as td:
    root = Path(td)
    outputs = []
    for name in ("run_a", "run_b"):
        out = root / name
        subprocess.run([sys.executable, str(GENERATOR), "--scale", "full", "--seed", SEED, "--output", str(out)], check=True)
        outputs.append(out)
    files_a = {p.name: sha(p) for p in outputs[0].glob("*.csv")}
    files_b = {p.name: sha(p) for p in outputs[1].glob("*.csv")}
    for name in ("data.json", "ground_truth.json"):
        files_a[name] = sha(outputs[0] / name)
        files_b[name] = sha(outputs[1] / name)
    if files_a != files_b:
        raise SystemExit("FAIL: full-scale outputs differ for identical seed")
    report = json.loads((outputs[0] / "validation_summary.json").read_text(encoding="utf-8"))
    if report["status"] != "PASS":
        raise SystemExit("FAIL: validation report is not PASS")
    print("PASS: two full-scale runs produced identical CSV/JSON SHA-256 checksums")
    print("Compared files:", len(files_a))
    print("Seed:", SEED)
