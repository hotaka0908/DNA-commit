# DNA-commit: 自己進化システム

人間の介入なしに自動で進化するシステム。ネットから情報を収集し、AIが評価・コード生成・レビューを行い、良い情報をコミットし、悪い情報を削ぎ落とす。

## コンセプト

```
[情報収集] → [AI評価] → [コード生成] → [AIレビュー] → [自動コミット]
     ↑                                                      ↓
     └──────────────── [クリーンアップ] ←───────────────────┘
```

## 機能

### 1. 情報収集エージェント
- **Tavily API**: Web検索で最新のAI/機械学習情報を収集
- **GitHub API**: 関連リポジトリのトレンドを監視
- raspi-voice改善に役立つ情報を自動収集

### 2. 情報評価エージェント
- **Claude API**で情報の品質を自動評価
- 品質、関連性、新規性、実用性をスコアリング
- 閾値以上の情報のみを採用

### 3. コード生成エージェント
- 評価された情報を元にraspi-voiceの改善コードを自動生成
- 既存コードとの整合性を考慮

### 4. コードレビューエージェント
- セキュリティ、品質、互換性を自動チェック
- 問題がなければ自動承認

### 5. Gitコミッター
- レビュー通過したコードを自動コミット
- 専用ブランチで管理

### 6. クリーンアップエージェント
- 古い情報を自動削除
- 品質の低い情報を削除
- 却下された情報を削除

## セットアップ

```bash
# セットアップスクリプト実行
./setup.sh

# 仮想環境有効化
source venv/bin/activate
```

### APIキー設定

`~/.ai-necklace/.env` に以下を設定:

```
ANTHROPIC_API_KEY=your_anthropic_key
TAVILY_API_KEY=your_tavily_key
OPENAI_API_KEY=your_openai_key  # オプション
GITHUB_TOKEN=your_github_token  # オプション
```

## 使い方

### 手動実行

```bash
# フルサイクル1回実行
python main.py

# 個別ステップ実行
python main.py --collect    # 情報収集
python main.py --evaluate   # 評価
python main.py --generate   # コード生成
python main.py --review     # レビュー
python main.py --commit     # コミット
python main.py --cleanup    # クリーンアップ

# 状態確認
python main.py --status
```

### 自動実行（毎日）

#### macOS

```bash
# launchd設定
cp com.dna-commit.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.dna-commit.plist

# 停止
launchctl unload ~/Library/LaunchAgents/com.dna-commit.plist
```

#### Linux

```bash
# systemd設定
sudo cp dna-commit.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable dna-commit
sudo systemctl start dna-commit
```

### スケジューラー直接実行

```bash
# フルモード（毎日3:00実行）
python scheduler.py --mode full

# 分割モード（6:00収集、18:00コミット、2:00クリーンアップ）
python scheduler.py --mode split

# 即座に1回実行
python scheduler.py --mode once
```

## ディレクトリ構成

```
DNA-commit/
├── main.py              # メインオーケストレーター
├── scheduler.py         # 自動実行スケジューラー
├── config.py            # 設定
├── agents/              # エージェントモジュール
│   ├── collector.py     # 情報収集
│   ├── evaluator.py     # 情報評価
│   ├── generator.py     # コード生成
│   ├── committer.py     # Gitコミット
│   ├── reviewer.py      # コードレビュー
│   └── cleaner.py       # クリーンアップ
├── data/                # データ保存（.gitignore）
│   ├── knowledge/       # 知識ベース
│   └── generated_code/  # 生成コード
└── logs/                # ログ（.gitignore）
```

## 自己改善機能

- 評価統計から検索キーワードの改善を提案
- よくあるレビュー指摘事項を分析
- 採用率が低い場合は自動で戦略を調整

## 安全性

- セキュリティチェックを通過したコードのみコミット
- 専用ブランチで管理（メインブランチには直接コミットしない）
- ロールバック機能あり
- 手動承認が必要な場合は警告

## License

MIT
