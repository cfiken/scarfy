"""Scarfyコンポーネントの基底インターフェース。

このモジュールは、すべてのScarfyコンポーネントが実装する必要がある
コアインターフェースを定義します。フレームワークはプラグインアーキテクチャに
従っており、これらのインターフェースの異なる実装を組み合わせて
カスタム自動化ワークフローを作成できます。

3つの主要コンポーネントタイプ：
- Trigger: イベントを検知してイベントバスにパブリッシュ
- Agent: イベントを処理して結果を生成
- Output: エージェントからの結果を処理（ログ、通知など）
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from .events import Event, EventBus


class Trigger(ABC):
    """イベントトリガーの基底インターフェース。

    トリガーは外部イベントを検知してイベントバスにパブリッシュする責任があります。
    バックグラウンドで継続的に実行され、特定のタイプのイベント（ファイル変更、
    スケジュール時刻、手動コマンドなど）を監視します。

    各トリガー実装は以下を行う必要があります：
    1. start()が呼ばれたときに監視を開始
    2. イベントが発生したときにEventオブジェクトをイベントバスにパブリッシュ
    3. stop()が呼ばれたときにリソースをクリーンアップ

    実装例：
        >>> class MyTrigger(Trigger):
        ...     async def start(self, event_bus, config):
        ...         # イベント監視を開始
        ...         while self._running:
        ...             # 何らかの方法でイベントを検知
        ...             event = Event(id="", type="my_event",
        ...                          data={}, timestamp=None, source="my_trigger")
        ...             await event_bus.publish(event)
        ...
        ...     async def stop(self):
        ...         self._running = False
    """

    @abstractmethod
    async def start(self, event_bus: EventBus, config: Dict[str, Any]) -> None:
        """トリガーを開始してイベントの監視を始めます。

        このメソッドはイベントを検知するために必要なバックグラウンドプロセスを
        開始する必要があります。通常、stop()が呼ばれるまで無期限に実行されます。

        Args:
            event_bus: イベントをパブリッシュするEventBusインスタンス。
            config: このトリガー固有の設定辞書。
                   内容はトリガー実装に依存します。

        ファイルウォッチャーの設定例：
            {
                "path": "/path/to/watch",
                "recursive": true,
                "event_type": "file_changed"
            }
        """
        pass

    @abstractmethod
    async def stop(self) -> None:
        """トリガーを停止してリソースをクリーンアップします。

        このメソッドはバックグラウンド監視を停止し、ファイルハンドル、
        ネットワーク接続などのリソースをクリーンアップする必要があります。

        このメソッドが呼ばれた後、トリガーはイベントバスに
        これ以上イベントをパブリッシュしてはいけません。
        """
        pass


class ControllableTrigger(Trigger):
    """プログラムから制御可能なトリガーのインターフェース。

    通常のTriggerとは異なり、trigger()メソッドを提供して
    プログラムから直接イベントを発火できるトリガーです。
    手動実行、テスト、CLI統合などに使用されます。
    """

    @abstractmethod
    async def trigger(self, data: Optional[Dict[str, Any]] = None) -> None:
        """手動でイベントをトリガーします。

        Args:
            data: イベントに含めるオプションのデータ辞書。
                 Noneの場合は空の辞書が使用されます。
        """
        pass


class Agent(ABC):
    """イベント処理エージェントの基底インターフェース。

    エージェントは自動化システムの「頭脳」です。トリガーからイベントを受け取り、
    それらを処理して結果を生成します。これには以下が含まれる可能性があります：
    - 外部APIやサービスの呼び出し
    - ファイルやデータの処理
    - イベント内容に基づく意思決定
    - レポートや要約の生成

    エージェントは複数のイベントを並行処理する可能性があるため、
    ステートレスでスレッドセーフである必要があります。

    実装例：
        >>> class FileProcessorAgent(Agent):
        ...     async def process(self, event, config):
        ...         file_path = event.data.get('file_path')
        ...         # 何らかの方法でファイルを処理
        ...         return {
        ...             'processed_file': file_path,
        ...             'result': 'success',
        ...             'summary': 'ファイルが正常に処理されました'
        ...         }
    """

    @abstractmethod
    async def process(self, event: Event, config: Dict[str, Any]) -> Dict[str, Any]:
        """イベントを処理して結果を返します。

        これはエージェントのロジックが存在するメインメソッドです。イベントを受け取り、
        そのイベントを処理した結果を含む辞書を返す必要があります。

        Args:
            event: 処理するEventオブジェクト。type、data、timestampなどを含みます。
            config: このエージェント固有の設定辞書。
                   内容はエージェント実装に依存します。

        Returns:
            処理結果を含む辞書。構造はエージェント実装に依存しますが、
            JSON直列化可能である必要があります。

        例：
            >>> event = Event(id="123", type="file_changed",
            ...              data={"file_path": "/tmp/test.txt"},
            ...              timestamp=datetime.now(), source="watcher")
            >>> result = await agent.process(event, {"timeout": 30})
            >>> print(result)
            {'status': 'success', 'message': 'ファイルが処理されました', 'lines': 42}
        """
        pass


class Output(ABC):
    """出力ハンドラーの基底インターフェース。

    出力は、エージェントによって生成された結果に対して何かを行う責任があります。
    これには以下が含まれる可能性があります：
    - ファイルやデータベースへのログ出力
    - 通知の送信（メール、Slackなど）
    - 外部システムの更新
    - 他のワークフローのトリガー

    出力は可能な限りエラーを適切に処理し、ワークフローの失敗を
    引き起こさないようにする必要があります。

    実装例：
        >>> class SlackOutput(Output):
        ...     async def send(self, data, config):
        ...         channel = config.get('channel', '#general')
        ...         message = f"ワークフロー結果: {data.get('status')}"
        ...         # Slack APIに送信
        ...         await self.slack_client.send_message(channel, message)
    """

    @abstractmethod
    async def send(self, data: Dict[str, Any], config: Dict[str, Any]) -> None:
        """出力データを送信/処理します。

        このメソッドはエージェントからの結果を受け取り、出力の目的
        （ログ、通知など）に従ってそれらを処理します。

        Args:
            data: エージェントからの結果を含む辞書。
                 構造はそれを生成したエージェントに依存します。
            config: この出力固有の設定辞書。
                   内容は出力実装に依存します。

        例：
            >>> data = {
            ...     'status': 'success',
            ...     'message': 'ファイルが処理されました',
            ...     'timestamp': '2024-01-01T12:00:00'
            ... }
            >>> config = {
            ...     'file_path': '/var/log/scarfy.log',
            ...     'format': 'json'
            ... }
            >>> await output.send(data, config)
        """
        pass
