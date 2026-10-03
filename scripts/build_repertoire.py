#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
docs/data.json(全採点記録)から、曲ごとにまとめた軽量なレパートリーデータ
docs/repertoire.json を作る。スマホ(docs/repertoire.html)で素早く開くための専用データ。

- 「(生音)」「[オリカラ]」「(ビデオクリップバージョン)」などの表記違いは同じ曲として集計
- 表示するキーは「直近5回で一番多かったキー」(同数なら直近のもの)
- ジャンルは重複あり。ARTIST_GENRES(歌手名ベース)と TITLE_GENRES(曲名で個別指定)で決める。
  直したい時はTITLE_GENRESに足す。どれにも当てはまらない新曲は「未分類」になる。
"""

import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO_ROOT, "docs", "data.json")
DST = os.path.join(REPO_ROOT, "docs", "repertoire.json")
JST = timezone(timedelta(hours=9))

ARTIST_GENRES = [
    ("サカナクション", ["J-POP", "ロック"]), ("Vaundy", ["J-POP"]), ("Mrs. GREEN APPLE", ["J-POP"]),
    ("茅原実里", ["アニメ"]), ("涼宮ハルヒ", ["アニメ"]), ("成田賢", ["アニメ"]), ("fripSide", ["アニメ"]),
    ("M!LK", ["J-POP"]), ("ピートマック", ["アニメ"]), ("藤原誠", ["アニメ"]), ("シェリル・ノーム", ["アニメ"]),
    ("May'n", ["アニメ"]), ("陰陽座", ["アニメ", "ロック"]), ("ALI PROJECT", ["アニメ"]), ("LiSA", ["アニメ", "J-POP"]),
    ("TRF", ["ダンス", "90年代"]), ("trf", ["ダンス", "90年代"]), ("中森明菜", ["昭和歌謡"]), ("TOKIO", ["J-POP"]),
    ("ゴダイゴ", ["昭和歌謡", "ロック"]), ("X JAPAN", ["ロック", "90年代"]), ("魔王魂", ["ゲーム・ボカロ"]),
    ("水樹奈々", ["アニメ"]), ("田村直美", ["アニメ", "90年代"]), ("ささきいさお", ["アニメ"]), ("中島みゆき", ["J-POP"]),
    ("DA PUMP", ["ダンス", "90年代"]), ("ポルノグラフィティ", ["J-POP", "ロック"]), ("浜崎あゆみ", ["J-POP"]),
    ("林原めぐみ", ["アニメ", "90年代"]), ("子門真人", ["アニメ"]), ("安室奈美恵", ["90年代", "ダンス"]),
    ("池田鴻", ["アニメ"]), ("GLAY", ["ロック", "90年代"]), ("PANDORA", ["特撮"]), ("井上大輔", ["アニメ"]),
    ("レベッカ", ["昭和歌謡", "ロック"]), ("郷ひろみ", ["昭和歌謡", "アイドル"]), ("久保田早紀", ["昭和歌謡"]),
    ("水木一郎", ["アニメ"]), ("BOOWY", ["ロック", "昭和歌謡"]), ("井上あずみ", ["アニメ"]), ("沖田浩之", ["アニメ"]),
    ("JAM Project", ["アニメ"]), ("小田和正", ["90年代", "J-POP"]), ("DREAMS COME TRUE", ["90年代", "J-POP"]),
    ("奥井雅美", ["アニメ"]), ("高橋洋子", ["アニメ"]), ("AKINO", ["アニメ"]), ("篠原涼子", ["90年代"]),
    ("岩崎宏美", ["昭和歌謡"]), ("鮎川麻弥", ["アニメ"]), ("angela", ["アニメ"]), ("井上陽水", ["昭和歌謡", "J-POP"]),
    ("チェッカーズ", ["昭和歌謡"]), ("Wink", ["昭和歌謡"]), ("TUBE", ["J-POP"]), ("Daito Music", ["ゲーム・ボカロ"]),
    ("AKB48", ["アイドル"]), ("鵜島仁文", ["アニメ"]), ("華原朋美", ["90年代"]), ("大黒摩季", ["90年代"]),
    ("高橋ひろ", ["アニメ", "90年代"]), ("TWO-MIX", ["アニメ", "90年代"]), ("沢田研二", ["昭和歌謡"]),
    ("月島きらり", ["アニメ"]), ("TM NETWORK", ["ロック", "アニメ"]), ("広瀬香美", ["90年代"]), ("岩崎良美", ["アニメ"]),
    ("中島美嘉", ["J-POP"]), ("T.M.Revolution", ["アニメ", "ロック", "90年代"]), ("串田アキラ", ["特撮"]),
    ("B.B.クィーンズ", ["アニメ", "90年代"]), ("LINDBERG", ["90年代"]), ("米津玄師", ["J-POP"]),
    ("ピンク・レディー", ["昭和歌謡", "アイドル"]), ("Every Little Thing", ["90年代", "J-POP"]), ("石川さゆり", ["演歌"]),
    ("相川七瀬", ["ロック", "90年代"]), ("クリスタルキング", ["アニメ", "昭和歌謡"]), ("爆風スランプ", ["ロック", "昭和歌謡"]),
    ("PRINCESS PRINCESS", ["昭和歌謡", "ロック"]), ("MAKE-UP", ["アニメ"]), ("MIQ", ["アニメ"]), ("DALI", ["アニメ", "90年代"]),
    ("サザンオールスターズ", ["J-POP", "ロック"]), ("十田敬三", ["アニメ"]), ("宇多田ヒカル", ["J-POP"]),
    ("石川ひとみ", ["昭和歌謡"]), ("高橋洋樹", ["アニメ"]), ("鈴木宏子", ["アニメ"]), ("濱田理恵", ["アニメ"]),
    ("SPEED", ["90年代", "ダンス"]), ("加藤登紀子", ["昭和歌謡"]), ("YOASOBI", ["J-POP", "アニメ"]),
    ("安全地帯", ["昭和歌謡", "ロック"]), ("荻野目洋子", ["昭和歌謡", "アイドル", "ダンス"]), ("新田洋", ["アニメ"]),
    ("細川たかし", ["演歌"]), ("尾藤イサオ", ["アニメ"]), ("八代亜紀", ["演歌"]), ("真宮寺さくら", ["ゲーム・ボカロ", "アニメ"]),
    ("キンモクセイ", ["J-POP"]), ("中原めいこ", ["昭和歌謡"]), ("梅沢富美男", ["演歌"]), ("globe", ["90年代", "ダンス"]),
    ("森口博子", ["アニメ"]), ("佳山明生", ["演歌"]), ("モーニング娘", ["アイドル", "90年代"]), ("乃木坂46", ["アイドル"]),
    ("WhiteFlame", ["ゲーム・ボカロ"]), ("山本まさゆき", ["アニメ"]), ("山口百恵", ["昭和歌謡", "アイドル"]),
    ("藤山一郎", ["昭和歌謡"]), ("day after tomorrow", ["90年代", "J-POP"]), ("hitomi", ["90年代", "ダンス"]),
    ("米米CLUB", ["昭和歌謡", "J-POP"]), ("Mr.Children", ["90年代", "J-POP"]), ("柊マグネタイト", ["ゲーム・ボカロ"]),
    ("吉幾三", ["演歌"]), ("小林幸子", ["演歌"]), ("BLACK BISCUITS", ["90年代"]), ("Team.ねこかん", ["ゲーム・ボカロ"]),
    ("千昌夫", ["演歌"]), ("小幡洋子", ["アニメ"]), ("ジュディ・オング", ["昭和歌謡"]), ("八神純子", ["昭和歌謡"]),
    ("村下孝蔵", ["昭和歌謡"]), ("アンサンブル・ボッカ", ["アニメ"]), ("H Jungle", ["90年代", "ダンス"]),
]

TITLE_GENRES = {
    "怪獣": ["アニメ", "J-POP", "ロック"], "ライラック": ["アニメ", "J-POP"], "ケセラセラ": ["J-POP"],
    "宙船(そらふね)": ["J-POP"], "誰がために": ["アニメ"], "キン肉マン Go Fight!": ["アニメ"],
    "秘密戦隊ゴレンジャー": ["特撮"], "Be The One": ["特撮"],
    "ウルトラセブンのうた": ["特撮"], "帰ってきたウルトラマン": ["特撮"], "ウルトラマンタロウ": ["特撮"], "ウルトラマンのうた": ["特撮"],
    "エアーマンが倒せない": ["ゲーム・ボカロ"],
    "光と影を抱きしめたまま": ["アニメ"], "燃えてヒーロー": ["アニメ"], "チェッ!チェッ!チェッ!": ["アニメ"],
    "FLYING IN THE SKY": ["アニメ"], "アンバランスなKissをして": ["アニメ"], "不思議色ハピネス": ["アニメ"],
    "笑顔に会いたい": ["アニメ"], "CARNIVAL・BABEL～カルナバル・バベル～": ["アニメ"], "恋をするたびに傷つきやすく…": ["アニメ"],
    "怪獣の花唄": ["J-POP"], "タイミング～Timing～": ["J-POP"], "Process": ["J-POP"],
}


def norm(title):
    s = re.sub(r"\[(生音|オリカラ|良音)\]", "", title)
    s = re.sub(r"\((生音|オリカラ|良音|ビデオクリップバージョン)\)", "", s)
    return re.sub(r"\s+", " ", s).strip()


def num(rec, key):
    try:
        return float(rec.get(key))
    except (TypeError, ValueError):
        return None


def perf_key(rec):
    try:
        return int(str(rec.get("lastPerformKey")).replace("+", ""))
    except ValueError:
        return None


def mode_key(items):
    keys = [perf_key(r) for _, r, _ in items if perf_key(r) is not None]
    counts = Counter(keys)
    if not counts:
        return None, 0
    top = max(counts.values())
    tied = [k for k, n in counts.items() if n == top]
    for _, r, _ in reversed(items):
        if perf_key(r) in tied:
            return perf_key(r), top
    return None, 0


def genres_for(title, artist):
    if title in TITLE_GENRES:
        return TITLE_GENRES[title]
    for name, genres in ARTIST_GENRES:
        if name in artist:
            return genres
    return ["未分類"]


def iso(stamp):
    return f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}"


def main():
    with open(SRC, "r", encoding="utf-8") as f:
        data = json.load(f)
    original_keys = data.get("originalKeys", {})

    groups = defaultdict(list)
    for mode, records in data["modes"].items():
        for rec in records:
            title = rec.get("contentsName") or rec.get("songName") or ""
            score = num(rec, "score")
            if not title or score is None or not rec.get("scoringDateTime"):
                continue
            groups[(norm(title), rec.get("artistName") or "")].append((mode, rec, score))

    songs = []
    for (title, artist), items in groups.items():
        items.sort(key=lambda x: x[1]["scoringDateTime"])
        scores = [s for _, _, s in items]
        best_item = max(items, key=lambda x: x[2])
        key_recent, key_recent_n = mode_key(items[-5:])
        key_all, _ = mode_key(items)
        last = items[-1][1]
        songs.append({
            "t": title, "a": artist, "n": len(items),
            "first": iso(items[0][1]["scoringDateTime"]), "last": iso(last["scoringDateTime"]),
            "best": round(max(scores), 2), "avg": round(sum(scores) / len(scores), 2),
            "r5": round(sum(scores[-5:]) / len(scores[-5:]), 2),
            "key": key_recent, "keyN": key_recent_n, "keyAll": key_all, "bestKey": perf_key(best_item[1]),
            "orig": original_keys.get(last.get("requestNo")),
            "modes": sorted({m for m, _, _ in items}),
            "g": genres_for(title, artist),
        })
    songs.sort(key=lambda x: (-x["n"], -x["best"]))

    out = {"updatedAt": datetime.now(JST).isoformat(), "songs": songs}
    with open(DST, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    unclassified = sum(1 for s in songs if s["g"] == ["未分類"])
    print(f"repertoire.json: {len(songs)}曲 (未分類 {unclassified}曲)")


if __name__ == "__main__":
    main()
