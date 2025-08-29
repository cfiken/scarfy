"""ScarfyEngineとWorkflowのテストモジュール。

エンジンのコアオーケストレーション機能を検証します。
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock

from src.scarfy.core.engine import ScarfyEngine, Workflow
from src.scarfy.core.events import Event
from src.scarfy.core.interfaces import Trigger, Agent, Output


class MockTrigger(Trigger):
    """テスト用のモックトリガー。"""

    def __init__(self):
        self.started = False
        self.stopped = False
        self.event_bus = None
        self.config = None

    async def start(self, event_bus, config):
        self.started = True
        self.event_bus = event_bus
        self.config = config

    async def stop(self):
        self.stopped = True

    async def trigger_event(self, event_data):
        """テスト用：イベントを手動でトリガー。"""
        if self.event_bus:
            event = Event(
                id="",
                type=self.config.get("event_type", "test_event"),
                data=event_data,
                timestamp=None,
                source="mock_trigger",
            )
            await self.event_bus.publish(event)


class MockAgent(Agent):
    """テスト用のモックエージェント。"""

    def __init__(self, return_value=None):
        self.processed_events = []
        self.return_value = return_value or {
            "status": "success",
            "message": "processed",
        }

    async def process(self, event, config):
        self.processed_events.append((event, config))
        return self.return_value


class MockOutput(Output):
    """テスト用のモック出力。"""

    def __init__(self):
        self.sent_data = []

    async def send(self, data, config):
        self.sent_data.append((data, config))


class TestWorkflow:
    """Workflowクラスのテストケース。"""

    def test_workflow_creation(self):
        """Workflowの正常な作成をテスト。"""
        trigger_config = {"type": "file_watcher", "path": "/tmp"}
        agent_config = {"type": "processor", "timeout": 30}
        output_config = {"type": "logger", "file": "/tmp/log.txt"}

        workflow = Workflow(
            name="test_workflow",
            trigger_config=trigger_config,
            agent_config=agent_config,
            output_config=output_config,
        )

        assert workflow.name == "test_workflow"
        assert workflow.trigger_config == trigger_config
        assert workflow.agent_config == agent_config
        assert workflow.output_config == output_config

    def test_workflow_config_immutability(self):
        """Workflowの設定が変更されても影響しないことをテスト。"""
        trigger_config = {"type": "file_watcher"}

        workflow = Workflow(
            name="test",
            trigger_config=trigger_config,
            agent_config={},
            output_config={},
        )

        # 元の設定を変更
        trigger_config["new_key"] = "new_value"

        # Workflowには影響しないことを確認
        assert "new_key" not in workflow.trigger_config


class TestScarfyEngine:
    """ScarfyEngineクラスのテストケース。"""

    def setup_method(self):
        """各テストメソッド実行前の初期化。"""
        self.engine = ScarfyEngine()
        self.mock_trigger = MockTrigger()
        self.mock_agent = MockAgent()
        self.mock_output = MockOutput()

    def test_engine_initialization(self):
        """エンジンの初期化をテスト。"""
        assert self.engine.event_bus is not None
        assert isinstance(self.engine.triggers, dict)
        assert isinstance(self.engine.agents, dict)
        assert isinstance(self.engine.outputs, dict)
        assert isinstance(self.engine.workflows, list)
        assert not self.engine._running

    def test_register_trigger(self):
        """トリガーの登録をテスト。"""
        self.engine.register_trigger("test_trigger", self.mock_trigger)

        assert "test_trigger" in self.engine.triggers
        assert self.engine.triggers["test_trigger"] is self.mock_trigger

    def test_register_agent(self):
        """エージェントの登録をテスト。"""
        self.engine.register_agent("test_agent", self.mock_agent)

        assert "test_agent" in self.engine.agents
        assert self.engine.agents["test_agent"] is self.mock_agent

    def test_register_output(self):
        """出力の登録をテスト。"""
        self.engine.register_output("test_output", self.mock_output)

        assert "test_output" in self.engine.outputs
        assert self.engine.outputs["test_output"] is self.mock_output

    def test_add_workflow(self):
        """ワークフローの追加をテスト。"""
        workflow = Workflow(
            name="test_workflow",
            trigger_config={"type": "test_trigger", "event_type": "test_event"},
            agent_config={"type": "test_agent"},
            output_config={"type": "test_output"},
        )

        self.engine.add_workflow(workflow)

        assert len(self.engine.workflows) == 1
        assert self.engine.workflows[0] is workflow

    @pytest.mark.asyncio
    async def test_start_with_registered_components(self):
        """登録されたコンポーネントでのエンジン開始をテスト。"""
        # コンポーネントを登録
        self.engine.register_trigger("test_trigger", self.mock_trigger)
        self.engine.register_agent("test_agent", self.mock_agent)
        self.engine.register_output("test_output", self.mock_output)

        # ワークフローを追加
        workflow = Workflow(
            name="test_workflow",
            trigger_config={"type": "test_trigger", "event_type": "test_event"},
            agent_config={"type": "test_agent"},
            output_config={"type": "test_output"},
        )
        self.engine.add_workflow(workflow)

        # エンジンを短時間実行
        engine_task = asyncio.create_task(self.engine.start())
        await asyncio.sleep(0.1)

        # トリガーが開始されたことを確認
        assert self.mock_trigger.started
        assert self.engine._running

        # エンジンを停止
        await self.engine.stop()

        # タスクの完了を待つ
        try:
            await asyncio.wait_for(engine_task, timeout=1.0)
        except asyncio.TimeoutError:
            pass

        assert not self.engine._running
        assert self.mock_trigger.stopped

    @pytest.mark.asyncio
    async def test_start_with_unregistered_trigger(self):
        """未登録のトリガーでのエンジン開始エラーをテスト。"""
        workflow = Workflow(
            name="test_workflow",
            trigger_config={"type": "nonexistent_trigger"},
            agent_config={"type": "test_agent"},
            output_config={"type": "test_output"},
        )
        self.engine.add_workflow(workflow)

        # ValueError が発生することを確認
        with pytest.raises(
            ValueError, match="Trigger 'nonexistent_trigger' not registered"
        ):
            await self.engine.start()

    @pytest.mark.asyncio
    async def test_workflow_processing_complete_flow(self):
        """完全なワークフロー処理をテスト。"""
        # コンポーネントを登録
        self.engine.register_trigger("test_trigger", self.mock_trigger)
        self.engine.register_agent("test_agent", self.mock_agent)
        self.engine.register_output("test_output", self.mock_output)

        # ワークフローを追加
        workflow = Workflow(
            name="test_workflow",
            trigger_config={"type": "test_trigger", "event_type": "test_event"},
            agent_config={"type": "test_agent", "param": "value"},
            output_config={"type": "test_output", "destination": "file"},
        )
        self.engine.add_workflow(workflow)

        # エンジンを開始
        engine_task = asyncio.create_task(self.engine.start())
        await asyncio.sleep(0.1)

        # イベントをトリガー
        await self.mock_trigger.trigger_event({"file_path": "/tmp/test.txt"})

        # イベント処理が完了するまで待機
        await asyncio.sleep(0.2)

        # エンジンを停止
        await self.engine.stop()

        try:
            await asyncio.wait_for(engine_task, timeout=1.0)
        except asyncio.TimeoutError:
            pass

        # エージェントがイベントを処理したことを確認
        assert len(self.mock_agent.processed_events) == 1
        event, config = self.mock_agent.processed_events[0]
        assert event.type == "test_event"
        assert event.data["file_path"] == "/tmp/test.txt"
        assert config["param"] == "value"

        # 出力がデータを受信したことを確認
        assert len(self.mock_output.sent_data) == 1
        data, config = self.mock_output.sent_data[0]
        assert data["status"] == "success"
        assert config["destination"] == "file"

    @pytest.mark.asyncio
    async def test_workflow_processing_with_unregistered_agent(self):
        """未登録のエージェントでの処理をテスト。"""
        self.engine.register_trigger("test_trigger", self.mock_trigger)

        workflow = Workflow(
            name="test_workflow",
            trigger_config={"type": "test_trigger", "event_type": "test_event"},
            agent_config={"type": "nonexistent_agent"},
            output_config={"type": "test_output"},
        )
        self.engine.add_workflow(workflow)

        # エンジンを開始
        engine_task = asyncio.create_task(self.engine.start())
        await asyncio.sleep(0.1)

        # イベントをトリガー（エラーになるが処理は継続）
        await self.mock_trigger.trigger_event({"test": "data"})
        await asyncio.sleep(0.1)

        # エンジンを停止
        await self.engine.stop()

        try:
            await asyncio.wait_for(engine_task, timeout=1.0)
        except asyncio.TimeoutError:
            pass

        # エージェントは呼ばれないことを確認
        assert len(self.mock_agent.processed_events) == 0

    @pytest.mark.asyncio
    async def test_workflow_processing_with_unregistered_output(self):
        """未登録の出力での処理をテスト。"""
        self.engine.register_trigger("test_trigger", self.mock_trigger)
        self.engine.register_agent("test_agent", self.mock_agent)

        workflow = Workflow(
            name="test_workflow",
            trigger_config={"type": "test_trigger", "event_type": "test_event"},
            agent_config={"type": "test_agent"},
            output_config={"type": "nonexistent_output"},
        )
        self.engine.add_workflow(workflow)

        # エンジンを開始
        engine_task = asyncio.create_task(self.engine.start())
        await asyncio.sleep(0.1)

        # イベントをトリガー
        await self.mock_trigger.trigger_event({"test": "data"})
        await asyncio.sleep(0.1)

        # エンジンを停止
        await self.engine.stop()

        try:
            await asyncio.wait_for(engine_task, timeout=1.0)
        except asyncio.TimeoutError:
            pass

        # エージェントは処理されるが、出力は呼ばれない
        assert len(self.mock_agent.processed_events) == 1
        assert len(self.mock_output.sent_data) == 0

    @pytest.mark.asyncio
    async def test_multiple_workflows(self):
        """複数のワークフローの処理をテスト。"""
        # 2つ目のモックエージェントを作成
        mock_agent2 = MockAgent({"status": "completed", "workflow": "2"})

        # コンポーネントを登録
        self.engine.register_trigger("test_trigger", self.mock_trigger)
        self.engine.register_agent("test_agent1", self.mock_agent)
        self.engine.register_agent("test_agent2", mock_agent2)
        self.engine.register_output("test_output", self.mock_output)

        # 2つのワークフローを追加
        workflow1 = Workflow(
            name="workflow1",
            trigger_config={"type": "test_trigger", "event_type": "test_event"},
            agent_config={"type": "test_agent1"},
            output_config={"type": "test_output"},
        )
        workflow2 = Workflow(
            name="workflow2",
            trigger_config={"type": "test_trigger", "event_type": "test_event"},
            agent_config={"type": "test_agent2"},
            output_config={"type": "test_output"},
        )

        self.engine.add_workflow(workflow1)
        self.engine.add_workflow(workflow2)

        # エンジンを開始
        engine_task = asyncio.create_task(self.engine.start())
        await asyncio.sleep(0.1)

        # イベントをトリガー
        await self.mock_trigger.trigger_event({"test": "data"})
        await asyncio.sleep(0.2)

        # エンジンを停止
        await self.engine.stop()

        try:
            await asyncio.wait_for(engine_task, timeout=1.0)
        except asyncio.TimeoutError:
            pass

        # 両方のエージェントが処理されたことを確認
        assert len(self.mock_agent.processed_events) == 1
        assert len(mock_agent2.processed_events) == 1

        # 両方の結果が出力に送信されたことを確認
        assert len(self.mock_output.sent_data) == 2

    @pytest.mark.asyncio
    async def test_agent_exception_handling(self):
        """エージェントで例外が発生した場合の処理をテスト。"""
        # 例外を発生させるモックエージェント
        failing_agent = Mock()
        failing_agent.process = AsyncMock(side_effect=Exception("Agent error"))

        self.engine.register_trigger("test_trigger", self.mock_trigger)
        self.engine.register_agent("failing_agent", failing_agent)
        self.engine.register_output("test_output", self.mock_output)

        workflow = Workflow(
            name="test_workflow",
            trigger_config={"type": "test_trigger", "event_type": "test_event"},
            agent_config={"type": "failing_agent"},
            output_config={"type": "test_output"},
        )
        self.engine.add_workflow(workflow)

        # エンジンを開始
        engine_task = asyncio.create_task(self.engine.start())
        await asyncio.sleep(0.1)

        # イベントをトリガー
        await self.mock_trigger.trigger_event({"test": "data"})
        await asyncio.sleep(0.1)

        # エンジンを停止
        await self.engine.stop()

        try:
            await asyncio.wait_for(engine_task, timeout=1.0)
        except asyncio.TimeoutError:
            pass

        # エージェントは呼ばれたが、出力は呼ばれない（例外のため）
        failing_agent.process.assert_called_once()
        assert len(self.mock_output.sent_data) == 0
