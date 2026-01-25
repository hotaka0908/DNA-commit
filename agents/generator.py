"""
コード生成エージェント

評価された情報を元にraspi-voiceの改善コードを自動生成
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


# リポジトリごとのプロンプトテンプレート
REPO_TEMPLATES = {
    "raspi-voice8": {
        "description": "自分専用のパーソナルアシスタント - 生活を全面サポートするパートナー",
        "purpose": """【目的】自分の生活を全面サポートするパートナー

【ゴール】
- 自分の生活パターンを学習し、先回りでサポート
- メール・予定・タスクを完璧に管理
- 音声だけで全ての操作が完結
- プライバシーを守りながら24時間サポート
- 家族との連絡をスムーズに

【成功指標】応答速度1秒以内、認識精度95%以上、稼働率99%以上""",
        "structure": """raspi-voice8/
├── main.py                    # エントリーポイント
├── config.py                  # 設定
├── core/                      # コア機能
│   ├── audio.py               # 音声入出力
│   ├── openai_realtime_client.py  # OpenAI Realtime APIクライアント
│   ├── firebase_voice.py      # Firebase音声メッセージ
│   ├── firebase_signaling.py  # ビデオ通話シグナリング
│   └── webrtc.py              # WebRTC
├── capabilities/              # 能力モジュール
│   ├── communication.py       # Gmail連携
│   ├── calendar.py            # カレンダー連携
│   ├── schedule.py            # アラーム/リマインダー
│   ├── search.py              # Web検索（Tavily）
│   ├── memory.py              # 記憶/ライフログ
│   ├── vision.py              # ビジョン機能（GPT-4o）
│   └── videocall.py           # ビデオ通話
├── prompts/                   # システムプロンプト
└── docs/                      # Voice Messenger Webアプリ""",
    },
    "DNA-commit": {
        "description": "自己進化エンジン - 最も良い技術を自動で取り込み、人々の生活をより良くする装置",
        "purpose": """【目的】最も良い技術を自動で取り込み、人々の生活をより良くするためにプロジェクトを進化させる装置

【ゴール】
- 最新のAI/技術トレンドを自動で発見・評価
- 人間の介入なしに安全にコードを改善
- バグや脆弱性を自動で検出・修正
- パフォーマンスを継続的に最適化
- 新機能のアイデアを自動で提案・実装

【成功指標】採用された改善の数、コード品質スコアの向上、自動承認率""",
        "structure": """DNA-commit/
├── main.py              # メインオーケストレーター
├── scheduler.py         # 自動実行スケジューラー
├── config.py            # 設定
├── agents/              # エージェントモジュール
│   ├── collector.py     # 情報収集（Tavily/GitHub API）
│   ├── evaluator.py     # 情報評価（Claude API）
│   ├── generator.py     # コード生成（Claude API）
│   ├── committer.py     # Gitコミット
│   ├── reviewer.py      # コードレビュー
│   └── cleaner.py       # クリーンアップ
├── data/                # データ保存
└── logs/                # ログ""",
    },
}

CODE_GENERATION_PROMPT = """あなたは{repo_name}プロジェクトの改善コードを生成するエキスパートエンジニアです。

## ターゲットプロジェクト: {repo_name}
{repo_description}

{repo_purpose}

### 現在のプロジェクト構造
```
{repo_structure}
```

## 参考情報
タイトル: {title}
URL: {url}
内容: {content}
評価サマリー: {summary}
適用可能な領域: {applicable_areas}
期待される改善: {potential_improvements}

## タスク
上記の情報を元に、{repo_name}の**目的とゴールに沿った**改善コードを生成してください。
ユーザーの生活をより良くすることを第一に考えてください。

## 出力形式（JSON）
{{
    "changes": [
        {{
            "file_path": "改善対象のファイルパス（例: agents/collector.py）",
            "change_type": "new_file|modify|add_function|refactor",
            "description": "この変更の説明",
            "code": "生成されたコード（完全なファイル内容または追加コード）",
            "insert_after": "modify/add_functionの場合、この行の後に挿入（オプション）",
            "replace_function": "refactorの場合、置き換える関数名（オプション）"
        }}
    ],
    "commit_message": "この変更のコミットメッセージ",
    "user_benefit": "この改善がユーザーにもたらす具体的な恩恵",
    "risk_level": "low|medium|high",
    "test_suggestions": ["テスト方法の提案"],
    "rollback_plan": "問題発生時のロールバック手順"
}}

JSONのみを出力してください。コードは完全で実行可能なものにしてください。"""

# 改善版: 1ファイル・1関数に限定したプロンプト
SINGLE_CHANGE_PROMPT = """あなたは{repo_name}プロジェクトの改善コードを生成するエキスパートエンジニアです。

## ターゲットプロジェクト: {repo_name}
{repo_description}

{repo_purpose}

## 変更対象ファイル
パス: {file_path}

### 既存コード
```python
{existing_code}
```

## 参考情報
タイトル: {title}
内容: {content}
期待される改善: {potential_improvements}

## タスク
上記の既存コードを参考に、**1つの関数のみ**を追加または修正してください。
- 既存のコードスタイル、インポート、クラス構造を維持
- 変更は最小限に
- 既存の関数シグネチャを壊さない

## 出力形式（JSON）
{{
    "file_path": "{file_path}",
    "function_name": "変更または追加する関数名",
    "change_type": "add_function|modify_function",
    "diff": "unified diff形式（--- a/... +++ b/... @@ ... @@）",
    "description": "この変更の説明（1-2文）",
    "commit_message": "簡潔なコミットメッセージ",
    "risk_level": "low|medium|high"
}}

重要:
- diffは実際のunified diff形式で出力（git diffと同じ形式）
- 変更部分のみを含める（ファイル全体ではない）
- JSONのみを出力"""


class CodeGenerator:
    """コード生成エージェント"""

    def __init__(self):
        self.client = Anthropic(api_key=Config.get_anthropic_api_key())
        self.generation_log_path = os.path.join(Config.LOGS_DIR, "generations.json")
        self._load_generation_history()

    def _load_generation_history(self):
        """生成履歴を読み込む"""
        if os.path.exists(self.generation_log_path):
            with open(self.generation_log_path, "r", encoding="utf-8") as f:
                self.generation_history = json.load(f)
        else:
            self.generation_history = {"generations": [], "statistics": {}}

    def _save_generation_history(self):
        """生成履歴を保存"""
        with open(self.generation_log_path, "w", encoding="utf-8") as f:
            json.dump(self.generation_history, f, ensure_ascii=False, indent=2)

    def _read_existing_code(self, file_path: str) -> Optional[str]:
        """既存のコードを読み込む"""
        full_path = os.path.join(Config.TARGET_REPO_PATH, file_path)
        if os.path.exists(full_path):
            with open(full_path, "r", encoding="utf-8") as f:
                return f.read()
        return None

    def _gather_context(self, item: dict, target_repo: str) -> dict:
        """変更対象ファイルのコンテキストを収集"""
        evaluation = item.get("evaluation", {})
        applicable_areas = evaluation.get("applicable_areas", [])

        context = {
            "target_files": {},
            "related_files": {},
        }

        # 適用可能な領域からファイルを特定
        for area in applicable_areas:
            # ファイルパス形式の場合（例: core/audio.py）
            if "/" in area and area.endswith(".py"):
                existing_code = self._read_existing_code(area)
                if existing_code:
                    context["target_files"][area] = {
                        "code": existing_code,
                        "lines": len(existing_code.splitlines()),
                    }
                else:
                    # 新規ファイルとしてマーク
                    context["target_files"][area] = {
                        "code": None,
                        "lines": 0,
                        "is_new": True,
                    }

        # target_filesが空の場合、デフォルトのターゲットを推測
        if not context["target_files"]:
            repo_template = REPO_TEMPLATES.get(target_repo, {})
            # 構造から主要ファイルを特定（最初のpyファイル）
            if target_repo == "raspi-voice8":
                default_targets = ["core/audio.py", "main.py"]
            else:
                default_targets = ["main.py"]

            for target in default_targets:
                existing_code = self._read_existing_code(target)
                if existing_code:
                    context["target_files"][target] = {
                        "code": existing_code,
                        "lines": len(existing_code.splitlines()),
                    }
                    break

        logger.info(f"コンテキスト収集完了: {len(context['target_files'])}ファイル")
        return context

    def _extract_json(self, text: str) -> str:
        """テキストからJSON部分を抽出"""
        import re

        # ```json ... ``` を抽出
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', text)
        if json_match:
            return json_match.group(1).strip()

        # ``` ... ``` を抽出
        code_match = re.search(r'```\s*([\s\S]*?)\s*```', text)
        if code_match:
            return code_match.group(1).strip()

        # { で始まり } で終わる部分を抽出
        brace_match = re.search(r'(\{[\s\S]*\})', text)
        if brace_match:
            return brace_match.group(1).strip()

        return text.strip()

    def _repair_json(self, json_str: str) -> str:
        """不完全なJSONを修復"""
        # 未閉じの文字列を閉じる
        if json_str.count('"') % 2 == 1:
            json_str += '"'

        # 未閉じの括弧を閉じる
        open_braces = json_str.count('{') - json_str.count('}')
        open_brackets = json_str.count('[') - json_str.count(']')

        if open_brackets > 0:
            json_str += ']' * open_brackets
        if open_braces > 0:
            json_str += '}' * open_braces

        return json_str

    def _generate_single_change(self, item: dict, file_path: str,
                                existing_code: str, target_repo: str) -> dict:
        """1つのファイルに対する変更を生成"""
        evaluation = item.get("evaluation", {})
        repo_template = REPO_TEMPLATES.get(target_repo, REPO_TEMPLATES["raspi-voice8"])

        # 既存コードが長すぎる場合は関連部分のみ抽出
        code_to_include = existing_code
        if existing_code and len(existing_code) > 3000:
            # 最初の3000文字 + 末尾の情報
            code_to_include = existing_code[:2500] + "\n\n# ... (中略) ...\n\n" + existing_code[-500:]

        prompt = SINGLE_CHANGE_PROMPT.format(
            repo_name=target_repo,
            repo_description=repo_template["description"],
            repo_purpose=repo_template.get("purpose", ""),
            file_path=file_path,
            existing_code=code_to_include if code_to_include else "# 新規ファイル",
            title=item.get("title", ""),
            content=item.get("content", item.get("description", ""))[:2000],
            potential_improvements=", ".join(evaluation.get("potential_improvements", [])),
        )

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,  # diffのみなので少なめで十分
            messages=[{"role": "user", "content": prompt}],
        )

        result_text = response.content[0].text
        json_str = self._extract_json(result_text)

        try:
            generation = json.loads(json_str)
        except json.JSONDecodeError:
            repaired = self._repair_json(json_str)
            generation = json.loads(repaired)

        return generation

    def _validate_generation(self, generation: dict) -> tuple[bool, list[str]]:
        """生成結果の構文チェックとバリデーション"""
        import ast
        errors = []

        # 必須フィールドの確認
        required_fields = ["file_path", "function_name", "diff", "commit_message"]
        for field in required_fields:
            if field not in generation:
                errors.append(f"必須フィールド '{field}' がありません")

        # diffが空でないか確認
        diff = generation.get("diff", "")
        if not diff or len(diff.strip()) < 10:
            errors.append("diffが空または短すぎます")

        # diffに切れた兆候がないか確認
        if diff:
            # 閉じ括弧の確認
            open_parens = diff.count('(') - diff.count(')')
            open_brackets = diff.count('[') - diff.count(']')
            open_braces = diff.count('{') - diff.count('}')

            if open_parens > 2 or open_brackets > 2 or open_braces > 2:
                errors.append("diffに未閉じの括弧があります（コードが途中で切れている可能性）")

            # 文字列が閉じていない
            if diff.count('"""') % 2 == 1:
                errors.append("三重引用符が閉じていません")
            if diff.count("'''") % 2 == 1:
                errors.append("三重シングル引用符が閉じていません")

        # diffから追加コードを抽出して構文チェック
        added_lines = []
        for line in diff.split('\n'):
            if line.startswith('+') and not line.startswith('+++'):
                added_lines.append(line[1:])  # +を除去

        if added_lines:
            added_code = '\n'.join(added_lines)
            # 完全な関数として構文チェック（インデントを調整）
            try:
                # 単純な構文チェック
                compile(added_code, '<generated>', 'exec')
            except SyntaxError as e:
                # 部分的なコードの場合はエラーを無視
                if "unexpected EOF" not in str(e) and "expected" not in str(e).lower():
                    errors.append(f"構文エラーの可能性: {e}")

        is_valid = len(errors) == 0
        return is_valid, errors

    def generate(self, item: dict) -> dict:
        """情報を元にコードを生成（改善版: 1ファイル・1関数に限定）"""
        target_repo = item.get("target_repo", "raspi-voice8")

        # Step 1: 既存コードのコンテキストを収集
        context = self._gather_context(item, target_repo)

        if not context["target_files"]:
            logger.warning("変更対象ファイルが特定できません")
            return self._create_fallback_generation(item, "変更対象ファイルが特定できません")

        # Step 2: 各ファイルに対して個別に変更を生成（1ファイルのみ）
        # 複数ファイル同時生成を避け、最初のターゲットのみ処理
        all_changes = []
        validation_errors = []

        for file_path, file_info in list(context["target_files"].items())[:1]:  # 1ファイルのみ
            existing_code = file_info.get("code", "")

            max_retries = 3
            last_error = None

            for attempt in range(max_retries):
                try:
                    # Step 2a: 単一ファイルの変更を生成
                    single_change = self._generate_single_change(
                        item, file_path, existing_code, target_repo
                    )

                    # Step 2b: バリデーション
                    is_valid, errors = self._validate_generation(single_change)

                    if is_valid:
                        all_changes.append(single_change)
                        logger.info(f"生成成功: {file_path}")
                        break
                    else:
                        last_error = "; ".join(errors)
                        logger.warning(f"バリデーションエラー (attempt {attempt + 1}): {last_error}")
                        validation_errors.extend(errors)

                except json.JSONDecodeError as e:
                    last_error = str(e)
                    logger.warning(f"JSON parse error (attempt {attempt + 1}/{max_retries}): {e}")
                except Exception as e:
                    last_error = str(e)
                    logger.error(f"Generation error (attempt {attempt + 1}/{max_retries}): {e}")

            else:
                # 全リトライ失敗
                logger.error(f"ファイル {file_path} の生成失敗: {last_error}")

        # Step 3: 結果をまとめる
        if not all_changes:
            return self._create_fallback_generation(
                item,
                f"全ファイルの生成失敗: {'; '.join(validation_errors) if validation_errors else 'Unknown error'}"
            )

        # 新しい形式で結果を構築
        first_change = all_changes[0]
        generation = {
            "file_path": first_change.get("file_path"),
            "function_name": first_change.get("function_name"),
            "change_type": first_change.get("change_type", "modify_function"),
            "diff": first_change.get("diff"),
            "description": first_change.get("description", ""),
            "commit_message": first_change.get("commit_message", ""),
            "risk_level": first_change.get("risk_level", "low"),
            # メタデータ
            "generated_at": datetime.now().isoformat(),
            "source_item_id": item.get("id"),
            "source_title": item.get("title"),
            "target_repo": target_repo,
            "status": "pending_review",
            # 後方互換性のためchanges配列も保持
            "changes": all_changes,
        }

        # 履歴に追加
        self.generation_history["generations"].append(generation)
        self._update_statistics(generation)
        self._save_generation_history()

        logger.info(f"コード生成完了 ({target_repo}): {item.get('title', '')[:50]}")
        return generation

    def _create_fallback_generation(self, item: dict, error: str) -> dict:
        """エラー時のフォールバック"""
        target_repo = item.get("target_repo", "raspi-voice8")
        return {
            "file_path": None,
            "function_name": None,
            "change_type": None,
            "diff": None,
            "description": f"生成失敗: {error}",
            "commit_message": f"[FAILED] コード生成失敗: {item.get('title', '')[:50]}",
            "risk_level": "high",
            "error": error,
            "generated_at": datetime.now().isoformat(),
            "source_item_id": item.get("id"),
            "source_title": item.get("title"),
            "target_repo": target_repo,
            "status": "failed",
            "changes": [],
        }

    def _update_statistics(self, generation: dict):
        """統計情報を更新"""
        stats = self.generation_history["statistics"]
        stats["total_generations"] = stats.get("total_generations", 0) + 1

        if generation.get("error"):
            stats["failed_generations"] = stats.get("failed_generations", 0) + 1
        else:
            stats["successful_generations"] = stats.get("successful_generations", 0) + 1

        risk = generation.get("risk_level", "unknown")
        stats[f"risk_{risk}"] = stats.get(f"risk_{risk}", 0) + 1

    def save_generated_code(self, generation: dict) -> list[str]:
        """生成されたコード/diffをファイルに保存"""
        saved_files = []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 新形式: diff を直接保存
        if generation.get("diff"):
            file_path = generation.get("file_path", "unknown.py")
            diff = generation.get("diff", "")

            # diff ファイルとして保存
            save_path = os.path.join(
                Config.GENERATED_CODE_DIR,
                timestamp,
                file_path.replace(".py", ".diff")
            )

            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            with open(save_path, "w", encoding="utf-8") as f:
                f.write(diff)

            saved_files.append(save_path)
            logger.info(f"生成diff保存: {save_path}")

        # 旧形式との互換性: changes配列にcodeがある場合
        for change in generation.get("changes", []):
            file_path = change.get("file_path", "")
            code = change.get("code", "")
            diff = change.get("diff", "")

            if not file_path:
                continue

            # codeがある場合（旧形式）
            if code:
                save_path = os.path.join(
                    Config.GENERATED_CODE_DIR,
                    timestamp,
                    file_path
                )
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(code)
                saved_files.append(save_path)
                logger.info(f"生成コード保存: {save_path}")

            # diffがある場合（新形式）
            elif diff and file_path.replace(".py", ".diff") not in [os.path.basename(f) for f in saved_files]:
                save_path = os.path.join(
                    Config.GENERATED_CODE_DIR,
                    timestamp,
                    file_path.replace(".py", ".diff")
                )
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(diff)
                saved_files.append(save_path)
                logger.info(f"生成diff保存: {save_path}")

        return saved_files

    def get_pending_generations(self) -> list[dict]:
        """レビュー待ちの生成を取得"""
        return [
            gen for gen in self.generation_history["generations"]
            if gen.get("status") == "pending_review"
        ]

    def update_generation_status(self, index: int, status: str, review_result: Optional[dict] = None):
        """生成のステータスを更新"""
        if 0 <= index < len(self.generation_history["generations"]):
            self.generation_history["generations"][index]["status"] = status
            if review_result:
                self.generation_history["generations"][index]["review"] = review_result
            self._save_generation_history()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    generator = CodeGenerator()

    test_item = {
        "id": "test123",
        "title": "Improved Audio Buffer Handling",
        "content": "A technique for reducing audio latency by using double buffering and async processing.",
        "evaluation": {
            "summary": "オーディオバッファの改善テクニック",
            "applicable_areas": ["core/audio.py"],
            "potential_improvements": ["遅延削減", "安定性向上"],
        }
    }

    result = generator.generate(test_item)
    print(json.dumps(result, ensure_ascii=False, indent=2))
