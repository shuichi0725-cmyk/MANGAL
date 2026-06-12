"use client";

import { useEffect, useRef, useState } from "react";

/** はみ出した時だけゆっくり横スクロールする1行タイトル。
 *  両端で一時停止(15%)→往復(alternate)。収まる題は一切動かない。 */
export default function MarqueeTitle({ text, className = "" }: { text: string; className?: string }) {
  const wrap = useRef<HTMLDivElement>(null);
  const span = useRef<HTMLSpanElement>(null);
  const [dist, setDist] = useState(0);
  useEffect(() => {
    const w = wrap.current;
    const s = span.current;
    if (w && s) setDist(Math.max(0, s.scrollWidth - w.clientWidth));
  }, [text]);
  const dur = Math.max(7, dist / 14); // ゆっくり(長いほど時間をかける)
  return (
    <div ref={wrap} className={`overflow-hidden whitespace-nowrap ${className}`}>
      <style>{`@keyframes mangal-mq { 0%, 18% { transform: translateX(0); } 82%, 100% { transform: translateX(var(--mq-dist)); } }`}</style>
      <span
        ref={span}
        className="inline-block will-change-transform"
        style={
          dist > 0
            ? ({ animation: `mangal-mq ${dur}s ease-in-out infinite alternate`, "--mq-dist": `-${dist}px` } as React.CSSProperties)
            : undefined
        }
      >
        {text}
      </span>
    </div>
  );
}
