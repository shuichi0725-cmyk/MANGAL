# -*- coding: utf-8 -*-
"""一覧索引(manga-list-index.json)のauthors列デコーダ(2026-07-14 索引v2)。
★索引v2はauthorsを "name\tkana" のパック文字列で持つ(旧=dict形式)。
索引を生読みするPythonスクリプトは必ずこれを使う(TS側の listIndexDecode.ts と対)。
dict前提の .get("name") は文字列でAttributeError、isinstanceガードは黙って空になる(両方実害済)。"""


def au_name(a):
    """authors列の1要素→著者名。パック文字列/旧dictの両対応。"""
    if isinstance(a, str):
        return a.split("\t")[0]
    return (a or {}).get("name", "")


def au_kana(a):
    """authors列の1要素→著者カナ(無ければ空)。"""
    if isinstance(a, str):
        p = a.split("\t")
        return p[1] if len(p) > 1 else ""
    return (a or {}).get("kana", "") or ""


def au_names(v):
    """authors列全体→名前list(空要素除去)。"""
    return [n for n in (au_name(a) for a in (v or [])) if n]
