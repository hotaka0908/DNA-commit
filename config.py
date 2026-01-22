"""
DNA-commit 設定ファイル

自己進化システムの設定を管理
"""

import os
from dotenv import load_dotenv

# 環境変数の読み込み
env_path = os.path.expanduser("~/.ai-necklace/.env")
load_dotenv(env_path)


class Config:
    """アプリケーション設定"""

    # プロジェクトパス
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(BASE_DIR, "data")
    KNOWLEDGE_DIR = os.path.join(DATA_DIR, "knowledge")
    GENERATED_CODE_DIR = os.path.join(DATA_DIR, "generated_code")
    LOGS_DIR = os.path.join(BASE_DIR, "logs")

    # ターゲットリポジトリ（raspi-voice8）
    TARGET_REPO_PATH = os.path.expanduser("~/dev/raspi-voice8")

    # 検索キーワード（具体的・実用的）
    SEARCH_TOPICS = [
        # === バグ修正・安定性 ===
        "PyAudio buffer overflow fix",
        "Python asyncio memory leak solution",
        "OpenAI Realtime API error handling",
        "WebSocket reconnection best practices Python",
        "Raspberry Pi audio crackling fix",

        # === 新機能アイデア ===
        "OpenAI Realtime API new features 2025",
        "voice assistant wake word detection Python",
        "offline speech recognition Raspberry Pi",
        "GPT-4o vision API use cases",
        "smart home voice control integration",

        # === パフォーマンス最適化 ===
        "Python audio latency reduction techniques",
        "Raspberry Pi 4 low latency audio",
        "asyncio performance optimization",
        "WebRTC audio quality improvement",
        "PyAudio vs sounddevice performance",

        # === セキュリティ ===
        "voice assistant security best practices",
        "API key management Python",
        "Firebase security rules voice app",
    ]

    # GitHub検索キーワード（具体的なリポジトリ発見用）
    GITHUB_TOPICS = [
        # 類似プロジェクト
        "openai-realtime-api voice",
        "raspberry-pi assistant GPT",
        "python voice assistant async",

        # 特定技術
        "pyaudio streaming example",
        "aiortc raspberry pi",
        "whisper realtime transcription",

        # 改善手法
        "audio buffer management python",
        "gpio button debounce python",
    ]

    # 情報評価の閾値
    QUALITY_THRESHOLD = 0.7  # 0.7以上の情報のみ採用
    RELEVANCE_THRESHOLD = 0.6  # raspi-voiceへの関連性

    # 自動削除の閾値
    STALENESS_DAYS = 30  # 30日以上古い情報は再評価
    MIN_USEFULNESS_SCORE = 0.3  # これ以下は削除候補

    # API設定
    @classmethod
    def get_anthropic_api_key(cls) -> str:
        """Anthropic APIキーを取得"""
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise ValueError("ANTHROPIC_API_KEY が設定されていません")
        return key

    @classmethod
    def get_openai_api_key(cls) -> str:
        """OpenAI APIキーを取得"""
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise ValueError("OPENAI_API_KEY が設定されていません")
        return key

    @classmethod
    def get_tavily_api_key(cls) -> str:
        """Tavily APIキーを取得"""
        key = os.getenv("TAVILY_API_KEY")
        if not key:
            raise ValueError("TAVILY_API_KEY が設定されていません")
        return key

    @classmethod
    def get_github_token(cls) -> str:
        """GitHub トークンを取得（オプション）"""
        return os.getenv("GITHUB_TOKEN", "")


# ディレクトリ作成
os.makedirs(Config.DATA_DIR, exist_ok=True)
os.makedirs(Config.KNOWLEDGE_DIR, exist_ok=True)
os.makedirs(Config.GENERATED_CODE_DIR, exist_ok=True)
os.makedirs(Config.LOGS_DIR, exist_ok=True)
