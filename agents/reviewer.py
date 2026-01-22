"""
コードレビューエージェント

生成されたコードの品質をAIで自動レビュー
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional

from anthropic import Anthropic

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

logger = logging.getLogger(__name__)


REVIEW_PROMPT = """あなたはセキュリティとコード品質のエキスパートレビュアーです。

以下の自動生成されたコードをレビューし、raspi-voiceプロジェクトに安全にマージできるか判定してください。

## 生成されたコード変更

### コミットメッセージ
{commit_message}

### 変更ファイル
{changes}

### リスクレベル（自己申告）
{risk_level}

## レビュー基準

1. **セキュリティ**
   - APIキーのハードコーディングがないか
   - コマンドインジェクションの脆弱性
   - 入力バリデーション
   - 安全でないファイル操作

2. **コード品質**
   - Pythonのベストプラクティスに従っているか
   - エラーハンドリングが適切か
   - 既存のコードスタイルと一貫性があるか

3. **互換性**
   - 既存機能を破壊しないか
   - 依存関係の追加が適切か
   - Raspberry Pi環境で動作するか

4. **実用性**
   - 実際に改善になっているか
   - パフォーマンスへの影響
   - メンテナンス性

## 出力形式（JSON）
{{
    "approved": true|false,
    "security_score": 0.0-1.0,
    "quality_score": 0.0-1.0,
    "compatibility_score": 0.0-1.0,
    "overall_score": 0.0-1.0,
    "issues": [
        {{
            "severity": "critical|major|minor|info",
            "file": "ファイルパス",
            "line": "行番号（推定）",
            "description": "問題の説明",
            "suggestion": "修正提案"
        }}
    ],
    "improvements": ["良い点のリスト"],
    "required_changes": ["承認に必要な修正（approved=falseの場合）"],
    "recommendation": "approve|request_changes|reject",
    "summary": "レビューサマリー"
}}

JSONのみを出力してください。"""


class CodeReviewer:
    """コードレビューエージェント"""

    def __init__(self):
        self.client = Anthropic(api_key=Config.get_anthropic_api_key())
        self.review_log_path = os.path.join(Config.LOGS_DIR, "reviews.json")
        self._load_review_history()

    def _load_review_history(self):
        """レビュー履歴を読み込む"""
        if os.path.exists(self.review_log_path):
            with open(self.review_log_path, "r", encoding="utf-8") as f:
                self.review_history = json.load(f)
        else:
            self.review_history = {"reviews": [], "statistics": {}}

    def _save_review_history(self):
        """レビュー履歴を保存"""
        with open(self.review_log_path, "w", encoding="utf-8") as f:
            json.dump(self.review_history, f, ensure_ascii=False, indent=2)

    def _format_changes(self, generation: dict) -> str:
        """変更内容をフォーマット"""
        changes_text = ""
        for i, change in enumerate(generation.get("changes", []), 1):
            changes_text += f"\n### 変更 {i}: {change.get('file_path', 'unknown')}\n"
            changes_text += f"タイプ: {change.get('change_type', 'unknown')}\n"
            changes_text += f"説明: {change.get('description', '')}\n"
            changes_text += f"```python\n{change.get('code', '')[:3000]}\n```\n"
        return changes_text

    def review(self, generation: dict) -> dict:
        """生成されたコードをレビュー"""
        try:
            prompt = REVIEW_PROMPT.format(
                commit_message=generation.get("commit_message", ""),
                changes=self._format_changes(generation),
                risk_level=generation.get("risk_level", "unknown"),
            )

            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )

            result_text = response.content[0].text
            # JSON部分を抽出
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0]
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0]

            review = json.loads(result_text.strip())
            review["reviewed_at"] = datetime.now().isoformat()
            review["generation_source"] = generation.get("source_item_id")

            # 履歴に追加
            self.review_history["reviews"].append(review)
            self._update_statistics(review)
            self._save_review_history()

            logger.info(f"レビュー完了: {review.get('recommendation')} (score: {review.get('overall_score', 0):.2f})")
            return review

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            return self._create_fallback_review(str(e))
        except Exception as e:
            logger.error(f"Review error: {e}")
            return self._create_fallback_review(str(e))

    def _create_fallback_review(self, error: str) -> dict:
        """エラー時のフォールバックレビュー"""
        return {
            "approved": False,
            "security_score": 0,
            "quality_score": 0,
            "compatibility_score": 0,
            "overall_score": 0,
            "issues": [
                {
                    "severity": "critical",
                    "file": "unknown",
                    "line": "unknown",
                    "description": f"自動レビュー失敗: {error}",
                    "suggestion": "手動レビューが必要です",
                }
            ],
            "improvements": [],
            "required_changes": ["手動レビューを実施してください"],
            "recommendation": "reject",
            "summary": f"自動レビュー中にエラーが発生: {error}",
            "error": error,
            "reviewed_at": datetime.now().isoformat(),
        }

    def _update_statistics(self, review: dict):
        """統計情報を更新"""
        stats = self.review_history["statistics"]
        stats["total_reviews"] = stats.get("total_reviews", 0) + 1

        rec = review.get("recommendation", "unknown")
        stats[f"count_{rec}"] = stats.get(f"count_{rec}", 0) + 1

        # 平均スコア更新
        for key in ["security_score", "quality_score", "compatibility_score", "overall_score"]:
            current_avg = stats.get(f"avg_{key}", 0)
            count = stats["total_reviews"]
            new_value = review.get(key, 0)
            stats[f"avg_{key}"] = ((current_avg * (count - 1)) + new_value) / count

        # Issue種別カウント
        for issue in review.get("issues", []):
            severity = issue.get("severity", "unknown")
            stats[f"issue_{severity}"] = stats.get(f"issue_{severity}", 0) + 1

    def should_auto_approve(self, review: dict) -> bool:
        """自動承認可能かどうかを判定"""
        if not review.get("approved", False):
            return False

        if review.get("recommendation") != "approve":
            return False

        # セキュリティスコアが高いことを確認
        if review.get("security_score", 0) < 0.8:
            return False

        # 全体スコアが高いことを確認
        if review.get("overall_score", 0) < 0.7:
            return False

        # criticalな問題がないことを確認
        for issue in review.get("issues", []):
            if issue.get("severity") == "critical":
                return False

        return True

    def get_statistics(self) -> dict:
        """統計情報を取得"""
        return self.review_history.get("statistics", {})

    def analyze_common_issues(self) -> dict:
        """よくある問題を分析（自己改善のため）"""
        all_issues = []
        for review in self.review_history.get("reviews", []):
            all_issues.extend(review.get("issues", []))

        # 種別ごとにカウント
        issue_types = {}
        for issue in all_issues:
            desc = issue.get("description", "")[:50]
            issue_types[desc] = issue_types.get(desc, 0) + 1

        # 頻出問題を抽出
        sorted_issues = sorted(issue_types.items(), key=lambda x: x[1], reverse=True)

        return {
            "total_issues": len(all_issues),
            "unique_issues": len(issue_types),
            "top_issues": sorted_issues[:10],
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    reviewer = CodeReviewer()

    test_generation = {
        "commit_message": "テスト: オーディオバッファ改善",
        "changes": [
            {
                "file_path": "core/audio.py",
                "change_type": "modify",
                "description": "バッファサイズの最適化",
                "code": "def improved_buffer():\n    buffer_size = 1024\n    return buffer_size",
            }
        ],
        "risk_level": "low",
        "source_item_id": "test123",
    }

    result = reviewer.review(test_generation)
    print(json.dumps(result, ensure_ascii=False, indent=2))
