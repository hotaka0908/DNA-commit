#!/usr/bin/env python3
"""
DNA-commit: 自己進化システム

ネットから情報を収集し、AIが評価・コード生成・レビューを行い、
人間の介入なしに自動でシステムを進化させる。

使用方法:
    python main.py              # フルサイクルを1回実行
    python main.py --collect    # 情報収集のみ
    python main.py --evaluate   # 評価のみ
    python main.py --generate   # コード生成のみ
    python main.py --review     # レビューのみ
    python main.py --commit     # コミットのみ
    python main.py --cleanup    # クリーンアップのみ
    python main.py --status     # 現在の状態を表示
"""

import argparse
import logging
import json
from datetime import datetime

from agents import (
    InformationCollector,
    InformationEvaluator,
    CodeGenerator,
    GitCommitter,
    CodeReviewer,
    KnowledgeCleaner,
)
from config import Config

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger("DNA-commit")


class DNACommitOrchestrator:
    """自己進化システムのオーケストレーター"""

    def __init__(self):
        self.collector = InformationCollector()
        self.evaluator = InformationEvaluator()
        self.generator = CodeGenerator()
        self.committer = GitCommitter()
        self.reviewer = CodeReviewer()
        self.cleaner = KnowledgeCleaner()

    def run_full_cycle(self) -> dict:
        """フルサイクルを実行"""
        logger.info("=" * 60)
        logger.info("DNA-commit: 自己進化サイクル開始")
        logger.info("=" * 60)

        results = {
            "timestamp": datetime.now().isoformat(),
            "collection": None,
            "evaluation": None,
            "generation": None,
            "review": None,
            "commit": None,
            "cleanup": None,
            "errors": [],
        }

        try:
            # 1. 情報収集
            logger.info("\n[1/6] 情報収集")
            results["collection"] = self.run_collection()

            # 2. 情報評価
            logger.info("\n[2/6] 情報評価")
            results["evaluation"] = self.run_evaluation()

            # 3. コード生成
            logger.info("\n[3/6] コード生成")
            results["generation"] = self.run_generation()

            # 4. レビュー
            logger.info("\n[4/6] コードレビュー")
            results["review"] = self.run_review()

            # 5. コミット
            logger.info("\n[5/6] コミット")
            results["commit"] = self.run_commit()

            # 6. クリーンアップ
            logger.info("\n[6/6] クリーンアップ")
            results["cleanup"] = self.run_cleanup()

        except Exception as e:
            logger.error(f"サイクル中にエラー発生: {e}")
            results["errors"].append(str(e))

        # サマリー表示
        self._print_summary(results)

        return results

    def run_collection(self) -> dict:
        """情報収集を実行"""
        try:
            result = self.collector.collect_all()
            logger.info(f"収集完了: {result['new_items_count']}件の新規情報")
            return result
        except Exception as e:
            logger.error(f"収集エラー: {e}")
            return {"error": str(e)}

    def run_evaluation(self) -> dict:
        """情報評価を実行"""
        try:
            pending_items = self.collector.get_pending_items()
            logger.info(f"評価対象: {len(pending_items)}件")

            evaluations = []
            for item in pending_items:
                evaluation = self.evaluator.evaluate(item)
                evaluations.append(evaluation)

                # ステータス更新
                self.collector.update_item_status(
                    item["id"],
                    "evaluated",
                    evaluation
                )

            # 採用可能なアイテム
            adoptable = [
                e for e in evaluations
                if e.get("recommendation") == "adopt"
            ]

            return {
                "evaluated_count": len(evaluations),
                "adoptable_count": len(adoptable),
                "statistics": self.evaluator.get_statistics(),
            }
        except Exception as e:
            logger.error(f"評価エラー: {e}")
            return {"error": str(e)}

    def run_generation(self) -> dict:
        """コード生成を実行"""
        try:
            # 採用可能なアイテムを取得
            from agents.collector import InformationCollector
            collector = InformationCollector()

            adoptable_items = []
            for item in collector.collected_data.get("items", []):
                evaluation = item.get("evaluation", {})
                if evaluation.get("recommendation") == "adopt":
                    if item.get("status") != "code_generated":
                        item["evaluation"] = evaluation
                        adoptable_items.append(item)

            logger.info(f"コード生成対象: {len(adoptable_items)}件")

            generations = []
            for item in adoptable_items[:5]:  # 一度に最大5件
                generation = self.generator.generate(item)
                generations.append(generation)

                # ステータス更新
                collector.update_item_status(item["id"], "code_generated")

            return {
                "generated_count": len(generations),
                "generations": generations,
            }
        except Exception as e:
            logger.error(f"生成エラー: {e}")
            return {"error": str(e)}

    def run_review(self) -> dict:
        """コードレビューを実行"""
        try:
            pending_generations = self.generator.get_pending_generations()
            logger.info(f"レビュー対象: {len(pending_generations)}件")

            reviews = []
            for i, generation in enumerate(pending_generations):
                if generation.get("status") == "pending_review":
                    review = self.reviewer.review(generation)
                    reviews.append(review)

                    # ステータス更新
                    new_status = "approved" if review.get("approved") else "rejected"
                    self.generator.update_generation_status(i, new_status, review)

            # 自動承認可能なもの
            auto_approved = [
                r for r in reviews
                if self.reviewer.should_auto_approve(r)
            ]

            return {
                "reviewed_count": len(reviews),
                "auto_approved_count": len(auto_approved),
                "statistics": self.reviewer.get_statistics(),
            }
        except Exception as e:
            logger.error(f"レビューエラー: {e}")
            return {"error": str(e)}

    def run_commit(self) -> dict:
        """コミットを実行"""
        try:
            # 承認済みの生成を取得
            generations = self.generator.generation_history.get("generations", [])
            approved = [
                g for g in generations
                if g.get("status") == "approved" and g.get("review", {}).get("approved")
            ]

            logger.info(f"コミット対象: {len(approved)}件")

            commits = []
            for generation in approved[:3]:  # 一度に最大3件
                # 自動承認可能かチェック
                review = generation.get("review", {})
                if self.reviewer.should_auto_approve(review):
                    commit_result = self.committer.commit(generation, reviewed=True)
                    commits.append(commit_result)

                    if commit_result.get("success"):
                        generation["status"] = "committed"
                else:
                    logger.info(f"手動承認が必要: {generation.get('source_title', '')[:50]}")

            return {
                "committed_count": len([c for c in commits if c.get("success")]),
                "commits": commits,
                "statistics": self.committer.get_statistics(),
            }
        except Exception as e:
            logger.error(f"コミットエラー: {e}")
            return {"error": str(e)}

    def run_cleanup(self) -> dict:
        """クリーンアップを実行"""
        try:
            result = self.cleaner.run_full_cleanup()
            return result
        except Exception as e:
            logger.error(f"クリーンアップエラー: {e}")
            return {"error": str(e)}

    def get_status(self) -> dict:
        """現在の状態を取得"""
        return {
            "data_summary": self.cleaner.get_data_summary(),
            "evaluation_stats": self.evaluator.get_statistics(),
            "review_stats": self.reviewer.get_statistics(),
            "commit_stats": self.committer.get_statistics(),
            "cleanup_stats": self.cleaner.get_statistics(),
            "pending_branches": self.committer.get_pending_branches(),
            "feedback_analysis": self.evaluator.analyze_feedback(),
            "common_issues": self.reviewer.analyze_common_issues(),
        }

    def _print_summary(self, results: dict):
        """サマリーを表示"""
        logger.info("\n" + "=" * 60)
        logger.info("DNA-commit: サイクル完了サマリー")
        logger.info("=" * 60)

        if results.get("collection"):
            c = results["collection"]
            logger.info(f"収集: {c.get('new_items_count', 0)}件の新規情報")

        if results.get("evaluation"):
            e = results["evaluation"]
            logger.info(f"評価: {e.get('evaluated_count', 0)}件評価, {e.get('adoptable_count', 0)}件採用可能")

        if results.get("generation"):
            g = results["generation"]
            logger.info(f"生成: {g.get('generated_count', 0)}件のコード生成")

        if results.get("review"):
            r = results["review"]
            logger.info(f"レビュー: {r.get('reviewed_count', 0)}件レビュー, {r.get('auto_approved_count', 0)}件自動承認")

        if results.get("commit"):
            cm = results["commit"]
            logger.info(f"コミット: {cm.get('committed_count', 0)}件コミット")

        if results.get("cleanup"):
            cl = results["cleanup"]
            stale = cl.get("stale", {}).get("removed_count", 0) if cl.get("stale") else 0
            low_q = cl.get("low_quality", {}).get("removed_count", 0) if cl.get("low_quality") else 0
            logger.info(f"クリーンアップ: {stale + low_q}件削除")

        if results.get("errors"):
            logger.warning(f"エラー: {len(results['errors'])}件")

        logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="DNA-commit: 自己進化システム")
    parser.add_argument("--collect", action="store_true", help="情報収集のみ")
    parser.add_argument("--evaluate", action="store_true", help="評価のみ")
    parser.add_argument("--generate", action="store_true", help="コード生成のみ")
    parser.add_argument("--review", action="store_true", help="レビューのみ")
    parser.add_argument("--commit", action="store_true", help="コミットのみ")
    parser.add_argument("--cleanup", action="store_true", help="クリーンアップのみ")
    parser.add_argument("--status", action="store_true", help="現在の状態を表示")

    args = parser.parse_args()

    orchestrator = DNACommitOrchestrator()

    if args.collect:
        result = orchestrator.run_collection()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.evaluate:
        result = orchestrator.run_evaluation()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.generate:
        result = orchestrator.run_generation()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.review:
        result = orchestrator.run_review()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.commit:
        result = orchestrator.run_commit()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.cleanup:
        result = orchestrator.run_cleanup()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.status:
        status = orchestrator.get_status()
        print(json.dumps(status, ensure_ascii=False, indent=2))
    else:
        # フルサイクル実行
        result = orchestrator.run_full_cycle()


if __name__ == "__main__":
    main()
