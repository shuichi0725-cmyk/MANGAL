"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { STORAGE_KEY, type ShelfItem, loadShelf, saveShelf } from "./myShelf";

/** localStorage そのものへの参照も投げることがある(Safari のプライベート・Cookie 無効)= 触る所は全部包む。 */
function safeStorage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

/**
 * マイ本棚の中身(端末保存)。★描画中には読まない = 水和後(useEffect)に読む。
 * サーバ描画と初回の水和は常に「空の棚・未読込」で一致させる(水和ずれ・空HTML型を踏まない)。
 * 別タブ(作品頁の「しまう」)で変わったら storage イベントで追従する。
 */
export function useMyShelf(): {
  items: ShelfItem[];
  /** 端末から読み終えたか(読む前に「空の棚」を出さないため) */
  ready: boolean;
  /** 直近の書き込みが端末に残ったか(false = この端末では保存できない) */
  persisted: boolean;
  update: (fn: (items: ShelfItem[]) => ShelfItem[]) => void;
} {
  const [items, setItems] = useState<ShelfItem[]>([]);
  const [ready, setReady] = useState(false);
  const [persisted, setPersisted] = useState(true);
  const ref = useRef<ShelfItem[]>([]);

  useEffect(() => {
    const read = () => {
      const s = loadShelf(safeStorage());
      ref.current = s;
      setItems(s);
    };
    read();
    setReady(true);
    const onStorage = (e: StorageEvent) => {
      if (e.key === null || e.key === STORAGE_KEY) read();
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const update = useCallback((fn: (items: ShelfItem[]) => ShelfItem[]) => {
    const next = fn(ref.current);
    if (next === ref.current) return;
    ref.current = next;
    setItems(next);
    setPersisted(saveShelf(safeStorage(), next));
  }, []);

  return { items, ready, persisted, update };
}
