"""Eventシステムのテストモジュール。

EventクラスとEventBusクラスの機能を検証します。
"""

import pytest
import asyncio
from datetime import datetime
from src.scarfy.core.events import Event, EventBus


class TestEvent:
    """Eventクラスのテストケース。"""

    def test_event_creation_with_all_fields(self):
        """全てのフィールドを指定したEventの作成をテスト。"""
        event_id = "test-123"
        event_type = "file_changed"
        data = {"file_path": "/tmp/test.txt"}
        timestamp = datetime.now()
        source = "file_watcher"

        event = Event(
            id=event_id, type=event_type, data=data, timestamp=timestamp, source=source
        )

        assert event.id == event_id
        assert event.type == event_type
        assert event.data == data
        assert event.timestamp == timestamp
        assert event.source == source

    def test_event_auto_generates_id_when_empty(self):
        """IDが空の場合に自動生成されることをテスト。"""
        event = Event(
            id="", type="test", data={}, timestamp=datetime.now(), source="test"
        )

        assert event.id != ""
        assert len(event.id) > 0
        # UUIDの形式を簡単に確認
        assert "-" in event.id

    def test_event_auto_generates_timestamp_when_none(self):
        """timestampがNoneの場合に自動生成されることをテスト。"""
        before_creation = datetime.now()

        event = Event(id="test", type="test", data={}, timestamp=None, source="test")

        after_creation = datetime.now()

        assert event.timestamp is not None
        assert isinstance(event.timestamp, datetime)
        assert before_creation <= event.timestamp <= after_creation

    def test_event_generates_unique_ids(self):
        """複数のEventで異なるIDが生成されることをテスト。"""
        event1 = Event(id="", type="test", data={}, timestamp=None, source="test")
        event2 = Event(id="", type="test", data={}, timestamp=None, source="test")

        assert event1.id != event2.id

    def test_event_immutable_data_structure(self):
        """Eventがイミュータブルなデータ構造であることをテスト。"""
        data = {"key": "value"}
        event = Event(
            id="test", type="test", data=data, timestamp=datetime.now(), source="test"
        )

        # データを変更してもEventには影響しないことを確認
        data["new_key"] = "new_value"
        assert "new_key" not in event.data


class TestEventBus:
    """EventBusクラスのテストケース。"""

    def setup_method(self):
        """各テストメソッド実行前の初期化。"""
        self.event_bus = EventBus()

    @pytest.mark.asyncio
    async def test_publish_and_subscribe_basic(self):
        """基本的なpublish/subscribeの動作をテスト。"""
        received_events = []

        async def test_callback(event):
            received_events.append(event)

        # イベントタイプに購読
        self.event_bus.subscribe("test_event", test_callback)

        # テスト用のイベントを作成してパブリッシュ
        test_event = Event(
            id="test-123",
            type="test_event",
            data={"message": "Hello"},
            timestamp=datetime.now(),
            source="test",
        )

        await self.event_bus.publish(test_event)

        # イベントバスを短時間実行してイベントを処理
        bus_task = asyncio.create_task(self.event_bus.start())
        await asyncio.sleep(0.1)
        self.event_bus.stop()

        # タスクが完了するまで少し待つ
        try:
            await asyncio.wait_for(bus_task, timeout=1.0)
        except asyncio.TimeoutError:
            pass

        # コールバックが呼ばれたことを確認
        assert len(received_events) == 1
        assert received_events[0].id == "test-123"
        assert received_events[0].type == "test_event"
        assert received_events[0].data["message"] == "Hello"

    @pytest.mark.asyncio
    async def test_multiple_subscribers_same_event_type(self):
        """同じイベントタイプに複数の購読者がいる場合をテスト。"""
        received_events_1 = []
        received_events_2 = []

        async def callback1(event):
            received_events_1.append(event)

        async def callback2(event):
            received_events_2.append(event)

        # 両方のコールバックを同じイベントタイプに購読
        self.event_bus.subscribe("test_event", callback1)
        self.event_bus.subscribe("test_event", callback2)

        # イベントをパブリッシュ
        test_event = Event(
            id="test",
            type="test_event",
            data={"data": "test"},
            timestamp=datetime.now(),
            source="test",
        )
        await self.event_bus.publish(test_event)

        # イベントバスを短時間実行
        bus_task = asyncio.create_task(self.event_bus.start())
        await asyncio.sleep(0.1)
        self.event_bus.stop()

        try:
            await asyncio.wait_for(bus_task, timeout=1.0)
        except asyncio.TimeoutError:
            pass

        # 両方のコールバックが呼ばれたことを確認
        assert len(received_events_1) == 1
        assert len(received_events_2) == 1
        assert received_events_1[0].id == received_events_2[0].id

    @pytest.mark.asyncio
    async def test_event_type_filtering(self):
        """イベントタイプでのフィルタリングをテスト。"""
        received_events = []

        async def callback(event):
            received_events.append(event)

        # 特定のイベントタイプに購読
        self.event_bus.subscribe("target_event", callback)

        # 異なるタイプのイベントをパブリッシュ
        event1 = Event(
            id="1",
            type="target_event",
            data={},
            timestamp=datetime.now(),
            source="test",
        )
        event2 = Event(
            id="2", type="other_event", data={}, timestamp=datetime.now(), source="test"
        )
        event3 = Event(
            id="3",
            type="target_event",
            data={},
            timestamp=datetime.now(),
            source="test",
        )

        await self.event_bus.publish(event1)
        await self.event_bus.publish(event2)
        await self.event_bus.publish(event3)

        # イベントバスを実行
        bus_task = asyncio.create_task(self.event_bus.start())
        await asyncio.sleep(0.1)
        self.event_bus.stop()

        try:
            await asyncio.wait_for(bus_task, timeout=1.0)
        except asyncio.TimeoutError:
            pass

        # target_eventのみが処理されたことを確認
        assert len(received_events) == 2
        assert received_events[0].id == "1"
        assert received_events[1].id == "3"

    @pytest.mark.asyncio
    async def test_sync_callback_support(self):
        """同期コールバックもサポートすることをテスト。"""
        received_events = []

        def sync_callback(event):
            received_events.append(event)

        self.event_bus.subscribe("test_event", sync_callback)

        test_event = Event(
            id="test",
            type="test_event",
            data={},
            timestamp=datetime.now(),
            source="test",
        )
        await self.event_bus.publish(test_event)

        # イベントバスを実行
        bus_task = asyncio.create_task(self.event_bus.start())
        await asyncio.sleep(0.1)
        self.event_bus.stop()

        try:
            await asyncio.wait_for(bus_task, timeout=1.0)
        except asyncio.TimeoutError:
            pass

        # 同期コールバックも正常に呼ばれたことを確認
        assert len(received_events) == 1
        assert received_events[0].id == "test"

    @pytest.mark.asyncio
    async def test_callback_exception_handling(self):
        """コールバックで例外が発生した場合の処理をテスト。"""
        received_events = []

        async def failing_callback(event):
            raise Exception("Test exception")

        async def working_callback(event):
            received_events.append(event)

        # 両方のコールバックを購読
        self.event_bus.subscribe("test_event", failing_callback)
        self.event_bus.subscribe("test_event", working_callback)

        test_event = Event(
            id="test",
            type="test_event",
            data={},
            timestamp=datetime.now(),
            source="test",
        )
        await self.event_bus.publish(test_event)

        # イベントバスを実行
        bus_task = asyncio.create_task(self.event_bus.start())
        await asyncio.sleep(0.1)
        self.event_bus.stop()

        try:
            await asyncio.wait_for(bus_task, timeout=1.0)
        except asyncio.TimeoutError:
            pass

        # 例外が発生しても他のコールバックは正常に動作することを確認
        assert len(received_events) == 1

    @pytest.mark.asyncio
    async def test_no_subscribers_for_event_type(self):
        """購読者がいないイベントタイプのテスト。"""
        test_event = Event(
            id="test",
            type="unknown_event",
            data={},
            timestamp=datetime.now(),
            source="test",
        )

        # 例外が発生しないことを確認
        await self.event_bus.publish(test_event)

        bus_task = asyncio.create_task(self.event_bus.start())
        await asyncio.sleep(0.1)
        self.event_bus.stop()

        try:
            await asyncio.wait_for(bus_task, timeout=1.0)
        except asyncio.TimeoutError:
            pass

        # 例外なく完了することを確認（実際のテストはここで完了）
        assert True

    def test_stop_sets_running_flag(self):
        """stop()メソッドが実行フラグを正しく設定することをテスト。"""
        # 初期状態では実行していない
        assert not self.event_bus._running

        # stop()を呼んでもエラーにならない
        self.event_bus.stop()
        assert not self.event_bus._running

    @pytest.mark.asyncio
    async def test_start_stop_lifecycle(self):
        """start/stopのライフサイクルをテスト。"""
        # タスクを開始
        bus_task = asyncio.create_task(self.event_bus.start())

        # 短時間待って実行状態になることを確認
        await asyncio.sleep(0.1)
        assert self.event_bus._running

        # 停止
        self.event_bus.stop()

        # タスクが終了することを確認
        try:
            await asyncio.wait_for(bus_task, timeout=1.0)
        except asyncio.TimeoutError:
            pytest.fail("EventBus task did not stop within timeout")

        assert not self.event_bus._running
