"""高橋留美子 (= creator C49857) の 全 record から 「超」 を 含む 作品を 抽出。"""
import json
import re
from pathlib import Path

SRC = Path(".cache/madb/metadata101.json")
CREATOR = "C49857"  # 高橋留美子

CREATOR_RE = re.compile(rf'"@id":\s*"https://mediaarts-db\.artmuseums\.go\.jp/id/{CREATOR}"')
LABEL_RE = re.compile(r'^      "rdfs:label":\s*"((?:[^"\\]|\\.)*)"')
ID_RE = re.compile(r'^      "@id":\s*"([^"]+)"')
NAME_START_RE = re.compile(r'^      "schema:name":\s*\[')
ALT_START_RE = re.compile(r'^      "schema:alternateName":\s*\[')
SINGLE_NAME_RE = re.compile(r'^      "schema:name":\s*"((?:[^"\\]|\\.)*)"')
SINGLE_ALT_RE = re.compile(r'^      "schema:alternateName":\s*"((?:[^"\\]|\\.)*)"')


def main() -> None:
    matches = []
    buf_lines: list[str] = []
    in_record = False

    with SRC.open(encoding="utf-8") as f:
        for line in f:
            if line.startswith("    {"):
                buf_lines = [line]
                in_record = True
                continue
            if not in_record:
                continue
            buf_lines.append(line)
            if line.rstrip().startswith("    }"):
                rec_text = "".join(buf_lines)
                if CREATOR not in rec_text:
                    in_record = False
                    continue
                label_m = re.search(r'^      "rdfs:label":\s*"((?:[^"\\]|\\.)*)"', rec_text, re.M)
                if not label_m:
                    in_record = False
                    continue
                label = json.loads(f'"{label_m.group(1)}"')
                if "超" not in label:
                    in_record = False
                    continue
                id_m = re.search(r'^      "@id":\s*"([^"]+)"', rec_text, re.M)
                mid = id_m.group(1).rsplit("/", 1)[-1] if id_m else "?"
                matches.append({"id": mid, "label": label, "text": rec_text})
                in_record = False

    print(f"= 高橋留美子 (= {CREATOR}) で 「超」 含む record: {len(matches)} 件 =")
    print()
    for m in matches:
        print(f"## {m['id']} : {m['label']}")
        for keyword in ["schema:name", "schema:alternateName", "ma:note"]:
            for ln in m["text"].splitlines():
                if f'"{keyword}"' in ln or ln.strip().startswith('"@value"') or ln.strip().startswith('"@language"'):
                    print(f"  {ln.rstrip()}")
        print()


if __name__ == "__main__":
    main()
