"""直接コマンド実行用の手動トリガー。

外部イベントに応答するのではなく、メソッドを呼び出すことで手動で
アクティベートできるトリガーを提供します。以下の用途に有用です：
- ワークフローの対話的テスト
- アプリケーションの他の部分からのワークフロートリガー
- 手動制御が必要なコマンドラインインターフェース

ManualTriggerは自動的にイベントを生成せず、trigger()メソッドの
明示的な呼び出しを待ちます。
"""

from typing import Dict, Any, Optional

from ..core.interfaces import ControllableTrigger
from ..core.events import Event, EventBus


class ManualTrigger(ControllableTrigger):
    """手動でオンデマンドでアクティベートできるトリガー。

    自動トリガー（ファイルウォッチャーなど）とは異なり、このトリガーは
    trigger()メソッドで明示的に指示された場合のみイベントを生成します。
    これは以下の用途に有用です：

    - 対話的テストとデバッグ
    - コマンドラインインターフェースとの統合
    - プログラムによるワークフローアクティベーション
    - 手動オーバーライドシナリオ

    トリガーはイベントバスと設定への参照を保持し、リクエスト時に
    イベントをパブリッシュできるようにします。

    使用例:
        >>> trigger = ManualTrigger()
        >>> await trigger.start(event_bus, config)
        >>>
        >>> # 後で手動でトリガー
        >>> await trigger.trigger({"user_input": "test data"})

    属性:
        event_bus: イベントパブリッシュ用のEventBusインスタンス（start()中に設定）
        config: 設定辞書（start()中に設定）
        _running: トリガーが現在アクティブかどうか
    """

    def __init__(self) -> None:
        """手動トリガーを初期化。

        使用前に開始する必要がある非アクティブトリガーを作成します。
        """
        self.event_bus: Optional[EventBus] = None
        self.config: Optional[Dict[str, Any]] = None
        self._running = False

    async def start(self, event_bus: EventBus, config: Dict[str, Any]) -> None:
        """参照を保存して手動トリガーを開始。

        他のトリガーとは異なり、これはバックグラウンド監視を開始しません。
        trigger()が呼ばれた時の後での使用のためにイベントバスと設定を
        保存するだけです。

        Args:
            event_bus: イベントをパブリッシュするEventBusインスタンス
            config: トリガーの設定辞書

        設定キー:
            event_type (str): パブリッシュイベントのタイプ（デフォルト: "manual"）

        注意:
            手動トリガーはバックグラウンドで継続的に実行されないため、
            このメソッドはすぐに返します。
        """
        self.event_bus = event_bus
        self.config = config
        self._running = True

    async def stop(self) -> None:
        """手動トリガーを停止し、参照をクリーンアップ。

        トリガーを停止とマークし、保存された参照をクリアします。
        これが呼ばれた後、start()が再び呼ばれるまでtrigger()メソッドは
        動作しません。
        """
        self._running = False
        self.event_bus = None
        self.config = None

    async def trigger(self, data: Optional[Dict[str, Any]] = None) -> None:
        """手動でイベントをトリガー。

        提供されたデータでイベントを作成し、パブリッシュします。これは
        このトリガーを使用するワークフローをアクティベートするための
        メインメソッドです。

        Args:
            data: イベントに含めるオプションのデータ辞書。
                 Noneの場合は空の辞書が使用されます。

        例:
            >>> # データなしでトリガー
            >>> await trigger.trigger()
            >>>
            >>> # カスタムデータでトリガー
            >>> await trigger.trigger({
            ...     "command": "process_files",
            ...     "priority": "high",
            ...     "user_id": "admin"
            ... })

        注意:
            トリガーが実行中でないか、適切に開始されていない場合、
            このメソッドは静かに返します。
        """
        if not self._running or not self.event_bus or self.config is None:
            return

        event = Event(
            id="",  # 自動生成
            type=self.config.get("event_type", "manual"),
            data=data or {},
            timestamp=None,  # 自動生成
            source="manual",
        )
        await self.event_bus.publish(event)
