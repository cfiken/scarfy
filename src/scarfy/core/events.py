"""Scarfyのイベントシステム。

このモジュールは、Scarfy自動化フレームワーク全体で使用される
コアイベント処理システムを提供します。構造化されたイベントを通じて
異なるコンポーネント間の通信を可能にする非同期イベントバスパターンを実装しています。

イベントシステムの構成要素：
- Event: 発生した出来事を表す不変データ構造
- EventBus: イベントを購読者にルーティングする中央メッセージディスパッチャー
"""

import asyncio
import copy
from typing import Any, Dict, Callable, Union, Optional
from dataclasses import dataclass
from datetime import datetime
import uuid


@dataclass
class Event:
    """Scarfyシステム内の単一イベントを表現します。

    イベントは、システム内で発生した出来事に関する情報を運ぶ
    不変データ構造です。ワークフローをトリガーし、異なるコンポーネント間で
    データを受け渡すために使用されます。

    属性:
        id: このイベントの一意識別子。未提供の場合は自動生成されます。
        type: 購読者へのルーティングに使用されるイベントタイプ識別子。
        data: このイベントに関連付けられた任意のデータペイロード。
        timestamp: このイベントが作成された時刻。未提供の場合は自動設定されます。
        source: このイベントを生成したコンポーネントの識別子。

    例:
        >>> event = Event(
        ...     id="",
        ...     type="file_changed",
        ...     data={"file_path": "/tmp/test.txt"},
        ...     timestamp=None,
        ...     source="file_watcher"
        ... )
        >>> print(event.id)  # 自動生成されたUUID
    """

    id: str
    type: str
    data: Dict[str, Any]
    timestamp: Optional[datetime]
    source: str

    def __post_init__(self) -> None:
        """オブジェクト作成後に自動生成フィールドを初期化します。

        提供されなかった場合のidとtimestampのデフォルト値を設定します。
        これにより、呼び出し元は自動生成のために空文字列/Noneを渡すことができます。
        データはイミュータブルにするためにディープコピーされます。
        """
        if not self.id:
            self.id = str(uuid.uuid4())
        if self.timestamp is None:
            self.timestamp = datetime.now()
        # イミュータブルデータ構造を保証するためにdataをディープコピー
        object.__setattr__(self, "data", copy.deepcopy(self.data))


class EventBus:
    """コンポーネント間の疎結合通信のための非同期イベントバス。

    EventBusは以下のパブリッシュ・サブスクライブパターンを実装します:
    - パブリッシャーは誰が処理するかを知らずにイベントを送信
    - サブスクライバーは特定のイベントタイプに対してコールバックを登録
    - バスは一致するすべてのサブスクライバーにイベントを非同期でルーティング

    この設計により、システムは高度にモジュール化されます - 新しいトリガー、
    エージェント、出力を既存のコードを変更せずに追加できます。

    例:
        >>> bus = EventBus()
        >>>
        >>> # ファイル変更イベントに購読
        >>> async def handle_file_change(event):
        ...     print(f"ファイルが変更されました: {event.data['file_path']}")
        >>>
        >>> bus.subscribe("file_changed", handle_file_change)
        >>>
        >>> # 処理開始（バックグラウンドタスクで）
        >>> asyncio.create_task(bus.start())
        >>>
        >>> # イベントをパブリッシュ
        >>> event = Event(id="", type="file_changed",
        ...               data={"file_path": "/tmp/test.txt"},
        ...               timestamp=None, source="watcher")
        >>> await bus.publish(event)
    """

    def __init__(self) -> None:
        """新しいEventBusインスタンスを初期化します。

        イベントのキューイングと購読者の追跡のための内部データ構造を作成します。
        バスは停止状態で作成されます。
        """
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._subscribers: Dict[str, list] = {}
        self._running = False

    async def publish(self, event: Event) -> None:
        """処理のためにイベントをバスにパブリッシュします。

        イベントは非同期処理のためにキューに入れられます。このメソッドは
        購読者がイベントを処理するのを待たずに即座に戻ります。

        Args:
            event: パブリッシュするEventインスタンス。

        例:
            >>> event = Event(id="", type="test", data={},
            ...               timestamp=None, source="test")
            >>> await bus.publish(event)
        """
        await self._queue.put(event)

    def subscribe(
        self, event_type: str, callback: Callable[[Event], Union[None, Any]]
    ) -> None:
        """特定のタイプのイベントを購読します。

        指定されたタイプのイベントがパブリッシュされるたびに呼び出される
        コールバック関数を登録します。コールバックは通常の関数でも
        コルーチンでも可能で、EventBusが自動的に両方を処理します。

        Args:
            event_type: 購読するイベントタイプ（Event.typeと一致）。
            callback: 一致するイベントがパブリッシュされたときに呼び出す関数。
                     同期でも非同期でも可能。

        例:
            >>> def sync_handler(event):
            ...     print(f"イベントを受信: {event.type}")
            >>>
            >>> async def async_handler(event):
            ...     await some_async_operation(event.data)
            >>>
            >>> bus.subscribe("test_event", sync_handler)
            >>> bus.subscribe("test_event", async_handler)
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    async def start(self) -> None:
        """イベント処理ループを開始します。

        これは無期限に実行され、キューからイベントを処理して
        購読者にルーティングします。通常はバックグラウンドタスクとして実行されます。

        ループはstop()が呼ばれるまで継続します。イベントは実行フラグの定期チェックを
        可能にするため1秒のタイムアウトで処理されます。

        例:
            >>> # バックグラウンドで処理開始
            >>> processing_task = asyncio.create_task(bus.start())
            >>>
            >>> # 他の作業を実行...
            >>>
            >>> # 処理停止
            >>> bus.stop()
            >>> await processing_task
        """
        self._running = True
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self._process_event(event)
            except asyncio.TimeoutError:
                # Timeout allows us to check _running flag periodically
                continue
            except Exception:
                # Log error in production code, but continue processing
                continue

    def stop(self) -> None:
        """イベント処理ループを停止します。

        内部の実行フラグをFalseに設定し、start()の処理ループが
        次の反復で終了するようにします。

        これはフラグを設定するだけの同期操作で、処理ループが
        実際に停止するまで待機しません。
        """
        self._running = False

    async def _process_event(self, event: Event) -> None:
        """単一のイベントを購読者にルーティングして処理します。

        実際のイベントディスパッチを処理する内部メソッドです。イベントタイプの
        すべての購読者を見つけて、それらを並行して呼び出します。

        同期と非同期の両方のコールバックがサポートされています。同期コールバックは
        イベントループのブロックを避けるためにasyncio.to_thread()でラップされます。

        個々のコールバックの例外はキャッチされ無視されるため、
        一つの失敗した購読者が他に影響することを防ぎます。

        Args:
            event: 処理するEvent。
        """
        subscribers = self._subscribers.get(event.type, [])

        tasks = []
        for callback in subscribers:
            if asyncio.iscoroutinefunction(callback):
                tasks.append(callback(event))
            else:
                # Run sync callbacks in thread pool to avoid blocking
                tasks.append(asyncio.create_task(asyncio.to_thread(callback, event)))

        if tasks:
            # Gather with return_exceptions=True to prevent one failure from canceling others
            await asyncio.gather(*tasks, return_exceptions=True)
