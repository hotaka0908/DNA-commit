"""
情報収集エージェント

Tavily APIとGitHub APIを使用してネットから情報を収集
"""

import os
import json
import hashlib
from datetime import datetime
from typing import Optional
import logging

from tavily import TavilyClient

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

logger = logging.getLogger(__name__)


class InformationCollector:
    """情報収集エージェント"""

    def __init__(self):
        self.tavily = TavilyClient(api_key=Config.get_tavily_api_key())
        self.collected_data_path = os.path.join(Config.DATA_DIR, "collected_info.json")
        self._load_existing_data()

    def _load_existing_data(self):
        """既存の収集データを読み込む"""
        if os.path.exists(self.collected_data_path):
            with open(self.collected_data_path, "r", encoding="utf-8") as f:
                self.collected_data = json.load(f)
        else:
            self.collected_data = {"items": [], "last_updated": None}

    def _save_data(self):
        """収集データを保存"""
        self.collected_data["last_updated"] = datetime.now().isoformat()
        with open(self.collected_data_path, "w", encoding="utf-8") as f:
            json.dump(self.collected_data, f, ensure_ascii=False, indent=2)

    def _generate_id(self, content: str) -> str:
        """コンテンツからユニークIDを生成"""
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def _is_duplicate(self, url: str) -> bool:
        """重複チェック"""
        existing_urls = [item.get("url") for item in self.collected_data["items"]]
        return url in existing_urls

    def search_web(self, query: str, max_results: int = 5) -> list[dict]:
        """Tavily APIでWeb検索"""
        try:
            response = self.tavily.search(
                query=query,
                search_depth="advanced",
                max_results=max_results,
                include_answer=True,
                include_raw_content=True,
            )

            results = []
            for item in response.get("results", []):
                if self._is_duplicate(item.get("url", "")):
                    continue

                result = {
                    "id": self._generate_id(item.get("url", "")),
                    "type": "web",
                    "query": query,
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": item.get("content", ""),
                    "raw_content": item.get("raw_content", "")[:5000] if item.get("raw_content") else "",
                    "score": item.get("score", 0),
                    "collected_at": datetime.now().isoformat(),
                    "status": "pending_evaluation",
                }
                results.append(result)

            return results

        except Exception as e:
            logger.error(f"Tavily search error: {e}")
            return []

    def search_github(self, query: str, max_results: int = 5) -> list[dict]:
        """GitHub APIでリポジトリ検索"""
        import requests

        try:
            headers = {}
            token = Config.get_github_token()
            if token:
                headers["Authorization"] = f"token {token}"

            # リポジトリ検索
            url = "https://api.github.com/search/repositories"
            params = {
                "q": query,
                "sort": "updated",
                "order": "desc",
                "per_page": max_results,
            }

            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get("items", []):
                repo_url = item.get("html_url", "")
                if self._is_duplicate(repo_url):
                    continue

                result = {
                    "id": self._generate_id(repo_url),
                    "type": "github_repo",
                    "query": query,
                    "title": item.get("full_name", ""),
                    "url": repo_url,
                    "description": item.get("description", "") or "",
                    "stars": item.get("stargazers_count", 0),
                    "language": item.get("language", ""),
                    "updated_at": item.get("updated_at", ""),
                    "topics": item.get("topics", []),
                    "collected_at": datetime.now().isoformat(),
                    "status": "pending_evaluation",
                }
                results.append(result)

            return results

        except Exception as e:
            logger.error(f"GitHub search error: {e}")
            return []

    def collect_all(self) -> dict:
        """全てのソースから情報を収集"""
        logger.info("=== 情報収集開始 ===")
        new_items = []

        # Web検索
        for topic in Config.SEARCH_TOPICS:
            logger.info(f"Web検索: {topic}")
            results = self.search_web(topic, max_results=3)
            new_items.extend(results)
            logger.info(f"  -> {len(results)}件の新規情報")

        # GitHub検索
        for topic in Config.GITHUB_TOPICS:
            logger.info(f"GitHub検索: {topic}")
            results = self.search_github(topic, max_results=3)
            new_items.extend(results)
            logger.info(f"  -> {len(results)}件の新規情報")

        # データに追加
        self.collected_data["items"].extend(new_items)
        self._save_data()

        logger.info(f"=== 収集完了: 計{len(new_items)}件の新規情報 ===")

        return {
            "new_items_count": len(new_items),
            "total_items_count": len(self.collected_data["items"]),
            "new_items": new_items,
        }

    def get_pending_items(self) -> list[dict]:
        """評価待ちのアイテムを取得"""
        return [
            item for item in self.collected_data["items"]
            if item.get("status") == "pending_evaluation"
        ]

    def update_item_status(self, item_id: str, status: str, evaluation: Optional[dict] = None):
        """アイテムのステータスを更新"""
        for item in self.collected_data["items"]:
            if item.get("id") == item_id:
                item["status"] = status
                if evaluation:
                    item["evaluation"] = evaluation
                break
        self._save_data()


if __name__ == "__main__":
    # テスト実行
    logging.basicConfig(level=logging.INFO)
    collector = InformationCollector()
    result = collector.collect_all()
    print(f"収集結果: {result['new_items_count']}件")
