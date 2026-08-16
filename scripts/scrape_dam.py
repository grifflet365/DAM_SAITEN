#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DAM★とも 採点履歴 自動取得スクリプト

環境変数:
  DAM_LOGIN_ID   ... DAM★とものログインID
  DAM_PASSWORD   ... DAM★とものパスワード

出力:
  data/ai.json        精密採点Ai の全蓄積レコード
  data/dxg.json        精密採点DX-G の全蓄積レコード
  data/hearts.json      精密採点Ai Heart の全蓄積レコード
  docs/data.json       上記3つをまとめた、ダッシュボード表示用のファイル
"""

import base64
import hashlib
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

import requests

BASE = "https://www.clubdam.com"
LOGIN_PAGE_URL = f"{BASE}/app/damtomo/auth/member/Login.do"
LOGIN_POST_URL = f"{BASE}/app/damtomo/auth/LoginXML.do"
MYPAGE_URL = f"{BASE}/app/damtomo/MyPage.do"

# Ai Heart のエンドポイント名は未確定なので候補を順に試す
AI_HEART_CANDIDATES = [
    "GetScoringHeartsListXML.do",
    "GetScoringAiHeartListXML.do",
    "GetScoringAiHeartsListXML.do",
    "GetScoringHeartListXML.do",
]

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")

JST = timezone(timedelta(hours=9))

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, "data")
DOCS_DIR = os.path.join(REPO_ROOT, "docs")


def log(msg):
    ts = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def login(session, login_id, password):
    """DAM★とも にログインしてセッションを確立する"""
    log("ログインページを取得中...")
    r = session.get(LOGIN_PAGE_URL, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    html = r.text

    # ログインフォームの hidden フィールドを拾う
    def find_hidden(name, default=None):
        m = re.search(
            rf'name=["\']{name}["\']\s+(?:id=["\'][^"\']*["\']\s+)?value=["\']([^"\']*)["\']',
            html,
        )
        if not m:
            m = re.search(
                rf'value=["\']([^"\']*)["\']\s+name=["\']{name}["\']',
                html,
            )
        return m.group(1) if m else default

    after_login = find_hidden("afterLogin")
    enc = find_hidden("enc", "sjis")

    if not after_login:
        log("警告: afterLogin フィールドが見つかりませんでした。ログインページの構造が変わっている可能性があります。")

    payload = {
        "procKbn": "1",
        "loginId": login_id,
        "password": password,
        "afterLogin": after_login or "",
        "enc": enc,
        "UTCserial": str(int(time.time() * 1000)),
    }

    log("ログインPOSTを送信中...")
    r = session.post(
        LOGIN_POST_URL,
        data=payload,
        headers={
            "User-Agent": UA,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": BASE,
            "Referer": LOGIN_PAGE_URL,
        },
        timeout=30,
    )
    r.raise_for_status()

    # ログイン後、マイページが正常に取れるか確認する
    r2 = session.get(MYPAGE_URL, headers={"User-Agent": UA}, timeout=30)
    r2.raise_for_status()
    if "cdmCardNo" not in r2.text:
        raise RuntimeError(
            "ログインに失敗した可能性があります(マイページに cdmCardNo が見つかりません)。"
            "IDまたはパスワードが正しいか、DAM側のログイン仕様が変わっていないか確認してください。"
        )

    log("ログイン成功。")
    return r2.text


def extract_ids(mypage_html):
    def find_input(input_id):
        m = re.search(rf'id=["\']{input_id}["\']\s+type=["\']hidden["\']', mypage_html)
        if not m:
            # 属性順が逆のパターンにも対応
            m = re.search(
                rf'value=["\']([^"\']*)["\']\s+id=["\']{input_id}["\']', mypage_html
            )
            return m.group(1) if m else None
        # value=... id=... の並び順を再取得
        m2 = re.search(
            rf'value=["\']([^"\']*)["\']\s+id=["\']{input_id}["\']', mypage_html
        )
        return m2.group(1) if m2 else None

    cdm_card_no = find_input("cdmCardNo")
    cdm_token = find_input("cdmToken")

    if not cdm_card_no:
        raise RuntimeError("cdmCardNo が抽出できませんでした。MyPage.do のHTML構造を確認してください。")

    return cdm_card_no, cdm_token


def strip_ns(tag):
    """'{http://...}tagName' -> 'tagName'"""
    return tag.split("}", 1)[1] if "}" in tag else tag


def xml_to_dict(elem):
    """XML要素を再帰的にdictへ変換する(同名タグが複数あればlistにまとめる)"""
    d = {}
    for child in elem:
        tag = strip_ns(child.tag)
        val = xml_to_dict(child) if len(child) else (child.text or "").strip()
        if tag in d:
            if not isinstance(d[tag], list):
                d[tag] = [d[tag]]
            d[tag].append(val)
        else:
            d[tag] = val
    if elem.attrib:
        d["_attrib"] = elem.attrib
    return d


def fetch_xml_list(session, url, params, debug_dump_path=None):
    """XML APIを叩いてレコードのリスト(list of dict)を返す

    DAM側のレスポンスは以下の形式で固定されている(2026/08 確認済み):
      <document>
        <list count="N">
          <data>
            <scoring contentsName="曲名" artistName="アーティスト" ...>90619</scoring>
          </data>
          ...
        </list>
      </document>
    レコードごとに中の要素名(scoring / scoringDxg / scoringHearts等)は
    モードによって異なるが、構造(dataの直下に1要素、属性に情報、
    テキストが1000倍した点数)は共通と想定して処理する。
    """
    r = session.get(
        url,
        params=params,
        headers={"User-Agent": UA, "Referer": MYPAGE_URL},
        timeout=30,
    )
    r.raise_for_status()
    if r.status_code != 200 or not r.text.strip().startswith("<"):
        raise RuntimeError(f"XMLではないレスポンスが返りました: {r.text[:200]}")

    if debug_dump_path:
        os.makedirs(os.path.dirname(debug_dump_path), exist_ok=True)
        with open(debug_dump_path, "w", encoding="utf-8") as f:
            f.write(r.text)

    root = ET.fromstring(r.text)

    # status を確認(エラー時はここに理由が入っていることが多い)
    status_elem = root.find(".//{*}status")
    status_code_elem = root.find(".//{*}statusCode")
    if status_elem is not None and status_elem.text and status_elem.text.strip() != "OK":
        msg_elem = root.find(".//{*}message")
        raise RuntimeError(
            f"APIがエラーを返しました: status={status_elem.text} "
            f"code={status_code_elem.text if status_code_elem is not None else '?'} "
            f"message={msg_elem.text if msg_elem is not None else ''}"
        )

    list_elem = root.find(".//{*}list")
    if list_elem is None:
        return []

    records = []
    for data_elem in list_elem.findall("{*}data"):
        # data の直下にある「本体」要素(scoring / scoringDxg / scoringHearts等)を取る
        children = list(data_elem)
        if not children:
            continue
        body = children[0]
        rec = dict(body.attrib)  # 属性(曲名・アーティスト名・日時など)を全部フィールド化
        rec["_tag"] = strip_ns(body.tag)
        raw_text = (body.text or "").strip()
        rec["_scoreRawText"] = raw_text
        if raw_text.replace("-", "").isdigit():
            # DAMの点数表現(例: "90619" -> 90.619点) を変換
            rec["score"] = round(int(raw_text) / 1000, 3)
        records.append(rec)

    return records


def make_record_id(mode, rec):
    """レコードの一意IDを作る(APIが独自IDを返さない場合のフォールバック含む)"""
    for key in ("scoringAiId", "scoringId", "id", "no", "serial"):
        if key in rec and rec[key]:
            return f"{mode}:{rec[key]}"
    # フォールバック: 曲名+日時+点数のハッシュ
    basis = json.dumps(rec, ensure_ascii=False, sort_keys=True)
    h = hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]
    return f"{mode}:{h}"


def load_existing(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def merge_new_records(mode, existing, fetched):
    existing_ids = {r["_id"] for r in existing}
    added = 0
    for rec in fetched:
        rid = make_record_id(mode, rec)
        if rid not in existing_ids:
            rec_with_meta = dict(rec)
            rec_with_meta["_id"] = rid
            rec_with_meta["_fetchedAt"] = datetime.now(JST).isoformat()
            existing.append(rec_with_meta)
            existing_ids.add(rid)
            added += 1
    return existing, added


def main():
    login_id = os.environ.get("DAM_LOGIN_ID")
    password = os.environ.get("DAM_PASSWORD")
    if not login_id or not password:
        log("エラー: 環境変数 DAM_LOGIN_ID / DAM_PASSWORD が設定されていません。")
        sys.exit(1)

    session = requests.Session()

    try:
        mypage_html = login(session, login_id, password)
    except Exception as e:
        log(f"ログイン処理でエラー: {e}")
        sys.exit(1)

    cdm_card_no, cdm_token = extract_ids(mypage_html)
    log(f"cdmCardNo 取得済み (先頭6文字のみ表示: {cdm_card_no[:6]}...)")

    results = {}

    # --- 精密採点Ai ---
    try:
        log("精密採点Ai のデータを取得中...")
        ai_records = fetch_xml_list(
            session,
            f"{BASE}/app/damtomo/scoring/GetScoringAiListXML.do",
            {"cdmCardNo": cdm_card_no},
            debug_dump_path=os.path.join(DATA_DIR, "_debug", "ai_raw.xml"),
        )
        log(f"精密採点Ai: {len(ai_records)}件 取得")
        results["ai"] = ai_records
    except Exception as e:
        log(f"精密採点Ai の取得に失敗: {e}")
        results["ai"] = []

    # --- 精密採点DX-G ---
    try:
        log("精密採点DX-G のデータを取得中...")
        dxg_records = fetch_xml_list(
            session,
            f"{BASE}/app/damtomo/scoring/GetScoringDxgListXML.do",
            {"cdmCardNo": cdm_card_no, "cdmToken": cdm_token},
            debug_dump_path=os.path.join(DATA_DIR, "_debug", "dxg_raw.xml"),
        )
        log(f"精密採点DX-G: {len(dxg_records)}件 取得")
        results["dxg"] = dxg_records
    except Exception as e:
        log(f"精密採点DX-G の取得に失敗: {e}")
        results["dxg"] = []

    # --- 精密採点Ai Heart (エンドポイント名を順番に試す) ---
    hearts_records = []
    hearts_ok = False
    for candidate in AI_HEART_CANDIDATES:
        try:
            log(f"精密採点Ai Heart を試行中: {candidate}")
            hearts_records = fetch_xml_list(
                session,
                f"{BASE}/app/damtomo/scoring/{candidate}",
                {"cdmCardNo": cdm_card_no},
                debug_dump_path=os.path.join(DATA_DIR, "_debug", "hearts_raw.xml"),
            )
            if hearts_records:
                log(f"精密採点Ai Heart: {candidate} で {len(hearts_records)}件 取得成功")
                hearts_ok = True
                break
        except Exception as e:
            log(f"  -> 失敗: {e}")
            continue
    if not hearts_ok:
        log("精密採点Ai Heart のエンドポイントが特定できませんでした。手動確認が必要です。")
    results["hearts"] = hearts_records

    # --- 差分マージして蓄積 ---
    summary = {}
    combined_for_dashboard = {}
    for mode, fetched in results.items():
        path = os.path.join(DATA_DIR, f"{mode}.json")
        existing = load_existing(path)
        merged, added = merge_new_records(mode, existing, fetched)
        save_json(path, merged)
        summary[mode] = {"total": len(merged), "added": added}
        combined_for_dashboard[mode] = merged
        log(f"{mode}: 累計 {len(merged)}件 (今回 +{added}件)")

    # ダッシュボード用にまとめて出力
    save_json(
        os.path.join(DOCS_DIR, "data.json"),
        {
            "updatedAt": datetime.now(JST).isoformat(),
            "modes": combined_for_dashboard,
        },
    )

    log("完了: " + json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
