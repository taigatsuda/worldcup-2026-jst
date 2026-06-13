# ITADAKI ’26 — FIFAワールドカップ2026 日本時間ガイド

全104試合を日本時間で。日本代表の日程・結果速報・グループ順位表・テレビ放送予定をひとつのページで。

**公開サイト:** https://taigatsuda.github.io/worldcup-2026-jst/

## 仕組み
- `src/build.py` が football-data.org のAPIから最新スコア・順位を取得し、会場・放送局データ（`src/schedule.json`）とマージして `site/index.html` を生成
- GitHub Actions（`.github/workflows/deploy.yml`）が **15分ごと** に再ビルドして GitHub Pages へ自動デプロイ
- APIトークンはリポジトリSecret `WC_API_TOKEN` から注入（コードには含めない）

データ提供: football-data.org ／ 国旗: flagcdn.com
