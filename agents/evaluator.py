"""
情報評価エージェント

Claude APIを使用して収集した情報の品質・関連性を自動評価
失敗を許容し、自己改善のためのフィードバックループを持つ
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


EVALUATION_PROMPT = """あなたは技術情報の品質評価エージェントです。

以下の情報を評価し、どのプロジェクトの改善に役立つか判定してください。

## 評価対象情報
タイトル: {title}
URL: {url}
内容: {content}

## 対象プロジェクト

### 1. raspi-voice8（音声AIアシスタント）
- Raspberry Pi上で動作する音声AIアシスタント
- OpenAI Realtime APIを使用
- 機能: Gmail連携、カレンダー、Web検索、ビジョン(カメラ)、音声メッセージ、ビデオ通話
- 技術: Python, PyAudio, WebRTC, Firebase, GPIO

### 2. DNA-commit（自己進化システム）
- AIが自動でコードを改善するシステム
- 情報収集 → 評価 → コード生成 → レビュー → コミットのサイクル
- 技術: Python, Claude API, Tavily API, GitHub API, Git

## 評価基準
1. **品質スコア (0.0-1.0)**: 情報の信頼性、正確性、詳細さ
2. **関連性スコア (0.0-1.0)**: プロジェクトへの適用可能性
3. **新規性スコア (0.0-1.0)**: 既存の一般的な知識を超えた新しい情報か
4. **実用性スコア (0.0-1.0)**: 実際にコードに適用できるか

## 出力形式（JSON）
{{
    "quality_score": 0.0-1.0,
    "relevance_score": 0.0-1.0,
    "novelty_score": 0.0-1.0,
    "practicality_score": 0.0-1.0,
    "overall_score": 0.0-1.0,
    "summary": "この情報の要約（2-3文）",
    "target_repos": ["raspi-voice8", "DNA-commit"],  // 適用可能なリポジトリ（両方可）
    "applicable_areas": ["適用可能な領域のリスト"],
    "potential_improvements": ["この情報で可能な改善のリスト"],
    "risks": ["適用時のリスクや注意点"],
    "recommendation": "adopt|consider|reject",
    "reasoning": "判断理由"
}}

JSONのみを出力してください。"""


class InformationEvaluator:
    """情報評価エージェント"""

    def __init__(self):
        self.client = Anthropic(api_key=Config.get_anthropic_api_key())
        self.evaluation_log_path = os.path.join(Config.LOGS_DIR, "evaluations.json")
        self._load_evaluation_history()

    def _load_evaluation_history(self):
        """評価履歴を読み込む"""
        if os.path.exists(self.evaluation_log_path):
            with open(self.evaluation_log_path, "r", encoding="utf-8") as f:
                self.evaluation_history = json.load(f)
        else:
            self.evaluation_history = {"evaluations": [], "statistics": {}}

    def _save_evaluation_history(self):
        """評価履歴を保存"""
        with open(self.evaluation_log_path, "w", encoding="utf-8") as f:
            json.dump(self.evaluation_history, f, ensure_ascii=False, indent=2)

    def _update_statistics(self, evaluation: dict):
        """統計情報を更新（自己改善のため）"""
        stats = self.evaluation_history["statistics"]

        # 累計評価数
        stats["total_evaluations"] = stats.get("total_evaluations", 0) + 1

        # 推奨別カウント
        rec = evaluation.get("recommendation", "unknown")
        stats[f"count_{rec}"] = stats.get(f"count_{rec}", 0) + 1

        # 平均スコア更新
        for key in ["quality_score", "relevance_score", "novelty_score", "practicality_score"]:
            current_avg = stats.get(f"avg_{key}", 0)
            count = stats["total_evaluations"]
            new_value = evaluation.get(key, 0)
            stats[f"avg_{key}"] = ((current_avg * (count - 1)) + new_value) / count

    def evaluate(self, item: dict) -> dict:
        """情報を評価"""
        try:
            content = item.get("content", "") or item.get("description", "")
            if item.get("raw_content"):
                content = item["raw_content"][:3000]

            prompt = EVALUATION_PROMPT.format(
                title=item.get("title", ""),
                url=item.get("url", ""),
                content=content[:4000],
            )

            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )

            # JSONパース
            result_text = response.content[0].text
            # JSON部分を抽出
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0]
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0]

            evaluation = json.loads(result_text.strip())
            evaluation["evaluated_at"] = datetime.now().isoformat()
            evaluation["item_id"] = item.get("id")

            # 履歴に追加
            self.evaluation_history["evaluations"].append(evaluation)
            self._update_statistics(evaluation)
            self._save_evaluation_history()

            logger.info(f"評価完了: {item.get('title', '')[:50]} -> {evaluation.get('recommendation')}")
            return evaluation

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            return self._create_fallback_evaluation(item, str(e))
        except Exception as e:
            logger.error(f"Evaluation error: {e}")
            return self._create_fallback_evaluation(item, str(e))

    def _create_fallback_evaluation(self, item: dict, error: str) -> dict:
        """エラー時のフォールバック評価（失敗を許容）"""
        return {
            "quality_score": 0.5,
            "relevance_score": 0.5,
            "novelty_score": 0.5,
            "practicality_score": 0.5,
            "overall_score": 0.5,
            "summary": "評価中にエラーが発生しました。手動確認が必要です。",
            "applicable_areas": [],
            "potential_improvements": [],
            "risks": ["自動評価が失敗したため、手動確認推奨"],
            "recommendation": "consider",
            "reasoning": f"自動評価エラー: {error}",
            "error": error,
            "evaluated_at": datetime.now().isoformat(),
            "item_id": item.get("id"),
        }

    def batch_evaluate(self, items: list[dict]) -> list[dict]:
        """複数のアイテムを一括評価"""
        evaluations = []
        for item in items:
            evaluation = self.evaluate(item)
            evaluations.append(evaluation)
        return evaluations

    def get_adoptable_items(self, items: list[dict], evaluations: list[dict]) -> list[dict]:
        """採用可能なアイテムを抽出"""
        adoptable = []
        for item, eval_result in zip(items, evaluations):
            if eval_result.get("recommendation") == "adopt":
                if eval_result.get("overall_score", 0) >= Config.QUALITY_THRESHOLD:
                    item["evaluation"] = eval_result
                    adoptable.append(item)
        return adoptable

    def get_statistics(self) -> dict:
        """自己改善のための統計情報を取得"""
        return self.evaluation_history.get("statistics", {})

    def analyze_feedback(self) -> dict:
        """過去の評価から学習し、改善点を分析"""
        stats = self.get_statistics()
        analysis = {
            "total_evaluated": stats.get("total_evaluations", 0),
            "adoption_rate": 0,
            "average_scores": {},
            "recommendations": [],
        }

        if stats.get("total_evaluations", 0) > 0:
            adopt_count = stats.get("count_adopt", 0)
            analysis["adoption_rate"] = adopt_count / stats["total_evaluations"]

            for key in ["quality_score", "relevance_score", "novelty_score", "practicality_score"]:
                analysis["average_scores"][key] = stats.get(f"avg_{key}", 0)

            # 自己改善の推奨事項
            if analysis["adoption_rate"] < 0.2:
                analysis["recommendations"].append(
                    "採用率が低いです。検索キーワードの改善を検討してください。"
                )
            if stats.get("avg_relevance_score", 0) < 0.5:
                analysis["recommendations"].append(
                    "関連性スコアが低いです。より具体的な検索クエリを使用してください。"
                )

        return analysis


if __name__ == "__main__":
    # テスト
    logging.basicConfig(level=logging.INFO)
    evaluator = InformationEvaluator()

    test_item = {
        "id": "test123",
        "title": "OpenAI Realtime API Best Practices",
        "url": "https://example.com/article",
        "content": "This article discusses best practices for implementing voice assistants using OpenAI's Realtime API, including audio streaming optimization and error handling.",
    }

    result = evaluator.evaluate(test_item)
    print(json.dumps(result, ensure_ascii=False, indent=2))
