# カラオケ記録 (DAM★とも 自動連携)

DAM★とも の採点履歴(精密採点Ai / DX-G / Ai Heart)を GitHub Actions で定期的に取得し、
GitHub Pages 上のダッシュボードで閲覧するためのプロジェクトです。

## セットアップ手順

### 1. リポジトリを作成する
このフォルダの中身を、**非公開(Private)** の新しいGitHubリポジトリにpushしてください。
採点結果自体は非公開の必要はありませんが、ログイン情報を扱うのでリポジトリ自体は
Privateにしておくことを推奨します(GitHub Pagesは後述の通りPrivateリポジトリでも公開ページとして配信できます)。

```bash
git init
git add .
git commit -m "initial commit"
git branch -M main
git remote add origin https://github.com/<あなたのユーザー名>/<リポジトリ名>.git
git push -u origin main
```

### 2. Secretsを登録する
リポジトリの `Settings → Secrets and variables → Actions → New repository secret` から、以下の2つを登録してください。

| Name | Value |
|---|---|
| `DAM_LOGIN_ID` | DAM★とものログインID |
| `DAM_PASSWORD` | DAM★とものパスワード(**必ず新しいものに変更してから登録してください**) |

### 3. GitHub Pages を有効にする
`Settings → Pages` で、以下のように設定してください。

- Source: `Deploy from a branch`
- Branch: `main` / フォルダ: `/docs`

数分待つと `https://<あなたのユーザー名>.github.io/<リポジトリ名>/` でダッシュボードにアクセスできるようになります。

### 4. 動作確認(手動実行)
`Actions` タブ → `DAMスコア取得` ワークフロー → `Run workflow` で手動実行できます。
実行ログで各モードの取得件数が表示されるので、正常に取れているか確認してください。

初回実行後、`data/ai.json` `data/dxg.json` `data/hearts.json` および `docs/data.json` が
自動的にコミットされます。

## 既知の不確定要素(初回実行時に確認・調整が必要な点)

このプロジェクトはDAM★とも側の非公開API仕様を解析して作られていますが、
以下の点は実際に動かしてみないと確定できません。動かない場合はこの点を疑ってください。

1. **精密採点Ai Heart のエンドポイント名**
   `scripts/scrape_dam.py` 内の `AI_HEART_CANDIDATES` に候補を複数用意し、
   成功したものを自動採用する仕組みにしていますが、全滅した場合は
   ブラウザのNetworkタブで実際のエンドポイント名を確認し、リストに追加してください。

2. **各XML APIが返すフィールド名**
   `docs/index.html` 内の `FIELD_CANDIDATES` / `ITEM_LABELS` に、
   曲名・アーティスト名・点数・日付・各採点項目の「あり得るフィールド名」を
   候補として複数登録しています。実際のレスポンスを見て、表示が空欄になる項目があれば
   ここに正しいフィールド名を追加してください
   (`docs/data.json` を直接開けば、実際に取れているフィールド名を確認できます)。

3. **ログインフォームの `afterLogin` パラメータ**
   ログインページから毎回動的に取得する設計にしていますが、
   DAM側の仕様変更で正規表現が効かなくなった場合はログインに失敗します。
   Actionsのログにエラーメッセージが出るので、その際は該当箇所の正規表現を調整してください。

## ファイル構成

```
scripts/scrape_dam.py       ログイン→取得→蓄積を行うメインスクリプト
.github/workflows/scrape.yml  GitHub Actions ワークフロー(定期実行+手動実行)
data/*.json                 モードごとの全蓄積データ(スクリプトが自動生成)
docs/index.html             ダッシュボード本体
docs/manifest.json          PWA設定(ホーム画面アイコン化用)
docs/service-worker.js      オフラインキャッシュ
docs/icons/                 アプリアイコン
docs/data.json              ダッシュボード表示用の統合データ(スクリプトが自動生成)
```
