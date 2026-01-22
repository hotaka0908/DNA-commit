#!/bin/bash
# DNA-commit セットアップスクリプト

set -e

echo "==================================="
echo "DNA-commit セットアップ"
echo "==================================="

# ディレクトリ作成
mkdir -p data/knowledge
mkdir -p data/generated_code
mkdir -p logs

# Python仮想環境作成
echo "Python仮想環境を作成中..."
python3 -m venv venv
source venv/bin/activate

# 依存関係インストール
echo "依存関係をインストール中..."
pip install --upgrade pip
pip install -r requirements.txt

# APIキー確認
ENV_FILE="$HOME/.ai-necklace/.env"
if [ -f "$ENV_FILE" ]; then
    echo "APIキー設定ファイル: $ENV_FILE"
else
    echo "警告: APIキー設定ファイルが見つかりません"
    echo "以下を $ENV_FILE に設定してください:"
    echo "  ANTHROPIC_API_KEY=your_key"
    echo "  TAVILY_API_KEY=your_key"
    echo "  OPENAI_API_KEY=your_key (オプション)"
    echo "  GITHUB_TOKEN=your_token (オプション)"
fi

echo ""
echo "==================================="
echo "セットアップ完了!"
echo "==================================="
echo ""
echo "使い方:"
echo "  source venv/bin/activate"
echo "  python main.py              # フルサイクル1回実行"
echo "  python main.py --status     # 現在の状態を表示"
echo "  python scheduler.py         # スケジューラー開始"
echo ""
echo "毎日自動実行の設定 (macOS):"
echo "  cp com.dna-commit.plist ~/Library/LaunchAgents/"
echo "  launchctl load ~/Library/LaunchAgents/com.dna-commit.plist"
echo ""
echo "停止:"
echo "  launchctl unload ~/Library/LaunchAgents/com.dna-commit.plist"
