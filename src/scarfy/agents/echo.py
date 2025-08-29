"""テストとデバッグ用のシンプルエコーエージェント。

イベントデータをメタデータと共にそのままエコーし返す基本的な
エージェント実装を提供します。以下の用途に有用です：
- ワークフロー設定のテスト
- イベントフローのデバッグ
- エージェントの仕組みの学習
- 開発中のプレースホルダー

EchoAgentは複雑な処理を行わず、入力イベントデータを
構造化されたレスポンスにパッケージ化するだけです。
"""

from typing import Dict, Any
from ..core.interfaces import Agent
from ..core.events import Event


class EchoAgent(Agent):
    """イベントデータをメタデータと共にエコーし返すシンプルエージェント。

    このエージェントは主にテストとデバッグに有用です。任意のイベントを
    受け取り、元のイベントデータと処理メタデータを含む構造化された
    レスポンスを返します。

    このエージェントはステートレスかつスレッドセーフで、複数のイベントを
    同時に処理するのに適しています。

    設定オプション:
        message (str): レスポンスに含めるカスタムメッセージ（デフォルト: "イベントが処理されました"）
        include_config (bool): レスポンスに設定を含めるか（デフォルト: False）

    設定例:
        {
            "type": "echo",
            "message": "ファイル処理が完了しました",
            "include_config": True
        }

    出力例:
        {
            "original_event": {
                "id": "abc-123",
                "type": "file_changed",
                "source": "file_watcher",
                "timestamp": "2024-01-01T12:00:00",
                "data": {"file_path": "/tmp/test.txt"}
            },
            "agent": "EchoAgent",
            "message": "イベントが処理されました",
            "processing_time": "2024-01-01T12:00:01"
        }
    """

    async def process(self, event: Event, config: Dict[str, Any]) -> Dict[str, Any]:
        """イベントをメタデータと共にエコーして処理。

        入力イベントを受け取り、元のイベントデータと処理メタデータを
        含む構造化されたレスポンスを返します。ワークフローのテストや
        イベント構造の理解に便利です。

        Args:
            event: 処理するEventオブジェクト
            config: このエージェントの設定辞書

        Returns:
            元のイベントデータとメタデータを含む辞書:
            - original_event: 完全なイベントデータ (id, type, source, timestamp, data)
            - agent: 処理したエージェントの名前
            - message: 処理メッセージ（設定からまたはデフォルト）
            - processing_time: 処理が実行された時刻のISOタイムスタンプ
            - config: エージェント設定（include_configがTrueの場合）

        例:
            >>> event = Event(id="123", type="test", data={"key": "value"},
            ...              timestamp=datetime.now(), source="test")
            >>> config = {"message": "カスタムメッセージ"}
            >>> result = await agent.process(event, config)
            >>> print(result["message"])
            "カスタムメッセージ"
        """
        from datetime import datetime

        result = {
            "original_event": {
                "id": event.id,
                "type": event.type,
                "source": event.source,
                "timestamp": event.timestamp.isoformat() if event.timestamp else None,
                "data": event.data,
            },
            "agent": "EchoAgent",
            "message": config.get("message", "イベントが処理されました"),
            "processing_time": datetime.now().isoformat(),
        }

        # オプションでエージェント設定をレスポンスに含める
        if config.get("include_config", False):
            result["config"] = config

        return result
