import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-md px-4 py-24 text-center">
      <div className="tactile rounded-card px-6 py-12">
        <p className="text-5xl font-bold tracking-tight text-ink/80">404</p>
        <p className="mt-3 text-sm text-ink/60">
          お探しのページは見つかりませんでした。
        </p>
        <Link
          href="/"
          className="tactile-chip mt-6 inline-flex items-center rounded-card px-4 py-2 text-sm font-medium active:scale-[0.96] transition"
        >
          ← トップへ戻る
        </Link>
      </div>
    </div>
  );
}
