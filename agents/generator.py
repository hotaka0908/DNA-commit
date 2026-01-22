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
        "description": "Raspberry Pi上で動作するOpenAI Realtime API使用の音声AIアシスタント",
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
        "description": "AIが自動でコードを改善する自己進化システム",
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
上記の情報を元に、{repo_name}の改善コードを生成してください。

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
    "risk_level": "low|medium|high",
    "test_suggestions": ["テスト方法の提案"],
    "rollback_plan": "問題発生時のロールバック手順"
}}

JSONのみを出力してください。コードは完全で実行可能なものにしてください。"""


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

    def generate(self, item: dict) -> dict:
        """情報を元にコードを生成（ターゲットリポジトリ対応）"""
        try:
            evaluation = item.get("evaluation", {})
            target_repo = item.get("target_repo", "raspi-voice8")

            # リポジトリ情報を取得
            repo_template = REPO_TEMPLATES.get(target_repo, REPO_TEMPLATES["raspi-voice8"])

            prompt = CODE_GENERATION_PROMPT.format(
                repo_name=target_repo,
                repo_description=repo_template["description"],
                repo_structure=repo_template["structure"],
                title=item.get("title", ""),
                url=item.get("url", ""),
                content=item.get("content", item.get("description", ""))[:4000],
                summary=evaluation.get("summary", ""),
                applicable_areas=", ".join(evaluation.get("applicable_areas", [])),
                potential_improvements=", ".join(evaluation.get("potential_improvements", [])),
            )

            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}],
            )

            result_text = response.content[0].text
            # JSON部分を抽出
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0]
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0]

            generation = json.loads(result_text.strip())
            generation["generated_at"] = datetime.now().isoformat()
            generation["source_item_id"] = item.get("id")
            generation["source_title"] = item.get("title")
            generation["target_repo"] = target_repo
            generation["status"] = "pending_review"

            # 履歴に追加
            self.generation_history["generations"].append(generation)
            self._update_statistics(generation)
            self._save_generation_history()

            logger.info(f"コード生成完了 ({target_repo}): {item.get('title', '')[:50]}")
            return generation

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            return self._create_fallback_generation(item, str(e))
        except Exception as e:
            logger.error(f"Generation error: {e}")
            return self._create_fallback_generation(item, str(e))

    def _create_fallback_generation(self, item: dict, error: str) -> dict:
        """エラー時のフォールバック"""
        return {
            "changes": [],
            "commit_message": f"[FAILED] コード生成失敗: {item.get('title', '')[:50]}",
            "risk_level": "high",
            "test_suggestions": ["手動でのコード確認が必要"],
            "rollback_plan": "変更なし",
            "error": error,
            "generated_at": datetime.now().isoformat(),
            "source_item_id": item.get("id"),
            "status": "failed",
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
        """生成されたコードをファイルに保存"""
        saved_files = []

        for change in generation.get("changes", []):
            file_path = change.get("file_path", "")
            code = change.get("code", "")
            change_type = change.get("change_type", "")

            if not file_path or not code:
                continue

            # 生成コード保存先
            save_path = os.path.join(
                Config.GENERATED_CODE_DIR,
                datetime.now().strftime("%Y%m%d_%H%M%S"),
                file_path
            )

            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            with open(save_path, "w", encoding="utf-8") as f:
                f.write(code)

            saved_files.append(save_path)
            logger.info(f"生成コード保存: {save_path}")

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
