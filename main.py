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
import os
from datetime import datetime, timedelta

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
    """自己進化システムのオーケストレーター（複数リポジトリ対応）"""

    # 最小実行間隔（時間）
    MIN_INTERVAL_HOURS = 4

    def __init__(self):
        self.collector = InformationCollector()
        self.evaluator = InformationEvaluator()
        self.generator = CodeGenerator()
        self.reviewer = CodeReviewer()
        self.cleaner = KnowledgeCleaner()

        # 複数リポジトリ用のコミッター
        self.committers = {}
        for repo_name, repo_config in Config.TARGET_REPOS.items():
            self.committers[repo_name] = GitCommitter(repo_config["path"])

        # デフォルトコミッター（後方互換性）
        self.committer = self.committers.get("raspi-voice8", GitCommitter())

        # 実行記録ファイル
        self.run_log_path = os.path.join(Config.LOGS_DIR, "run_history.json")

    def _load_run_history(self) -> dict:
        """実行履歴を読み込む"""
        if os.path.exists(self.run_log_path):
            try:
                with open(self.run_log_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"runs": []}

    def _save_run_history(self, history: dict):
        """実行履歴を保存"""
        with open(self.run_log_path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

    def _should_run_full_cycle(self) -> tuple[bool, str]:
        """フルサイクルを実行すべきか判定"""
        history = self._load_run_history()
        runs = history.get("runs", [])

        if not runs:
            return True, "初回実行"

        # 最後の成功した実行を取得
        last_run = runs[-1]
        last_time_str = last_run.get("timestamp")

        if not last_time_str:
            return True, "前回実行時刻不明"

        try:
            last_time = datetime.fromisoformat(last_time_str)
            elapsed = datetime.now() - last_time
            min_interval = timedelta(hours=self.MIN_INTERVAL_HOURS)

            if elapsed < min_interval:
                remaining = min_interval - elapsed
                return False, f"前回実行から{elapsed.seconds // 3600}時間{(elapsed.seconds % 3600) // 60}分（{self.MIN_INTERVAL_HOURS}時間間隔まで残り{remaining.seconds // 60}分）"

            return True, f"前回実行から{elapsed.seconds // 3600}時間{(elapsed.seconds % 3600) // 60}分経過"
        except Exception as e:
            return True, f"時刻パースエラー: {e}"

    def _record_run(self, results: dict):
        """実行を記録"""
        history = self._load_run_history()
        history["runs"].append({
            "timestamp": datetime.now().isoformat(),
            "success": not results.get("errors"),
            "summary": {
                "collected": results.get("collection", {}).get("new_items_count", 0),
                "evaluated": results.get("evaluation", {}).get("evaluated_count", 0),
            }
        })
        # 最新100件のみ保持
        history["runs"] = history["runs"][-100:]
        self._save_run_history(history)

    def run_full_cycle(self, force: bool = False) -> dict:
        """フルサイクルを実行（全リポジトリ対象）"""
        # 重複実行チェック
        should_run, reason = self._should_run_full_cycle()
        if not should_run and not force:
            logger.info("=" * 60)
            logger.info("DNA-commit: スキップ")
            logger.info(f"理由: {reason}")
            logger.info("=" * 60)
            return {"skipped": True, "reason": reason}

        logger.info("=" * 60)
        logger.info("DNA-commit: 自己進化サイクル開始")
        logger.info(f"実行理由: {reason}")
        logger.info(f"対象リポジトリ: {', '.join(Config.TARGET_REPOS.keys())}")
        logger.info("=" * 60)

        results = {
            "timestamp": datetime.now().isoformat(),
            "target_repos": list(Config.TARGET_REPOS.keys()),
            "collection": None,
            "evaluation": None,
            "generation": {},  # リポジトリごとの結果
            "review": {},
            "commit": {},
            "cleanup": None,
            "errors": [],
        }

        try:
            # 1. 情報収集（全リポジトリ共通）
            logger.info("\n[1/6] 情報収集")
            results["collection"] = self.run_collection()

            # 2. 情報評価（全リポジトリ共通）
            logger.info("\n[2/6] 情報評価")
            results["evaluation"] = self.run_evaluation()

            # 3-5. 各リポジトリに対してコード生成・レビュー・コミット
            for repo_name, repo_config in Config.TARGET_REPOS.items():
                logger.info(f"\n{'='*40}")
                logger.info(f"処理中: {repo_name}")
                logger.info(f"{'='*40}")

                # 3. コード生成
                logger.info(f"\n[3/6] コード生成 ({repo_name})")
                results["generation"][repo_name] = self.run_generation(repo_name)

                # 4. レビュー
                logger.info(f"\n[4/6] コードレビュー ({repo_name})")
                results["review"][repo_name] = self.run_review()

                # 5. コミット
                logger.info(f"\n[5/6] コミット ({repo_name})")
                results["commit"][repo_name] = self.run_commit(repo_name)

            # 6. クリーンアップ
            logger.info("\n[6/6] クリーンアップ")
            results["cleanup"] = self.run_cleanup()

        except Exception as e:
            logger.error(f"サイクル中にエラー発生: {e}")
            results["errors"].append(str(e))

        # 実行記録
        self._record_run(results)

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

    def run_generation(self, target_repo: str = "raspi-voice8") -> dict:
        """コード生成を実行（ターゲットリポジトリ指定）"""
        try:
            # 採用可能なアイテムを取得
            from agents.collector import InformationCollector
            collector = InformationCollector()

            adoptable_items = []
            for item in collector.collected_data.get("items", []):
                evaluation = item.get("evaluation", {})
                if evaluation.get("recommendation") == "adopt":
                    # まだコード生成されていない、かつこのリポジトリ用に生成されていない
                    generated_for = item.get("generated_for", [])
                    if target_repo not in generated_for:
                        item["evaluation"] = evaluation
                        item["target_repo"] = target_repo
                        adoptable_items.append(item)

            logger.info(f"コード生成対象 ({target_repo}): {len(adoptable_items)}件")

            generations = []
            for item in adoptable_items[:3]:  # 一度に最大3件（各リポジトリ）
                # ターゲットリポジトリ情報を追加
                item["target_repo_config"] = Config.TARGET_REPOS.get(target_repo, {})
                generation = self.generator.generate(item)
                generation["target_repo"] = target_repo
                generations.append(generation)

                # ステータス更新
                generated_for = item.get("generated_for", [])
                generated_for.append(target_repo)
                collector.update_item_status(
                    item["id"],
                    "code_generated",
                    {"generated_for": generated_for}
                )

            return {
                "target_repo": target_repo,
                "generated_count": len(generations),
                "generations": generations,
            }
        except Exception as e:
            logger.error(f"生成エラー ({target_repo}): {e}")
            return {"error": str(e), "target_repo": target_repo}

    def run_review(self) -> dict:
        """コードレビューを実行"""
        try:
            all_generations = self.generator.generation_history.get("generations", [])
            pending_count = sum(1 for g in all_generations if g.get("status") == "pending_review")
            logger.info(f"レビュー対象: {pending_count}件")

            reviews = []
            for i, generation in enumerate(all_generations):
                if generation.get("status") == "pending_review":
                    review = self.reviewer.review(generation)
                    reviews.append(review)

                    # ステータス更新（スコアベースで判定）
                    if self.reviewer.should_auto_approve(review):
                        new_status = "approved"
                    elif review.get("recommendation") == "reject":
                        new_status = "rejected"
                    else:
                        new_status = "pending_manual_review"
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

    def run_commit(self, target_repo: str = "raspi-voice8") -> dict:
        """コミットを実行（ターゲットリポジトリ指定）"""
        try:
            # このリポジトリ用のコミッターを取得
            committer = self.committers.get(target_repo)
            if not committer:
                return {"error": f"Unknown repository: {target_repo}"}

            # 承認済みの生成を取得（このリポジトリ用のもののみ）
            generations = self.generator.generation_history.get("generations", [])
            approved = [
                g for g in generations
                if g.get("status") == "approved"
                and g.get("target_repo") == target_repo
            ]

            logger.info(f"コミット対象 ({target_repo}): {len(approved)}件")

            commits = []
            for generation in approved[:2]:  # 一度に最大2件（各リポジトリ）
                # 自動承認可能かチェック
                review = generation.get("review", {})
                if self.reviewer.should_auto_approve(review):
                    commit_result = committer.commit(generation, reviewed=True)
                    commits.append(commit_result)

                    if commit_result.get("success"):
                        generation["status"] = "committed"
                else:
                    logger.info(f"手動承認が必要: {generation.get('source_title', '')[:50]}")

            return {
                "target_repo": target_repo,
                "committed_count": len([c for c in commits if c.get("success")]),
                "commits": commits,
                "statistics": committer.get_statistics(),
            }
        except Exception as e:
            logger.error(f"コミットエラー ({target_repo}): {e}")
            return {"error": str(e), "target_repo": target_repo}

    def run_cleanup(self) -> dict:
        """クリーンアップを実行"""
        try:
            result = self.cleaner.run_full_cleanup()
            return result
        except Exception as e:
            logger.error(f"クリーンアップエラー: {e}")
            return {"error": str(e)}

    def get_status(self) -> dict:
        """現在の状態を取得（全リポジトリ）"""
        # 各リポジトリのコミット統計
        commit_stats = {}
        pending_branches = {}
        for repo_name, committer in self.committers.items():
            commit_stats[repo_name] = committer.get_statistics()
            pending_branches[repo_name] = committer.get_pending_branches()

        return {
            "target_repos": list(Config.TARGET_REPOS.keys()),
            "data_summary": self.cleaner.get_data_summary(),
            "evaluation_stats": self.evaluator.get_statistics(),
            "review_stats": self.reviewer.get_statistics(),
            "commit_stats": commit_stats,
            "cleanup_stats": self.cleaner.get_statistics(),
            "pending_branches": pending_branches,
            "feedback_analysis": self.evaluator.analyze_feedback(),
            "common_issues": self.reviewer.analyze_common_issues(),
        }

    def _print_summary(self, results: dict):
        """サマリーを表示（複数リポジトリ対応）"""
        logger.info("\n" + "=" * 60)
        logger.info("DNA-commit: サイクル完了サマリー")
        logger.info("=" * 60)

        if results.get("collection"):
            c = results["collection"]
            logger.info(f"収集: {c.get('new_items_count', 0)}件の新規情報")

        if results.get("evaluation"):
            e = results["evaluation"]
            logger.info(f"評価: {e.get('evaluated_count', 0)}件評価, {e.get('adoptable_count', 0)}件採用可能")

        # 各リポジトリの結果
        for repo_name in results.get("target_repos", []):
            logger.info(f"\n--- {repo_name} ---")

            gen = results.get("generation", {}).get(repo_name, {})
            if gen and not gen.get("error"):
                logger.info(f"  生成: {gen.get('generated_count', 0)}件")

            rev = results.get("review", {}).get(repo_name, {})
            if rev and not rev.get("error"):
                logger.info(f"  レビュー: {rev.get('reviewed_count', 0)}件, 自動承認: {rev.get('auto_approved_count', 0)}件")

            cm = results.get("commit", {}).get(repo_name, {})
            if cm and not cm.get("error"):
                logger.info(f"  コミット: {cm.get('committed_count', 0)}件")

        if results.get("cleanup"):
            cl = results["cleanup"]
            stale = cl.get("stale", {}).get("removed_count", 0) if cl.get("stale") else 0
            low_q = cl.get("low_quality", {}).get("removed_count", 0) if cl.get("low_quality") else 0
            logger.info(f"\nクリーンアップ: {stale + low_q}件削除")

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
    parser.add_argument("--force", action="store_true", help="重複チェックをスキップして強制実行")

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
        result = orchestrator.run_full_cycle(force=args.force)


if __name__ == "__main__":
    main()


# === DNA-commit auto-generated ===
import json


async def handle_search_request(query: str, search_depth: str = "basic", max_results: int = 5) -> Optional[dict]:
    """
    Tavily APIを使用してリアルタイム検索を実行
    
    Args:
        query: 検索クエリ
        search_depth: 検索の深度 (basic, fast, advanced, ultra-fast)
        max_results: 最大結果数 (1-20)
    
    Returns:
        検索結果辞書またはNone（エラー時）
    """
    try:
        # 入力バリデーション
        if not query or not isinstance(query, str):
            logger.warning("Invalid query provided")
            return None
            
        query = query.strip()[:500]  # サニタイズ: 長さ制限
        
        if search_depth not in ["basic", "fast", "advanced", "ultra-fast"]:
            search_depth = "basic"
            
        max_results = max(1, min(max_results, 20))  # 範囲チェック
        
        # APIキーを環境変数から取得
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            logger.warning("Tavily API key not found")
            return None
            
        # 検索パラメータ
        search_params = {
            "query": query,
            "search_depth": search_depth,
            "max_results": max_results,
            "topic": "general"
        }
        
        # 検索実行をログ（クエリの一部のみ）
        safe_query = query[:50] + "..." if len(query) > 50 else query
        logger.info(f"Search request: {safe_query}")
        
        # TODO: 実際のAPIコール実装は次のイテレーションで
        return {"status": "ready", "params": search_params}
        
    except Exception as e:
        logger.error(f"Search request failed: {str(e)[:100]}")
        return None


def signal_handler(sig, frame):
