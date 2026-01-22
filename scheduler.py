#!/usr/bin/env python3
"""
DNA-commit スケジューラー

毎日指定時刻に自己進化サイクルを自動実行
"""

import schedule
import time
import logging
import json
from datetime import datetime
import os

from main import DNACommitOrchestrator
from config import Config

# ログ設定
os.makedirs(Config.LOGS_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(os.path.join(Config.LOGS_DIR, "scheduler.log")),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger("DNA-scheduler")


class DNAScheduler:
    """自己進化スケジューラー"""

    def __init__(self):
        self.orchestrator = DNACommitOrchestrator()
        self.run_history_path = os.path.join(Config.LOGS_DIR, "run_history.json")
        self._load_run_history()

    def _load_run_history(self):
        """実行履歴を読み込む"""
        if os.path.exists(self.run_history_path):
            with open(self.run_history_path, "r", encoding="utf-8") as f:
                self.run_history = json.load(f)
        else:
            self.run_history = {"runs": [], "statistics": {}}

    def _save_run_history(self):
        """実行履歴を保存"""
        with open(self.run_history_path, "w", encoding="utf-8") as f:
            json.dump(self.run_history, f, ensure_ascii=False, indent=2)

    def run_evolution_cycle(self):
        """進化サイクルを実行"""
        logger.info("=" * 60)
        logger.info("スケジュール実行: 自己進化サイクル開始")
        logger.info("=" * 60)

        start_time = datetime.now()

        try:
            result = self.orchestrator.run_full_cycle()
            success = len(result.get("errors", [])) == 0
        except Exception as e:
            logger.error(f"サイクル実行エラー: {e}")
            result = {"error": str(e)}
            success = False

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # 履歴に追加
        run_record = {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "success": success,
            "summary": self._extract_summary(result),
        }
        self.run_history["runs"].append(run_record)
        self._update_statistics(run_record)
        self._save_run_history()

        logger.info(f"サイクル完了: {duration:.1f}秒")

    def _extract_summary(self, result: dict) -> dict:
        """結果からサマリーを抽出"""
        return {
            "collected": result.get("collection", {}).get("new_items_count", 0),
            "evaluated": result.get("evaluation", {}).get("evaluated_count", 0),
            "generated": result.get("generation", {}).get("generated_count", 0),
            "reviewed": result.get("review", {}).get("reviewed_count", 0),
            "committed": result.get("commit", {}).get("committed_count", 0),
            "errors": len(result.get("errors", [])),
        }

    def _update_statistics(self, run_record: dict):
        """統計情報を更新"""
        stats = self.run_history["statistics"]
        stats["total_runs"] = stats.get("total_runs", 0) + 1

        if run_record.get("success"):
            stats["successful_runs"] = stats.get("successful_runs", 0) + 1
        else:
            stats["failed_runs"] = stats.get("failed_runs", 0) + 1

        # 平均実行時間
        current_avg = stats.get("avg_duration", 0)
        count = stats["total_runs"]
        new_duration = run_record.get("duration_seconds", 0)
        stats["avg_duration"] = ((current_avg * (count - 1)) + new_duration) / count

    def run_morning_cycle(self):
        """朝のサイクル（情報収集・評価重視）"""
        logger.info("朝のサイクル: 情報収集・評価")
        self.orchestrator.run_collection()
        self.orchestrator.run_evaluation()

    def run_evening_cycle(self):
        """夕方のサイクル（生成・レビュー・コミット重視）"""
        logger.info("夕方のサイクル: 生成・レビュー・コミット")
        self.orchestrator.run_generation()
        self.orchestrator.run_review()
        self.orchestrator.run_commit()

    def run_nightly_cleanup(self):
        """夜間クリーンアップ"""
        logger.info("夜間クリーンアップ")
        self.orchestrator.run_cleanup()

    def start(self, schedule_type: str = "full"):
        """スケジューラーを開始"""
        logger.info(f"DNA-commit スケジューラー開始 (モード: {schedule_type})")

        if schedule_type == "full":
            # フルサイクルを毎日3時に実行
            schedule.every().day.at("03:00").do(self.run_evolution_cycle)
            logger.info("スケジュール: 毎日03:00にフルサイクル実行")

        elif schedule_type == "split":
            # 分割サイクル
            schedule.every().day.at("06:00").do(self.run_morning_cycle)
            schedule.every().day.at("18:00").do(self.run_evening_cycle)
            schedule.every().day.at("02:00").do(self.run_nightly_cleanup)
            logger.info("スケジュール: 06:00収集・評価, 18:00生成・コミット, 02:00クリーンアップ")

        elif schedule_type == "hourly":
            # テスト用: 毎時実行
            schedule.every().hour.do(self.run_evolution_cycle)
            logger.info("スケジュール: 毎時フルサイクル実行")

        # メインループ
        logger.info("スケジューラー待機中...")
        while True:
            schedule.run_pending()
            time.sleep(60)  # 1分ごとにチェック

    def get_statistics(self) -> dict:
        """統計情報を取得"""
        return self.run_history.get("statistics", {})

    def get_recent_runs(self, count: int = 10) -> list:
        """最近の実行履歴を取得"""
        return self.run_history.get("runs", [])[-count:]


def main():
    import argparse

    parser = argparse.ArgumentParser(description="DNA-commit スケジューラー")
    parser.add_argument(
        "--mode",
        choices=["full", "split", "hourly", "once"],
        default="full",
        help="スケジュールモード (full: 毎日1回, split: 分割, hourly: 毎時, once: 即座に1回実行)"
    )
    parser.add_argument("--status", action="store_true", help="統計情報を表示")

    args = parser.parse_args()

    scheduler = DNAScheduler()

    if args.status:
        print("実行統計:")
        print(json.dumps(scheduler.get_statistics(), ensure_ascii=False, indent=2))
        print("\n最近の実行:")
        for run in scheduler.get_recent_runs(5):
            print(f"  {run['start_time']}: {'成功' if run['success'] else '失敗'}")
    elif args.mode == "once":
        scheduler.run_evolution_cycle()
    else:
        scheduler.start(args.mode)


if __name__ == "__main__":
    main()
