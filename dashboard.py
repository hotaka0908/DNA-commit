#!/usr/bin/env python3
"""
DNA-commit ダッシュボード

実行状況をWebブラウザで確認できるシンプルなダッシュボード
"""

import os
import re
import json
import subprocess
from datetime import datetime
from flask import Flask, render_template, jsonify

app = Flask(__name__)

# パス設定
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.join(BASE_DIR, "logs")
LOG_FILE = os.path.join(LOGS_DIR, "launchd_error.log")
RUN_HISTORY_FILE = os.path.join(LOGS_DIR, "run_history.json")


def is_running() -> dict:
    """DNA-commitが実行中か確認"""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "DNA-commit/main.py"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            pid = result.stdout.strip().split('\n')[0]
            return {"running": True, "pid": pid}
    except Exception:
        pass
    return {"running": False, "pid": None}


def get_current_phase() -> dict:
    """現在のフェーズをログから解析"""
    if not os.path.exists(LOG_FILE):
        return {"phase": "不明", "detail": "ログファイルがありません"}

    try:
        # ログファイルの最後の部分を読む
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            # 最後の100行を取得
            lines = f.readlines()[-100:]

        # フェーズパターン
        phase_patterns = [
            (r'\[1/6\] 情報収集', '1/6 情報収集'),
            (r'\[2/6\] 情報評価', '2/6 情報評価'),
            (r'\[3/6\] コード生成', '3/6 コード生成'),
            (r'\[4/6\] コードレビュー', '4/6 コードレビュー'),
            (r'\[5/6\] コミット', '5/6 コミット'),
            (r'\[6/6\] クリーンアップ', '6/6 クリーンアップ'),
            (r'サイクル完了サマリー', '完了'),
            (r'DNA-commit: スキップ', 'スキップ'),
        ]

        current_phase = "待機中"
        last_activity = ""
        repo_name = ""

        for line in reversed(lines):
            # 最新のフェーズを探す
            for pattern, phase_name in phase_patterns:
                if re.search(pattern, line):
                    current_phase = phase_name

                    # リポジトリ名を抽出
                    repo_match = re.search(r'\(([\w-]+)\)', line)
                    if repo_match:
                        repo_name = repo_match.group(1)
                    break

            # 最新のアクティビティを取得
            if not last_activity and '| INFO |' in line:
                # ログ行から詳細を抽出
                parts = line.split(' | ')
                if len(parts) >= 4:
                    last_activity = parts[-1].strip()[:80]

            if current_phase != "待機中" and last_activity:
                break

        return {
            "phase": current_phase,
            "repo": repo_name,
            "detail": last_activity
        }
    except Exception as e:
        return {"phase": "エラー", "detail": str(e)}


def get_recent_logs(lines: int = 30) -> list:
    """最新のログを取得"""
    if not os.path.exists(LOG_FILE):
        return []

    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
            return [line.strip() for line in all_lines[-lines:]]
    except Exception:
        return []


def get_run_history() -> list:
    """実行履歴を取得"""
    if not os.path.exists(RUN_HISTORY_FILE):
        return []

    try:
        with open(RUN_HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("runs", [])[-10:]  # 最新10件
    except Exception:
        return []


def get_statistics() -> dict:
    """統計情報を取得"""
    stats = {
        "today_runs": 0,
        "total_collected": 0,
        "total_evaluated": 0,
    }

    history = get_run_history()
    today = datetime.now().date().isoformat()

    for run in history:
        timestamp = run.get("timestamp", "")
        if timestamp.startswith(today):
            stats["today_runs"] += 1

        summary = run.get("summary", {})
        stats["total_collected"] += summary.get("collected", 0)
        stats["total_evaluated"] += summary.get("evaluated", 0)

    return stats


@app.route("/")
def index():
    """ダッシュボードページ"""
    return render_template("dashboard.html")


@app.route("/api/status")
def api_status():
    """ステータスAPI"""
    running = is_running()
    phase = get_current_phase()
    stats = get_statistics()

    return jsonify({
        "running": running["running"],
        "pid": running["pid"],
        "phase": phase["phase"],
        "repo": phase.get("repo", ""),
        "detail": phase["detail"],
        "stats": stats,
        "timestamp": datetime.now().isoformat()
    })


@app.route("/api/logs")
def api_logs():
    """ログAPI"""
    logs = get_recent_logs(100)
    return jsonify({"logs": logs})


@app.route("/api/history")
def api_history():
    """履歴API"""
    history = get_run_history()
    return jsonify({"history": history})


if __name__ == "__main__":
    # templatesディレクトリ作成
    os.makedirs(os.path.join(BASE_DIR, "templates"), exist_ok=True)

    print("DNA-commit ダッシュボード起動中...")
    print("http://localhost:5050 でアクセスできます")
    app.run(host="0.0.0.0", port=5050, debug=False)
