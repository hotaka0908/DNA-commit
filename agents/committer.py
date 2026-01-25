"""
Git コミットエージェント

生成・レビュー済みのコードをraspi-voiceリポジトリにコミット
"""

import os
import subprocess
import shutil
import logging
from datetime import datetime
from typing import Optional
import json

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

logger = logging.getLogger(__name__)


class GitCommitter:
    """Gitコミットエージェント"""

    def __init__(self, repo_path: Optional[str] = None):
        self.repo_path = repo_path or Config.TARGET_REPO_PATH
        self.commit_log_path = os.path.join(Config.LOGS_DIR, "commits.json")
        self._load_commit_history()

    def _load_commit_history(self):
        """コミット履歴を読み込む"""
        if os.path.exists(self.commit_log_path):
            with open(self.commit_log_path, "r", encoding="utf-8") as f:
                self.commit_history = json.load(f)
        else:
            self.commit_history = {"commits": [], "statistics": {}}

    def _save_commit_history(self):
        """コミット履歴を保存"""
        with open(self.commit_log_path, "w", encoding="utf-8") as f:
            json.dump(self.commit_history, f, ensure_ascii=False, indent=2)

    def _run_git(self, *args) -> tuple[bool, str]:
        """Gitコマンドを実行"""
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return True, result.stdout.strip()
            else:
                return False, result.stderr.strip()
        except Exception as e:
            return False, str(e)

    def create_branch(self, branch_name: str) -> bool:
        """新しいブランチを作成"""
        # 現在のブランチを確認
        success, current = self._run_git("branch", "--show-current")

        # ブランチ作成
        success, output = self._run_git("checkout", "-b", branch_name)
        if not success:
            # ブランチが既に存在する場合はチェックアウト
            success, output = self._run_git("checkout", branch_name)

        if success:
            logger.info(f"ブランチ作成/切り替え: {branch_name}")
        else:
            logger.error(f"ブランチ作成失敗: {output}")

        return success

    def apply_changes(self, generation: dict) -> list[str]:
        """生成されたコードを適用（diff/code両形式対応）"""
        applied_files = []

        # 新形式: トップレベルにdiffがある場合
        if generation.get("diff"):
            file_path = generation.get("file_path", "")
            diff_content = generation.get("diff", "")
            if file_path and diff_content:
                if self._apply_diff(file_path, diff_content):
                    applied_files.append(file_path)
                    logger.info(f"diff適用: {file_path}")

        # changes配列を処理
        for change in generation.get("changes", []):
            file_path = change.get("file_path", "")
            code = change.get("code", "")
            diff_content = change.get("diff", "")
            change_type = change.get("change_type", "")

            if not file_path:
                continue

            # 既に適用済みならスキップ
            if file_path in applied_files:
                continue

            target_path = os.path.join(self.repo_path, file_path)

            try:
                # diff形式の場合
                if diff_content and not code:
                    if self._apply_diff(file_path, diff_content):
                        applied_files.append(file_path)
                        logger.info(f"diff適用: {file_path}")
                    continue

                # code形式の場合（旧形式）
                if not code:
                    continue

                # ディレクトリ作成
                os.makedirs(os.path.dirname(target_path), exist_ok=True)

                # バックアップ作成
                if os.path.exists(target_path):
                    backup_path = target_path + ".backup"
                    shutil.copy2(target_path, backup_path)

                # コード適用
                if change_type == "new_file":
                    with open(target_path, "w", encoding="utf-8") as f:
                        f.write(code)
                elif change_type == "modify" or change_type == "refactor":
                    with open(target_path, "w", encoding="utf-8") as f:
                        f.write(code)
                elif change_type == "add_function":
                    # 既存ファイルに追加
                    with open(target_path, "a", encoding="utf-8") as f:
                        f.write("\n\n" + code)

                applied_files.append(file_path)
                logger.info(f"変更適用: {file_path} ({change_type})")

            except Exception as e:
                logger.error(f"変更適用失敗: {file_path} - {e}")

        return applied_files

    def _apply_diff(self, file_path: str, diff_content: str) -> bool:
        """diffをファイルに適用"""
        import tempfile

        try:
            # 一時ファイルにdiffを保存
            with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False) as f:
                f.write(diff_content)
                patch_file = f.name

            # git applyで適用（--check でドライランしてから本適用）
            success, output = self._run_git("apply", "--check", patch_file)
            if success:
                success, output = self._run_git("apply", patch_file)
                if success:
                    logger.info(f"git apply成功: {file_path}")
                    os.unlink(patch_file)
                    return True

            # git applyが失敗した場合、手動でパッチ適用を試みる
            logger.warning(f"git apply失敗、手動適用を試みます: {output}")
            result = self._manual_apply_diff(file_path, diff_content)
            os.unlink(patch_file)
            return result

        except Exception as e:
            logger.error(f"diff適用エラー: {e}")
            return False

    def _manual_apply_diff(self, file_path: str, diff_content: str) -> bool:
        """diffを手動で適用（追加行のみ抽出して追加）"""
        try:
            target_path = os.path.join(self.repo_path, file_path)

            # 追加行を抽出
            added_lines = []
            for line in diff_content.split('\n'):
                if line.startswith('+') and not line.startswith('+++'):
                    added_lines.append(line[1:])  # +を除去

            if not added_lines:
                return False

            # バックアップ
            if os.path.exists(target_path):
                shutil.copy2(target_path, target_path + ".backup")

            # ファイル末尾に追加（簡易版）
            with open(target_path, "a", encoding="utf-8") as f:
                f.write("\n\n# === DNA-commit auto-generated ===\n")
                f.write('\n'.join(added_lines))
                f.write("\n")

            logger.info(f"手動diff適用: {file_path} ({len(added_lines)}行追加)")
            return True

        except Exception as e:
            logger.error(f"手動diff適用失敗: {e}")
            return False

    def commit(self, generation: dict, reviewed: bool = False) -> dict:
        """変更をコミット"""
        result = {
            "success": False,
            "commit_hash": None,
            "branch": None,
            "files_changed": [],
            "error": None,
            "timestamp": datetime.now().isoformat(),
        }

        try:
            # ブランチ作成
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            branch_name = f"dna-auto/{timestamp}"
            if not self.create_branch(branch_name):
                result["error"] = "ブランチ作成失敗"
                return result

            result["branch"] = branch_name

            # 変更適用
            applied_files = self.apply_changes(generation)
            if not applied_files:
                result["error"] = "適用可能な変更がありません"
                return result

            result["files_changed"] = applied_files

            # ステージング
            for file_path in applied_files:
                success, output = self._run_git("add", file_path)
                if not success:
                    logger.warning(f"ステージング失敗: {file_path}")

            # コミット
            commit_message = generation.get("commit_message", "DNA-commit: 自動生成コード")
            if reviewed:
                commit_message = f"[REVIEWED] {commit_message}"
            else:
                commit_message = f"[AUTO] {commit_message}"

            commit_message += "\n\nGenerated by DNA-commit system"
            commit_message += f"\nSource: {generation.get('source_title', 'unknown')}"
            commit_message += f"\nRisk level: {generation.get('risk_level', 'unknown')}"

            success, output = self._run_git("commit", "-m", commit_message)
            if success:
                # コミットハッシュ取得
                success, commit_hash = self._run_git("rev-parse", "HEAD")
                result["commit_hash"] = commit_hash[:8] if success else None
                result["success"] = True
                logger.info(f"コミット成功: {result['commit_hash']} on {branch_name}")

                # 自動マージ & プッシュ
                if reviewed:
                    merge_success = self._merge_and_push(branch_name)
                    result["merged"] = merge_success
                    if merge_success:
                        logger.info(f"mainにマージ＆プッシュ完了")
                    else:
                        logger.warning(f"マージまたはプッシュに失敗しました")
            else:
                result["error"] = output
                logger.error(f"コミット失敗: {output}")

            # 履歴に追加
            self.commit_history["commits"].append(result)
            self._update_statistics(result)
            self._save_commit_history()

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"コミットエラー: {e}")

        return result

    def _update_statistics(self, result: dict):
        """統計情報を更新"""
        stats = self.commit_history["statistics"]
        stats["total_commits"] = stats.get("total_commits", 0) + 1

        if result.get("success"):
            stats["successful_commits"] = stats.get("successful_commits", 0) + 1
        else:
            stats["failed_commits"] = stats.get("failed_commits", 0) + 1

    def _merge_and_push(self, branch_name: str) -> bool:
        """ブランチをmainにマージしてプッシュ"""
        try:
            # mainブランチに切り替え
            success, output = self._run_git("checkout", "main")
            if not success:
                success, output = self._run_git("checkout", "master")
            if not success:
                logger.error(f"mainブランチへの切り替え失敗: {output}")
                return False

            # マージ
            success, output = self._run_git("merge", branch_name, "--no-edit")
            if not success:
                logger.error(f"マージ失敗: {output}")
                # コンフリクト時はマージを中止
                self._run_git("merge", "--abort")
                return False

            logger.info(f"マージ成功: {branch_name} → main")

            # プッシュ
            success, output = self._run_git("push", "origin", "main")
            if not success:
                logger.error(f"プッシュ失敗: {output}")
                return False

            logger.info("プッシュ成功: origin/main")

            # ブランチ削除
            success, output = self._run_git("branch", "-d", branch_name)
            if success:
                logger.info(f"ブランチ削除: {branch_name}")

            return True

        except Exception as e:
            logger.error(f"マージ/プッシュエラー: {e}")
            return False

    def revert_last_commit(self) -> bool:
        """最後のコミットをリバート"""
        success, output = self._run_git("revert", "--no-edit", "HEAD")
        if success:
            logger.info("コミットリバート成功")
        else:
            logger.error(f"リバート失敗: {output}")
        return success

    def switch_to_main(self) -> bool:
        """メインブランチに戻る"""
        success, output = self._run_git("checkout", "main")
        if not success:
            success, output = self._run_git("checkout", "master")
        return success

    def get_pending_branches(self) -> list[str]:
        """マージ待ちのDNAブランチを取得"""
        success, output = self._run_git("branch", "--list", "dna-auto/*")
        if success:
            branches = [b.strip().lstrip("* ") for b in output.split("\n") if b.strip()]
            return branches
        return []

    def get_statistics(self) -> dict:
        """統計情報を取得"""
        return self.commit_history.get("statistics", {})


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    committer = GitCommitter()

    print(f"ターゲットリポジトリ: {committer.repo_path}")
    print(f"コミット統計: {committer.get_statistics()}")
    print(f"待機中のブランチ: {committer.get_pending_branches()}")
