# DAMスコア取得をこのPC上で実行し、変更があればコミット&プッシュする。
# タスクスケジューラから定期実行される想定(旧GitHub Actionsの代替)。
#
# ログイン(2026-10-26〜):
#   DAM★とものログインに reCAPTCHA v3 が入り、IDとパスワードだけの自動ログインは通らなくなった。
#   ログインは人が scripts\login_and_sync.cmd(Chrome の窓が開く)で行い、ここでは保存した
#   ログイン状態を使う。ログイン状態が無い・切れている場合は、何もコミットせずに終了コード 2 で終わる。
#   以前の環境変数 DAM_LOGIN_ID / DAM_PASSWORD は使わなくなった。
#
# 注意: git等のネイティブコマンドは正常時でもstderrに出力することがあるため、
# $ErrorActionPreference は Continue にして、成否は $LASTEXITCODE で判定する。

$ErrorActionPreference = "Continue"
$RepoRoot = "C:\Users\m12\Documents\DAM_SAITEN"
$LogDir = Join-Path $RepoRoot "data\_debug"
$LogFile = Join-Path $LogDir ("run_and_push_{0}.log" -f (Get-Date -Format "yyyyMMdd_HHmmss"))

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }

function Log($msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
    Write-Output $line
    Add-Content -Path $LogFile -Value $line
}

Set-Location $RepoRoot

Log "git pull中..."
git pull --ff-only 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "git pull に失敗しました(exit=$LASTEXITCODE)。処理を中止します。"
    exit 1
}

Log "scrape_dam.py 実行中..."
python scripts\scrape_dam.py 2>&1 | ForEach-Object { Log $_ }
$scrapeExit = $LASTEXITCODE
if ($scrapeExit -eq 2) {
    Log "ログインが必要です。scripts\login_and_sync.cmd を実行して、開いた Chrome の窓でログインしてください。コミットは行いません。"
    exit 2
}
if ($scrapeExit -ne 0) {
    Log "scrape_dam.py が失敗しました(exit=$scrapeExit)。コミットは行いません。"
    exit 1
}

Log "レパートリー更新中..."
python scripts\build_repertoire.py 2>&1 | ForEach-Object { Log $_ }
if ($LASTEXITCODE -ne 0) {
    Log "build_repertoire.py が失敗しました(exit=$LASTEXITCODE)。データ更新は続行します。"
}

git add data/ docs/data.json docs/repertoire.json
git diff --cached --quiet
$hasChanges = ($LASTEXITCODE -ne 0)
if (-not $hasChanges) {
    Log "変更なし、コミットをスキップします"
} else {
    $msg = "採点データ更新 $(Get-Date -Format 'yyyy-MM-dd HH:mm') JST (ローカル実行)"
    git commit -m $msg 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "git commit に失敗しました(exit=$LASTEXITCODE)。"
        exit 1
    }
    git push 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "git push に失敗しました(exit=$LASTEXITCODE)。"
        exit 1
    }
    Log "コミット&プッシュ完了: $msg"
}

exit 0
