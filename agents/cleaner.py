"""
知識クリーナーエージェント

古い情報の削除、品質低下した情報の再評価、
使われない生成コードの削除を行う
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

logger = logging.getLogger(__name__)


class KnowledgeCleaner:
    """知識クリーナーエージェント"""

    def __init__(self):
        self.collected_data_path = os.path.join(Config.DATA_DIR, "collected_info.json")
        self.cleanup_log_path = os.path.join(Config.LOGS_DIR, "cleanups.json")
        self._load_cleanup_history()

    def _load_cleanup_history(self):
        """クリーンアップ履歴を読み込む"""
        if os.path.exists(self.cleanup_log_path):
            with open(self.cleanup_log_path, "r", encoding="utf-8") as f:
                self.cleanup_history = json.load(f)
        else:
            self.cleanup_history = {"cleanups": [], "statistics": {}}

    def _save_cleanup_history(self):
        """クリーンアップ履歴を保存"""
        with open(self.cleanup_log_path, "w", encoding="utf-8") as f:
            json.dump(self.cleanup_history, f, ensure_ascii=False, indent=2)

    def _load_collected_data(self) -> dict:
        """収集データを読み込む"""
        if os.path.exists(self.collected_data_path):
            with open(self.collected_data_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"items": [], "last_updated": None}

    def _save_collected_data(self, data: dict):
        """収集データを保存"""
        with open(self.collected_data_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def identify_stale_items(self) -> list[dict]:
        """古くなったアイテムを特定"""
        data = self._load_collected_data()
        stale_items = []
        cutoff_date = datetime.now() - timedelta(days=Config.STALENESS_DAYS)

        for item in data.get("items", []):
            collected_at = item.get("collected_at", "")
            if collected_at:
                try:
                    item_date = datetime.fromisoformat(collected_at)
                    if item_date < cutoff_date:
                        stale_items.append(item)
                except ValueError:
                    pass

        logger.info(f"古いアイテム検出: {len(stale_items)}件")
        return stale_items

    def identify_low_quality_items(self) -> list[dict]:
        """品質の低いアイテムを特定"""
        data = self._load_collected_data()
        low_quality_items = []

        for item in data.get("items", []):
            evaluation = item.get("evaluation", {})
            if evaluation:
                overall_score = evaluation.get("overall_score", 1.0)
                if overall_score < Config.MIN_USEFULNESS_SCORE:
                    low_quality_items.append(item)

        logger.info(f"低品質アイテム検出: {len(low_quality_items)}件")
        return low_quality_items

    def identify_rejected_items(self) -> list[dict]:
        """却下されたアイテムを特定"""
        data = self._load_collected_data()
        rejected_items = []

        for item in data.get("items", []):
            evaluation = item.get("evaluation", {})
            if evaluation.get("recommendation") == "reject":
                rejected_items.append(item)

        logger.info(f"却下アイテム検出: {len(rejected_items)}件")
        return rejected_items

    def cleanup_items(self, items_to_remove: list[dict], reason: str) -> dict:
        """アイテムを削除"""
        data = self._load_collected_data()
        ids_to_remove = {item.get("id") for item in items_to_remove}

        original_count = len(data.get("items", []))
        data["items"] = [
            item for item in data.get("items", [])
            if item.get("id") not in ids_to_remove
        ]
        removed_count = original_count - len(data["items"])

        self._save_collected_data(data)

        result = {
            "removed_count": removed_count,
            "reason": reason,
            "removed_ids": list(ids_to_remove),
            "timestamp": datetime.now().isoformat(),
        }

        # 履歴に追加
        self.cleanup_history["cleanups"].append(result)
        self._update_statistics(result)
        self._save_cleanup_history()

        logger.info(f"クリーンアップ完了: {removed_count}件削除 (理由: {reason})")
        return result

    def cleanup_old_generated_code(self, days_old: int = 30) -> dict:
        """古い生成コードを削除"""
        removed_dirs = []
        cutoff_date = datetime.now() - timedelta(days=days_old)

        if os.path.exists(Config.GENERATED_CODE_DIR):
            for dirname in os.listdir(Config.GENERATED_CODE_DIR):
                dirpath = os.path.join(Config.GENERATED_CODE_DIR, dirname)
                if os.path.isdir(dirpath):
                    try:
                        # ディレクトリ名から日付を解析 (YYYYMMDD_HHMMSS形式)
                        dir_date = datetime.strptime(dirname[:8], "%Y%m%d")
                        if dir_date < cutoff_date:
                            import shutil
                            shutil.rmtree(dirpath)
                            removed_dirs.append(dirname)
                    except (ValueError, IndexError):
                        pass

        result = {
            "removed_dirs": removed_dirs,
            "removed_count": len(removed_dirs),
            "reason": f"{days_old}日以上前の生成コード削除",
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(f"生成コードクリーンアップ: {len(removed_dirs)}ディレクトリ削除")
        return result

    def _update_statistics(self, result: dict):
        """統計情報を更新"""
        stats = self.cleanup_history["statistics"]
        stats["total_cleanups"] = stats.get("total_cleanups", 0) + 1
        stats["total_items_removed"] = stats.get("total_items_removed", 0) + result.get("removed_count", 0)

        reason = result.get("reason", "unknown")
        stats[f"count_{reason[:20]}"] = stats.get(f"count_{reason[:20]}", 0) + 1

    def run_full_cleanup(self) -> dict:
        """全てのクリーンアップを実行"""
        logger.info("=== フルクリーンアップ開始 ===")

        results = {
            "stale": None,
            "low_quality": None,
            "rejected": None,
            "generated_code": None,
            "timestamp": datetime.now().isoformat(),
        }

        # 古いアイテムの削除
        stale_items = self.identify_stale_items()
        if stale_items:
            results["stale"] = self.cleanup_items(stale_items, "古いアイテム")

        # 低品質アイテムの削除
        low_quality_items = self.identify_low_quality_items()
        if low_quality_items:
            results["low_quality"] = self.cleanup_items(low_quality_items, "低品質アイテム")

        # 却下アイテムの削除
        rejected_items = self.identify_rejected_items()
        if rejected_items:
            results["rejected"] = self.cleanup_items(rejected_items, "却下アイテム")

        # 古い生成コードの削除
        results["generated_code"] = self.cleanup_old_generated_code()

        total_removed = sum([
            r.get("removed_count", 0) if r else 0
            for r in [results["stale"], results["low_quality"], results["rejected"]]
        ])

        logger.info(f"=== クリーンアップ完了: 計{total_removed}件削除 ===")
        return results

    def get_statistics(self) -> dict:
        """統計情報を取得"""
        return self.cleanup_history.get("statistics", {})

    def get_data_summary(self) -> dict:
        """現在のデータサマリーを取得"""
        data = self._load_collected_data()
        items = data.get("items", [])

        summary = {
            "total_items": len(items),
            "by_status": {},
            "by_recommendation": {},
            "by_type": {},
        }

        for item in items:
            status = item.get("status", "unknown")
            summary["by_status"][status] = summary["by_status"].get(status, 0) + 1

            item_type = item.get("type", "unknown")
            summary["by_type"][item_type] = summary["by_type"].get(item_type, 0) + 1

            evaluation = item.get("evaluation", {})
            if evaluation:
                rec = evaluation.get("recommendation", "unknown")
                summary["by_recommendation"][rec] = summary["by_recommendation"].get(rec, 0) + 1

        return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cleaner = KnowledgeCleaner()

    print("データサマリー:")
    print(json.dumps(cleaner.get_data_summary(), ensure_ascii=False, indent=2))

    print("\nクリーンアップ統計:")
    print(json.dumps(cleaner.get_statistics(), ensure_ascii=False, indent=2))
