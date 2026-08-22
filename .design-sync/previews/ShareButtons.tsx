import React from "react";
import { ShareButtons } from "mangal";

/** The standard work-page share row. */
export function OnWorkPage() {
  return (
    <ShareButtons
      title="ハンター×ハンター"
      url="https://mangal.example/manga/hunter-x-hunter"
    />
  );
}

/** Where it sits on a work page: a labelled footer strip above related works. */
export function InPageFooter() {
  return (
    <div className="max-w-md tactile rounded-card p-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-bold">ベルサイユのばら</p>
        <span className="text-xs text-ink/45">全10巻・完結</span>
      </div>
      <div className="mt-2 border-t border-[var(--color-line)] pt-2">
        <ShareButtons
          title="ベルサイユのばら"
          url="https://mangal.example/manga/versailles-no-bara"
          titleSuffix={false}
        />
      </div>
    </div>
  );
}
