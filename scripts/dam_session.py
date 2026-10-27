#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DAM★とも へのログインを「人が」行い、そのログイン状態(Cookie)を保存する。

2026-10-26 から DAM★とも のログインに Google reCAPTCHA v3(画面には何も出ない判定)が入り、
scrape_dam.py がIDとパスワードだけで行っていた自動ログインが通らなくなった。
判定をすり抜ける細工はしない。ログインは人がふつうの Chrome の窓で行い、
その後の採点データの取得だけを scrape_dam.py が保存したログイン状態で自動で行う。

使い方:
  python scripts/dam_session.py login   Chrome の窓でログイン画面を開く。ログインが済んだら
                                          ログイン状態を保存して窓を閉じる(15分待つ)
  python scripts/dam_session.py check   保存したログイン状態がまだ有効かを確かめる
                                          (終了コード 0 = 有効、2 = ログインが必要)

保存場所(公開リポジトリの外): %LOCALAPPDATA%\\DAM_SAITEN\\
  chrome-profile\\   ログイン用の Chrome のプロファイル(普段の Chrome とは別)
  session.json      Cookie と User-Agent(scrape_dam.py が読む)
"""

import json
import os
import re
import sys
import time
from datetime import datetime

import requests

BASE = "https://www.clubdam.com"
LOGIN_PAGE_URL = f"{BASE}/app/damtomo/auth/member/Login.do"
MYPAGE_URL = f"{BASE}/app/damtomo/MyPage.do"
STATE_DIR = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "DAM_SAITEN")
PROFILE_DIR = os.path.join(STATE_DIR, "chrome-profile")
SESSION_FILE = os.environ.get("DAM_SESSION_FILE") or os.path.join(STATE_DIR, "session.json")
LOGIN_TIMEOUT_SEC = 15 * 60


def log(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def save_session(cookies, user_agent, path=SESSION_FILE):
    """cookies: [{name, value, domain, path, expires, secure}] を保存する(公開リポジトリの外)。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = {"saved_at": datetime.now().isoformat(timespec="seconds"), "user_agent": user_agent,
            "cookies": [{k: c.get(k) for k in ("name", "value", "domain", "path", "expires", "secure")} for c in cookies]}
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def load_session(path=SESSION_FILE):
    """保存したログイン状態から requests のセッションを作る。ファイルが無ければ None。"""
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        saved = json.load(f)
    s = requests.Session()
    if saved.get("user_agent"):
        s.headers["User-Agent"] = saved["user_agent"]
    for c in saved.get("cookies", []):
        s.cookies.set(c["name"], c["value"], domain=c.get("domain") or "", path=c.get("path") or "/")
    return s


def is_logged_in(session):
    r = session.get(MYPAGE_URL, timeout=30)
    r.raise_for_status()
    return "cdmCardNo" in r.text, r.text


def check():
    s = load_session()
    if s is None:
        log("保存したログイン状態がありません。")
        return 2
    ok, _ = is_logged_in(s)
    log("保存したログイン状態は有効です。" if ok else "保存したログイン状態は切れています。")
    return 0 if ok else 2


def login():
    from playwright.sync_api import sync_playwright

    os.makedirs(PROFILE_DIR, exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(PROFILE_DIR, channel="chrome", headless=False, no_viewport=True)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        attempts = []

        def on_response(resp):
            # ログインボタンで送られる LoginXML.do の結果を記録する(失敗の理由を知るため)
            if "LoginXML.do" in resp.url:
                try:
                    m = re.search(r"<statusCode>([^<]*)</statusCode>", resp.text())
                except Exception:
                    m = None
                attempts.append(m.group(1) if m else "?")
                log(f"ログインの送信結果: HTTP {resp.status}、statusCode {attempts[-1]}"
                    + ("(DAM側で認証が通りませんでした)" if attempts[-1] == "1010" else ""))

        page.on("response", on_response)
        # すでにログイン済みなら(プロファイルにログイン状態が残っていれば)そのまま使う
        page.goto(MYPAGE_URL, wait_until="domcontentloaded")
        ok = "cdmCardNo" in page.content()
        if not ok:
            page.goto(LOGIN_PAGE_URL, wait_until="domcontentloaded")
            log("Chrome の窓が開きました。いつも通りIDとパスワードでログインしてください。")
            log("(確認の画面が出た場合も、そのままご自身で操作してください。最大15分待ちます)")
        deadline = time.time() + LOGIN_TIMEOUT_SEC
        seen = len(attempts)
        while not ok and time.time() < deadline:
            try:
                if page.is_closed():
                    break
                page.wait_for_timeout(1500)        # time.sleep では画面の移動などの知らせが届かない
                on_login_page = "/auth/member/Login.do" in page.url
                if on_login_page and len(attempts) == seen:
                    continue                       # まだ入力中
                seen = len(attempts)
                page.wait_for_timeout(1500)        # ログイン後の画面の移動を待つ
                r = ctx.request.get(MYPAGE_URL, timeout=30000)
                if r.ok and b"cdmCardNo" in r.body():   # マイページは Shift-JIS のことがあるので、文字にせずバイト列で探す
                    ok = True
                    break
                if not on_login_page:
                    page.goto(LOGIN_PAGE_URL, wait_until="domcontentloaded")   # ログインできていなければ画面に戻す
            except Exception as e:                 # 画面の移動中など
                log(f"(待機中: {type(e).__name__})")
        if not ok:
            log("時間内にログインを確認できませんでした。取得は行いません。")
            try:
                ctx.close()
            except Exception:
                pass
            return 1
        ua = page.evaluate("navigator.userAgent")
        save_session(ctx.cookies(), ua)
        ctx.close()
    log("ログインを確認しました。ログイン状態を保存しました(公開リポジトリの外)。")
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "login"
    sys.exit({"login": login, "check": check}[cmd]())
