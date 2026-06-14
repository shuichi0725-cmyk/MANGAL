import os
root = "out"
n = 0
tot_path = 0
by_ext = {}
txt = 0
for dp, _, fs in os.walk(root):
    for f in fs:
        rel = "/" + os.path.relpath(os.path.join(dp, f), root).replace(os.sep, "/")
        n += 1
        tot_path += len(rel)
        ext = os.path.splitext(f)[1] or "(none)"
        by_ext[ext] = by_ext.get(ext, 0) + 1
        if ext == ".txt":
            txt += 1
print("total files:", n)
print(".txt files:", txt, "-> 削除後:", n - txt)
# マニフェスト1エントリ ~ path + 32byte hash + JSON構造(~40) と概算
est_full = tot_path + n * 72
print("マニフェスト概算(全):", round(est_full / 1024), "KiB")
# .txt除去後概算(pathは平均で引く)
avg = tot_path / n if n else 0
est_notxt = (tot_path - txt * avg) + (n - txt) * 72
print("マニフェスト概算(.txt除去後):", round(est_notxt / 1024), "KiB")
print("上位ext:", sorted(by_ext.items(), key=lambda x: -x[1])[:8])
