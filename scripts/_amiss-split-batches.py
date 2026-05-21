"""A-miss input.json を 100件/batch に分割。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / ".cache" / "amiss" / "input.json"
OUT_DIR = ROOT / ".cache" / "amiss"

data = json.loads(SRC.read_text(encoding="utf-8"))
batch_size = 100
n = (len(data) + batch_size - 1) // batch_size

for i in range(n):
    chunk = data[i * batch_size:(i + 1) * batch_size]
    path = OUT_DIR / f"input-{i+1:03d}.json"
    path.write_text(json.dumps(chunk, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"total: {len(data)}, batches: {n}")
