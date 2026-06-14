// ITADAKI '26 — ライブスコア中継 (Cloudflare Worker)
//
// 目的: 公開サイト(GitHub Pages)のブラウザから football-data.org のスコアを
//       リアルタイム取得できるようにする中継サーバー。
//       APIトークンはこのWorkerの中だけに置き、ブラウザには一切出さない。
//
// 使い方:
//   1. Cloudflare(無料)でWorkerを作成し、このコードを貼り付け
//   2. 設定 → 変数 → 「WC_API_TOKEN」(シークレット)にAPIトークンを登録
//   3. デプロイ。発行されたURL(例 https://wc-proxy.xxxx.workers.dev)をサイトに設定
//
// 対応パス: /api/matches  /api/standings  /api/scorers
//   football-data.org の 10回/分 制限を守るため 30秒キャッシュ。

const API_BASE = "https://api.football-data.org/v4/competitions/WC";
const ENDPOINTS = {
  "/api/matches": "/matches",
  "/api/standings": "/standings",
  "/api/scorers": "/scorers",
};
const CACHE_SECONDS = 30;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const cors = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, OPTIONS",
      "Access-Control-Allow-Headers": "*",
    };
    if (request.method === "OPTIONS") return new Response(null, { headers: cors });

    const path = ENDPOINTS[url.pathname];
    if (!path) return new Response("Not found", { status: 404, headers: cors });

    // Cloudflareのエッジキャッシュで30秒キャッシュ（APIレート制限の保護）
    const cacheKey = new Request(API_BASE + path, request);
    const cache = caches.default;
    let res = await cache.match(cacheKey);
    if (!res) {
      const upstream = await fetch(API_BASE + path, {
        headers: { "X-Auth-Token": env.WC_API_TOKEN },
      });
      res = new Response(upstream.body, upstream);
      res.headers.set("Cache-Control", `max-age=${CACHE_SECONDS}`);
      for (const [k, v] of Object.entries(cors)) res.headers.set(k, v);
      res.headers.set("Content-Type", "application/json; charset=utf-8");
      // キャッシュにはCORS付きの応答を保存
      await cache.put(cacheKey, res.clone());
    }
    return res;
  },
};
