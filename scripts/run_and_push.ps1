# DAMスコア取得をこのPC上で実行し、変更があればコミット&プッシュする。
# タスクスケジューラから定期実行される想定(旧GitHub Actionsの代替)。
#
# 事前準備(初回のみ、このスクリプトの外で1回だけ実行):
#   setx DAM_LOGIN_ID "自分のログインID"
#   setx DAM_PASSWORD "自分のパスワード"
# (setxで設定した環境変数は、新しく開いたシェル/タスクスケジューラから見える)

$ErrorActionPreference = "Stop"
$RepoRoot = "C:\Users\m12\Documents\DAM_SAITEN"
$LogDir = Join-Path $RepoRoot "data\_debug"
$LogFile = Join-Path $LogDir ("run_and_push_{0}.log" -f (Get-Date -Format "yyyyMMdd_HHmmss"))

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }

function Log($msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
    Write-Output $line
    Add-Content -Path $LogFile -Value $line
}

try {
    if (-not $env:DAM_LOGIN_ID -or -not $env:DAM_PASSWORD) {
        Log "エラー: 環境変数 DAM_LOGIN_ID / DAM_PASSWORD が設定されていません。setxで設定してください。"
        exit 1
    }

    Set-Location $RepoRoot

    Log "git pull中..."
    git pull --ff-only 2>&1 | ForEach-Object { Log $_ }

    Log "scrape_dam.py 実行中..."
    python scripts\scrape_dam.py 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "scrape_dam.py が失敗しました(exit=$LASTEXITCODE)。コミットは行いません。"
        exit 1
    }

    git add data/ docs/data.json
    $diff = git diff --cached --quiet; $hasChanges = ($LASTEXITCODE -ne 0)
    if (-not $hasChanges) {
        Log "変更なし、コミットをスキップします"
    } else {
        $msg = "採点データ更新 $(Get-Date -Format 'yyyy-MM-dd HH:mm') JST (ローカル実行)"
        git commit -m $msg 2>&1 | ForEach-Object { Log $_ }
        git push 2>&1 | ForEach-Object { Log $_ }
        Log "コミット&プッシュ完了: $msg"
    }
} catch {
    Log "予期しないエラー: $_"
    exit 1
}
