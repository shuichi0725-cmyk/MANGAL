"""NDL発見2024/2025の未収穫ISBN(data/seeds/ndl-rakuten-todo.txt)を楽天BooksBook APIで
ISBN直引き収穫。著者harvestが取りこぼした新刊(MADB未収録)のRakutenデータ(caption/書影/価格/発売日)を回収。
- 1.2s/req(QPS順守)・resumable(既収集skip)・outOfStockFlag=1(絶版/品切れも)。
- 出力: .cache/rakuten-isbn-delta.jsonl に追記(既存harvestと同形式 {isbn,item}) + 進捗log。
"""
import sys, re, json, time, urllib.parse, urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
TODO = ROOT / "data" / "seeds" / "ndl-rakuten-todo.txt"
OUT = ROOT / ".cache" / "rakuten-isbn-delta.jsonl"
RATE = 1.2
env = dict(l.strip().split("=", 1) for l in (ROOT / ".env.local").read_text(encoding="utf-8").splitlines()
           if "=" in l and not l.strip().startswith("#"))
ORIGIN = "https://mangal.shuichi0725.workers.dev"


def call_api(isbn):
    qs = urllib.parse.urlencode({
        "applicationId": env["RAKUTEN_APP_ID"], "accessKey": env["RAKUTEN_ACCESS_KEY"],
        "isbn": isbn, "affiliateId": env.get("RAKUTEN_AFFILIATE_ID", ""),
        "outOfStockFlag": "1", "format": "json", "formatVersion": "2"})
    req = urllib.request.Request("https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404?" + qs)
    req.add_header("Referer", ORIGIN + "/"); req.add_header("Origin", ORIGIN)
    req.add_header("User-Agent", "Mozilla/5.0 MANGAL")
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read())


def main():
    todo = [l.strip() for l in TODO.read_text(encoding="utf-8").splitlines() if l.strip()]
    # 既収集(deltaの末尾近く=このスクリプト追記分)を skip するため、 全deltaのISBNを読む
    have = set()
    if OUT.exists():
        rxe = re.compile(r'"isbn":\s*"?(\d{13})')
        for line in OUT.open(encoding="utf-8"):
            m = rxe.search(line)
            if m:
                have.add(m.group(1))
    pending = [i for i in todo if i not in have]
    print(f"todo {len(todo)} / 既収集 {len(todo)-len(pending)} / 収穫対象 {len(pending)}", flush=True)
    f = OUT.open("a", encoding="utf-8")
    got = miss = err = 0
    for n, isbn in enumerate(pending, 1):
        try:
            d = call_api(isbn)
            items = d.get("Items") or []
            if items:
                it = items[0]
                # formatVersion=2 では item が直接、 1 では {"Item":...}
                it = it.get("Item", it)
                f.write(json.dumps({"isbn": isbn, "item": it}, ensure_ascii=False) + "\n")
                f.flush(); got += 1
            else:
                miss += 1
            time.sleep(RATE)
        except Exception as e:
            err += 1
            time.sleep(RATE * 2)
        if n % 50 == 0:
            print(f"  {n}/{len(pending)} (got{got}/miss{miss}/err{err})", flush=True)
    f.close()
    print(f"完了: 収穫{got} / Rakuten無{miss} / err{err}", flush=True)


if __name__ == "__main__":
    main()
