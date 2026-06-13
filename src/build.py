#!/usr/bin/env python3
"""
ITADAKI '26 — 公開サイトのビルドスクリプト（GitHub Actions用）

football-data.org のAPIから最新の試合結果・順位を取得し、
会場・放送局データ（schedule.json）とマージして site/index.html を生成する。

環境変数:
  WC_API_TOKEN  football-data.org のAPIトークン（リポジトリSecretから注入）
出力:
  site/index.html, site/og.png, site/apple-touch-icon.png, site/.nojekyll
"""
import json
import os
import shutil
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
SRC = Path(__file__).resolve().parent
# 出力先はリポジトリ直下（branch方式の GitHub Pages がルートを配信する）
OUT = SRC.parent
API_BASE = "https://api.football-data.org/v4/competitions/WC"
TOKEN = os.environ.get("WC_API_TOKEN", "")


def fetch(path):
    req = urllib.request.Request(API_BASE + path, headers={"X-Auth-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.loads(res.read())


# ---- チーム情報(TLA → 日本語名・国旗コード) ----
TEAMS = {
 'JPN': ('日本', 'jp'), 'NED': ('オランダ', 'nl'), 'SWE': ('スウェーデン', 'se'), 'TUN': ('チュニジア', 'tn'),
 'MEX': ('メキシコ', 'mx'), 'KOR': ('韓国', 'kr'), 'CZE': ('チェコ', 'cz'), 'RSA': ('南アフリカ', 'za'),
 'BIH': ('ボスニア・ヘルツェゴビナ', 'ba'), 'CAN': ('カナダ', 'ca'), 'QAT': ('カタール', 'qa'), 'SUI': ('スイス', 'ch'),
 'BRA': ('ブラジル', 'br'), 'HAI': ('ハイチ', 'ht'), 'MAR': ('モロッコ', 'ma'), 'SCO': ('スコットランド', 'gb-sct'),
 'AUS': ('オーストラリア', 'au'), 'PAR': ('パラグアイ', 'py'), 'TUR': ('トルコ', 'tr'), 'USA': ('アメリカ', 'us'),
 'CUW': ('キュラソー', 'cw'), 'GER': ('ドイツ', 'de'), 'ECU': ('エクアドル', 'ec'), 'CIV': ('コートジボワール', 'ci'),
 'EGY': ('エジプト', 'eg'), 'BEL': ('ベルギー', 'be'), 'IRN': ('イラン', 'ir'), 'NZL': ('ニュージーランド', 'nz'),
 'CPV': ('カーボベルデ', 'cv'), 'KSA': ('サウジアラビア', 'sa'), 'ESP': ('スペイン', 'es'), 'URY': ('ウルグアイ', 'uy'),
 'FRA': ('フランス', 'fr'), 'IRQ': ('イラク', 'iq'), 'NOR': ('ノルウェー', 'no'), 'SEN': ('セネガル', 'sn'),
 'ALG': ('アルジェリア', 'dz'), 'ARG': ('アルゼンチン', 'ar'), 'JOR': ('ヨルダン', 'jo'), 'AUT': ('オーストリア', 'at'),
 'COD': ('コンゴ民主共和国', 'cd'), 'COL': ('コロンビア', 'co'), 'POR': ('ポルトガル', 'pt'), 'UZB': ('ウズベキスタン', 'uz'),
 'ENG': ('イングランド', 'gb-eng'), 'GHA': ('ガーナ', 'gh'), 'CRO': ('クロアチア', 'hr'), 'PAN': ('パナマ', 'pa'),
}

STAGE_JA = {
 'GROUP_STAGE': 'グループステージ', 'LAST_32': 'ラウンド32', 'LAST_16': 'ラウンド16',
 'QUARTER_FINALS': '準々決勝', 'SEMI_FINALS': '準決勝', 'THIRD_PLACE': '3位決定戦', 'FINAL': '決勝',
 'PLAY_OFFS': '決勝トーナメント', 'PLAYOFFS': '決勝トーナメント',
}

ALIAS = {'Turkiye': 'TUR', 'USA': 'USA', 'DRC': 'COD', 'Korea Republic': 'KOR',
         'Cabo Verde': 'CPV', 'Cape Verde': 'CPV', 'Ivory Coast': 'CIV',
         'Bosnia and Herzegovina': 'BIH', 'Côte d’Ivoire': 'CIV',
         'Bosnia': 'BIH', 'Curacao': 'CUW'}


def build():
    api_matches = fetch("/matches")["matches"]
    api_standings = fetch("/standings")["standings"]
    sched = json.load(open(SRC / "schedule.json", encoding="utf-8"))

    api_name_to_tla = {}
    for x in api_matches:
        for side in ('homeTeam', 'awayTeam'):
            t = x[side]
            if t.get('tla'):
                api_name_to_tla[t['name']] = t['tla']

    def raw_to_tla(raw):
        return api_name_to_tla.get(raw) or ALIAS.get(raw)

    sched_by_key, sched_by_pair, sched_by_date = {}, {}, {}
    for s in sched:
        ts = s['timestamp']
        home_tla = None
        if s['matchup']['type'] == 'teams':
            home_tla = raw_to_tla(s['matchup']['home']['raw'])
            away_tla = raw_to_tla(s['matchup']['away']['raw'])
            if home_tla and away_tla and s['stage'] == 'Group stage':
                sched_by_pair[frozenset((home_tla, away_tla))] = s
        sched_by_key[(ts, home_tla)] = s
        sched_by_date.setdefault(ts[:10], []).append(s)
    for v in sched_by_date.values():
        v.sort(key=lambda e: e['timestamp'])

    consumed = set()

    def find_sched(jst_ts, h, a, is_group):
        if is_group:
            s = sched_by_key.get((jst_ts, h))
            if s is None and h and a:
                s = sched_by_pair.get(frozenset((h, a)))
        else:
            s = None
            for cand in sched_by_date.get(jst_ts[:10], []):
                if cand['stage'] != 'Group stage' and id(cand) not in consumed:
                    s = cand
                    break
        if s is not None:
            consumed.add(id(s))
        return s

    matches = []
    for x in sorted(api_matches, key=lambda m: m['utcDate']):
        utc = datetime.fromisoformat(x['utcDate'].replace('Z', '+00:00'))
        jst_ts = utc.astimezone(JST).strftime('%Y-%m-%dT%H:%M:%S')
        h = x['homeTeam'].get('tla')
        a = x['awayTeam'].get('tla')
        s = find_sched(jst_ts, h, a, x.get('stage') == 'GROUP_STAGE')
        ft = x['score']['fullTime']
        stage = x.get('stage', '')
        matches.append({
            'id': x['id'], 'utc': x['utcDate'], 'st': x['status'],
            'stage': stage, 'stageJa': STAGE_JA.get(stage, stage),
            'group': (x.get('group') or '').replace('GROUP_', ''),
            'h': h, 'a': a, 'sh': ft['home'], 'sa': ft['away'],
            'venue': (s or {}).get('venue', ''),
            'tv': ((s or {}).get('broadcast') or {}).get('tv', []),
            'ol': ((s or {}).get('broadcast') or {}).get('online', []),
        })

    standings = {}
    for st in api_standings:
        if st['type'] != 'TOTAL':
            continue
        g = st['group'].replace('Group ', '')
        standings[g] = [{
            'tla': t['team']['tla'], 'p': t['playedGames'], 'w': t['won'], 'd': t['draw'],
            'l': t['lost'], 'gf': t['goalsFor'], 'ga': t['goalsAgainst'],
            'gd': t['goalDifference'], 'pts': t['points'],
        } for t in st['table']]

    teams_obj = {tla: {'ja': ja, 'flag': fl} for tla, (ja, fl) in TEAMS.items()}
    data = {
        'generatedAt': datetime.now(JST).strftime('%Y-%m-%d %H:%M'),
        'teams': teams_obj, 'matches': matches, 'standings': standings,
    }
    blob = json.dumps(data, ensure_ascii=False, separators=(',', ':'))

    tpl = open(SRC / "template.html", encoding="utf-8").read()
    assert '__WC_DATA__' in tpl, "テンプレートに __WC_DATA__ がありません"

    OUT.mkdir(exist_ok=True)
    (OUT / "index.html").write_text(tpl.replace('__WC_DATA__', blob), encoding="utf-8")
    for asset in ("og.png", "apple-touch-icon.png"):
        shutil.copy(SRC / asset, OUT / asset)
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    print(f"生成完了: {len(matches)}試合 / {len(standings)}グループ / {len(blob)} bytes")


if __name__ == "__main__":
    if not TOKEN:
        print("ERROR: 環境変数 WC_API_TOKEN が未設定です", file=sys.stderr)
        sys.exit(1)
    build()
