// 静的アセット配信用の最小ワーカー。 main + ASSETS binding にすることで、
// wrangler はアセットを参照方式(JWT)でアップロードし、 デプロイ metadata を小さく保つ
// (= assets専用[main無し]だと一覧をmetadataに同梱し 1MiB 超 code:100145 になる回避)。
export default {
  async fetch(request, env) {
    return env.ASSETS.fetch(request);
  },
};
