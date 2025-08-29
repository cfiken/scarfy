"""ファイルシステム監視トリガー。

watchdogライブラリを使用してファイルシステムの変更を監視するトリガーを
提供します。指定されたディレクトリ内でのファイルの作成、変更、削除、
移動を監視できます。

FileWatcherTriggerはファイルが変更された際にイベントをパブリッシュし、
自動化ワークフローがファイルシステムの活動に応答できるようにします。
"""

import asyncio
import concurrent.futures
import fnmatch
from pathlib import Path
from watchdog.observers import Observer
from watchdog.observers.api import BaseObserver
from watchdog.events import FileSystemEventHandler
from typing import Dict, Any, Optional
from watchdog.events import FileSystemEvent
import time

from ..core.interfaces import Trigger
from ..core.events import Event, EventBus
from ..utils.logger import get_logger


class FileChangeHandler(FileSystemEventHandler):
    """ファイルシステム変更用のカスタムイベントハンドラー。

    このハンドラーはwatchdog Observerからファイルシステムイベントを受信し、
    イベントバスにパブリッシュされるScarfy Eventオブジェクトに変換します。

    デバウンス機能により、同じファイルの短時間での複数イベントを統合し、
    一時ファイルのフィルタリングでエディタの中間ファイルを除外します。

    属性:
        event_bus: イベントをパブリッシュするEventBusインスタンス
        config: ワークフローからの設定辞書
        loop: タスクをスケジュールするasyncioイベントループ
        pending_timers: デバウンス用の保留中タイマー辞書
        debounce_delay: デバウンス遅延時間（秒）
    """

    def __init__(
        self,
        event_bus: EventBus,
        config: Dict[str, Any],
        loop: asyncio.AbstractEventLoop,
    ):
        """ファイル変更ハンドラーを初期化。

        Args:
            event_bus: イベントをパブリッシュするEventBusインスタンス
            config: event_typeとその他の設定を含む設定辞書
            loop: タスクをスケジュールするAsyncioイベントループ
        """
        super().__init__()
        self.event_bus = event_bus
        self.config = config
        self.loop = loop
        self.filename_patterns = config.get("filename_patterns", [])

        # デバウンス機能
        self.pending_timers: Dict[str, concurrent.futures.Future] = (
            {}
        )  # file_path -> timer_task
        self.last_event_times: Dict[str, float] = (
            {}
        )  # file_path -> last_event_timestamp
        self.timer_ids: Dict[str, int] = {}  # file_path -> timer_id (ユニークID用)
        self._next_timer_id: int = 0  # タイマーIDのカウンター
        self.debounce_delay = config.get("debounce_delay", 1.0)  # デフォルト1秒

        # 監視対象イベントタイプの設定
        watch_events = config.get("watch_events", ["created", "modified"])
        self.watch_created = "created" in watch_events
        self.watch_modified = "modified" in watch_events

        # 一時ファイル除外パターン
        default_temp_patterns = [
            "*.tmp",
            "*.temp",
            "~*",
            ".#*",
            "#*#",
            ".DS_Store",
            "Thumbs.db",
            "*.swp",
            "*.swo",
            "*~",
            "*.bak",
            "*.orig",
        ]
        self.temp_patterns = config.get("ignore_temp_files", default_temp_patterns)

    def _matches_filename_patterns(self, file_path: str) -> bool:
        """ファイルパスが設定されたパターンにマッチするかチェック。

        Args:
            file_path: チェックするファイルパス

        Returns:
            パターンが未設定の場合、またはいずれかのパターンにマッチした場合True
        """
        # パターンが設定されていない場合は全てのファイルを対象
        if not self.filename_patterns:
            return True

        filename = Path(file_path).name
        return any(
            fnmatch.fnmatch(filename, pattern) for pattern in self.filename_patterns
        )

    def _is_temp_file(self, file_path: str) -> bool:
        """ファイルが一時ファイルかどうかをチェック。

        Args:
            file_path: チェックするファイルパス

        Returns:
            一時ファイルの場合True
        """
        filename = Path(file_path).name
        return any(fnmatch.fnmatch(filename, pattern) for pattern in self.temp_patterns)

    def _should_process_file(self, file_path: str) -> bool:
        """ファイルを処理対象とするかどうかを総合判定。

        Args:
            file_path: チェックするファイルパス

        Returns:
            処理対象の場合True
        """
        # 一時ファイルは除外
        if self._is_temp_file(file_path):
            return False

        # ファイル名パターンチェック
        return self._matches_filename_patterns(file_path)

    def _schedule_debounced_event(self, action: str, file_path: str) -> None:
        """タイムスタンプベースのデバウンス機能付きでイベントをスケジュール。

        各タイマーにユニークIDを付与し、実行時に最新性をチェックして
        確実に重複を防止します。

        Args:
            action: ファイルシステムアクションの種類
            file_path: 影響を受けたファイルのフルパス
        """
        current_time = time.time()

        # 最新のイベント時刻を記録
        self.last_event_times[file_path] = current_time

        # ユニークなタイマーIDを生成
        timer_id = self._next_timer_id
        self._next_timer_id += 1
        self.timer_ids[file_path] = timer_id

        print(
            f"⏰ [FileWatcherTrigger] デバウンスタイマー作成: {file_path} (ID: {timer_id}, action: {action})"
        )

        # 既存のタイマーをキャンセル（ベストエフォート）
        if file_path in self.pending_timers:
            old_timer = self.pending_timers[file_path]
            old_timer.cancel()

        # 新しいタイマーを作成してスケジュール
        timer_task = asyncio.run_coroutine_threadsafe(
            self._delayed_publish_with_timestamp_check(
                action, file_path, timer_id, current_time
            ),
            self.loop,
        )
        self.pending_timers[file_path] = timer_task

    async def _delayed_publish_with_timestamp_check(
        self, action: str, file_path: str, timer_id: int, scheduled_time: float
    ) -> None:
        """タイムスタンプベースのチェック付きデバウンス実行。

        タイマー実行時に二重チェック（ID + 時刻）を行い、
        確実に最新タイマーのみがイベントを発行します。

        Args:
            action: ファイルシステムアクションの種類
            file_path: 影響を受けたファイルのフルパス
            timer_id: このタイマーのユニークID
            scheduled_time: このタイマーがスケジュールされた時刻
        """
        try:
            # デバウンス待機
            await asyncio.sleep(self.debounce_delay)

            # 条件チェック1: 自分が最新のタイマーか？
            current_timer_id = self.timer_ids.get(file_path)
            if current_timer_id != timer_id:
                print(
                    f"⏰ [FileWatcherTrigger] 古いタイマーのため実行スキップ: {file_path} (ID: {timer_id}, 現在: {current_timer_id})"
                )
                return

            # 条件チェック2: 十分な時間が経過したか？
            if file_path not in self.last_event_times:
                print(
                    f"⏰ [FileWatcherTrigger] イベント時刻が削除されているため実行スキップ: {file_path} (ID: {timer_id})"
                )
                return

            time_since_last_event = time.time() - self.last_event_times[file_path]
            if time_since_last_event < self.debounce_delay:
                print(
                    f"⏰ [FileWatcherTrigger] まだ新しいイベントがあるため実行スキップ: {file_path} (ID: {timer_id}, 経過時間: {time_since_last_event:.2f}s)"
                )
                return

            # 全ての条件を満たした場合のみイベント発行
            print(
                f"🚀 [FileWatcherTrigger] デバウンス条件クリア、イベント発行: {file_path} (ID: {timer_id})"
            )
            await self._publish_event(action, file_path)

        except asyncio.CancelledError:
            print(
                f"⏰ [FileWatcherTrigger] デバウンス: {file_path} のタイマー(ID: {timer_id})がキャンセルされました"
            )
            raise
        finally:
            # クリーンアップ（自分が最新の場合のみ）
            if self.timer_ids.get(file_path) == timer_id:
                if file_path in self.pending_timers:
                    del self.pending_timers[file_path]
                if file_path in self.last_event_times:
                    del self.last_event_times[file_path]
                if file_path in self.timer_ids:
                    del self.timer_ids[file_path]
                print(
                    f"🧹 [FileWatcherTrigger] デバウンスデータクリーンアップ: {file_path} (ID: {timer_id})"
                )

    def on_created(self, event: FileSystemEvent) -> None:
        """ファイル作成イベントを処理。

        監視ディレクトリに新しいファイルが作成された際にwatchdogから呼ばれます。
        ディレクトリではなく、通常のファイルのみを処理し、デバウンス機能を適用します。

        Args:
            event: ファイルパスとメタデータを含むwatchdogからのFileSystemEvent
        """
        if not event.is_directory and self.watch_created:
            src_path = str(event.src_path)  # bytes to str conversion
            if self._should_process_file(src_path):
                logger = get_logger(__name__)
                logger.info("ファイル作成検出: %s", src_path)
                self._schedule_debounced_event("file_created", src_path)

    def on_modified(self, event: FileSystemEvent) -> None:
        """ファイル変更イベントを処理。

        監視ディレクトリ内の既存ファイルが変更された際にwatchdogから呼ばれます。
        ディレクトリではなく、通常のファイルのみを処理し、デバウンス機能を適用します。

        Args:
            event: ファイルパスとメタデータを含むwatchdogからのFileSystemEvent
        """
        if not event.is_directory and self.watch_modified:
            src_path = str(event.src_path)  # bytes to str conversion
            if self._should_process_file(src_path):
                logger = get_logger(__name__)
                logger.info("ファイル変更検出: %s", src_path)
                self._schedule_debounced_event("file_modified", src_path)

    async def _publish_event(self, action: str, file_path: str) -> None:
        """ファイルシステムイベントをScarfy Eventに変換してパブリッシュ。

        ファイル情報を含むScarfy Eventオブジェクトを作成し、ワークフローでの
        処理のためにイベントバスにパブリッシュします。

        Args:
            action: ファイルシステムアクションの種類（"file_created", "file_modified"など）
            file_path: 影響を受けたファイルのフルパス
        """
        event = Event(
            id="",  # Auto-generated
            type=self.config.get("event_type", "file_change"),
            data={
                "action": action,
                "file_path": file_path,
                "file_name": Path(file_path).name,
                "file_extension": Path(file_path).suffix,
                "parent_directory": str(Path(file_path).parent),
            },
            timestamp=None,  # Auto-generated
            source="file_watcher",
        )
        logger = get_logger(__name__)
        logger.debug("デバウンス完了、イベント発行: %s", event.data)
        await self.event_bus.publish(event)

    async def cleanup(self) -> None:
        """ハンドラーのクリーンアップ。

        保留中のタイマーをすべてキャンセルし、デバウンス関連の
        全ての追跡データをクリアします。
        """
        # 保留中のタイマーをキャンセル
        for timer_task in list(self.pending_timers.values()):
            timer_task.cancel()

        # 全ての追跡データをクリア
        self.pending_timers.clear()
        self.last_event_times.clear()
        self.timer_ids.clear()

        print(
            "🧹 [FileWatcherTrigger] デバウンスタイマーと追跡データをクリーンアップしました"
        )


class FileWatcherTrigger(Trigger):
    """ファイルシステム変更を監視するトリガー。

    このトリガーはwatchdogライブラリを使用してディレクトリ（およびオプションで
    そのサブディレクトリ）のファイルシステム変更を監視します。ファイルが作成、
    変更、削除、移動された際にイベントバスにイベントをパブリッシュします。

    v2.0の改善点:
    - デバウンス機能: 同じファイルの連続イベントを統合
    - 一時ファイル除外: エディタの中間ファイルを自動除外
    - 監視イベント選択: created/modifiedを個別に有効/無効化可能

    設定オプション:
        path: 監視するディレクトリパス（デフォルト: カレントディレクトリ）
        recursive: サブディレクトリも監視するか（デフォルト: False）
        event_type: パブリッシュするイベントタイプ（デフォルト: "file_change"）
        filename_patterns: 監視するファイル名パターンのリスト（任意、未設定時は全ファイル）
        debounce_delay: デバウンス遅延時間（秒、デフォルト: 1.0）
        watch_events: 監視するイベントタイプ（デフォルト: ['created', 'modified']）
        ignore_temp_files: 除外する一時ファイルパターン（デフォルト: 標準的な一時ファイル）

    設定例:
        {
            "type": "file_watcher",
            "path": "/path/to/watch",
            "recursive": True,
            "event_type": "file_changed",
            "filename_patterns": ["*.md", "*.txt"],
            "debounce_delay": 2.0,
            "watch_events": ["modified"],
            "ignore_temp_files": ["*.tmp", "~*", ".DS_Store"]
        }

    属性:
        observer: ファイルシステム監視用のWatchdog Observerインスタンス
        handler: イベント処理用のFileChangeHandlerインスタンス
    """

    def __init__(self) -> None:
        """ファイルウォッチャートリガーを初期化。

        内部状態を作成しますが、start()が呼ばれるまで監視は開始しません。
        """
        self.observer: Optional[BaseObserver] = None
        self.handler: Optional[FileChangeHandler] = None

    async def start(self, event_bus: EventBus, config: Dict[str, Any]) -> None:
        """ファイルシステムの変更監視を開始。

        指定されたディレクトリを監視するwatchdog Observerを設定し、
        ファイル変更時のイベントパブリッシュを開始します。

        Args:
            event_bus: イベントをパブリッシュするEventBusインスタンス
            config: 監視設定を含む設定辞書

        設定キー:
            path (str): 監視するディレクトリ（デフォルト: カレントディレクトリ）
            recursive (bool): サブディレクトリも監視（デフォルト: False）
            event_type (str): パブリッシュイベントのタイプ（デフォルト: "file_change"）

        Raises:
            OSError: 指定されたパスが存在しないかアクセスできない場合
        """
        watch_path = config.get("path", ".")

        # パスの存在確認
        if not Path(watch_path).exists():
            raise OSError(f"監視パスが存在しません: {watch_path}")

        print(
            f"📂 [FileWatcherTrigger] 監視開始: {watch_path} (recursive={config.get('recursive', False)})"
        )

        try:
            # ハンドラーに渡すための現在のイベントループを取得
            current_loop = asyncio.get_running_loop()
            self.handler = FileChangeHandler(event_bus, config, current_loop)
            self.observer = Observer()
            self.observer.schedule(
                self.handler, watch_path, recursive=config.get("recursive", False)
            )
            self.observer.start()
            print(f"✅ [FileWatcherTrigger] 監視開始成功: {watch_path}")
        except Exception as e:
            print(f"❌ [FileWatcherTrigger] 監視開始エラー: {watch_path} - {e}")
            raise

    async def stop(self) -> None:
        """ファイルシステム変更の監視を停止し、リソースをクリーンアップ。

        watchdog Observerを停止し、デバウンスタイマーをクリーンアップして、
        残りのイベント処理が完了するのを待ちます。
        """
        # デバウンスタイマーのクリーンアップ
        if self.handler:
            await self.handler.cleanup()

        # Observer の停止
        if self.observer and self.observer.is_alive():
            self.observer.stop()
            self.observer.join()

        self.observer = None
        self.handler = None
        print("🛑 [FileWatcherTrigger] ファイル監視を停止しました")
