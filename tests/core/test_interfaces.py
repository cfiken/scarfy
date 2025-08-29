"""インターフェースのテストモジュール。

抽象基底クラスの定義と継承の動作を検証します。
"""

import pytest
import asyncio
from abc import ABC
from datetime import datetime
from src.scarfy.core.interfaces import Trigger, Agent, Output
from src.scarfy.core.events import Event
from src.scarfy.core.engine import ScarfyEngine, Workflow


class TestTriggerInterface:
    """Triggerインターフェースのテストケース。"""

    def test_trigger_is_abstract_class(self):
        """TriggerがABCから継承された抽象クラスであることをテスト。"""
        assert issubclass(Trigger, ABC)

        # 直接インスタンス化しようとするとTypeErrorが発生
        with pytest.raises(TypeError):
            Trigger()

    def test_trigger_abstract_methods(self):
        """Triggerの抽象メソッドが正しく定義されていることをテスト。"""
        # 抽象メソッドの存在確認
        assert hasattr(Trigger, "start")
        assert hasattr(Trigger, "stop")

        # 抽象メソッドのフラグ確認
        assert getattr(Trigger.start, "__isabstractmethod__", False)
        assert getattr(Trigger.stop, "__isabstractmethod__", False)

    def test_concrete_trigger_implementation(self):
        """具象Triggerクラスが正しく実装できることをテスト。"""

        class ConcreteTrigger(Trigger):
            def __init__(self):
                self.started = False
                self.stopped = False

            async def start(self, event_bus, config):
                self.started = True
                self.event_bus = event_bus
                self.config = config

            async def stop(self):
                self.stopped = True

        # 具象クラスはインスタンス化可能
        trigger = ConcreteTrigger()
        assert isinstance(trigger, Trigger)
        assert not trigger.started
        assert not trigger.stopped

    def test_incomplete_trigger_implementation(self):
        """不完全なTrigger実装でのエラーをテスト。"""

        # startメソッドのみ実装
        class IncompleteTrigger(Trigger):
            async def start(self, event_bus, config):
                pass

            # stopメソッドが未実装

        # インスタンス化時にTypeErrorが発生
        with pytest.raises(TypeError):
            IncompleteTrigger()


class TestAgentInterface:
    """Agentインターフェースのテストケース。"""

    def test_agent_is_abstract_class(self):
        """AgentがABCから継承された抽象クラスであることをテスト。"""
        assert issubclass(Agent, ABC)

        # 直接インスタンス化しようとするとTypeErrorが発生
        with pytest.raises(TypeError):
            Agent()

    def test_agent_abstract_methods(self):
        """Agentの抽象メソッドが正しく定義されていることをテスト。"""
        # 抽象メソッドの存在確認
        assert hasattr(Agent, "process")

        # 抽象メソッドのフラグ確認
        assert getattr(Agent.process, "__isabstractmethod__", False)

    def test_concrete_agent_implementation(self):
        """具象Agentクラスが正しく実装できることをテスト。"""

        class ConcreteAgent(Agent):
            def __init__(self, result=None):
                self.result = result or {"status": "success"}

            async def process(self, event, config):
                return {
                    "agent": "ConcreteAgent",
                    "event_id": event.id,
                    "config": config,
                    **self.result,
                }

        # 具象クラスはインスタンス化可能
        agent = ConcreteAgent()
        assert isinstance(agent, Agent)

    @pytest.mark.asyncio
    async def test_concrete_agent_process_method(self):
        """具象Agentのprocessメソッドをテスト。"""

        class TestAgent(Agent):
            async def process(self, event, config):
                return {
                    "processed": True,
                    "event_type": event.type,
                    "data": event.data,
                    "timeout": config.get("timeout", 30),
                }

        agent = TestAgent()

        # テスト用のイベントと設定
        event = Event(
            id="test-123",
            type="test_event",
            data={"file_path": "/tmp/test.txt"},
            timestamp=datetime.now(),
            source="test",
        )
        config = {"timeout": 60, "param": "value"}

        # processメソッドの実行
        result = await agent.process(event, config)

        assert result["processed"] is True
        assert result["event_type"] == "test_event"
        assert result["data"]["file_path"] == "/tmp/test.txt"
        assert result["timeout"] == 60

    def test_incomplete_agent_implementation(self):
        """不完全なAgent実装でのエラーをテスト。"""

        # processメソッドが未実装
        class IncompleteAgent(Agent):
            def __init__(self):
                pass

            # processメソッドが未実装

        # インスタンス化時にTypeErrorが発生
        with pytest.raises(TypeError):
            IncompleteAgent()


class TestOutputInterface:
    """Outputインターフェースのテストケース。"""

    def test_output_is_abstract_class(self):
        """OutputがABCから継承された抽象クラスであることをテスト。"""
        assert issubclass(Output, ABC)

        # 直接インスタンス化しようとするとTypeErrorが発生
        with pytest.raises(TypeError):
            Output()

    def test_output_abstract_methods(self):
        """Outputの抽象メソッドが正しく定義されていることをテスト。"""
        # 抽象メソッドの存在確認
        assert hasattr(Output, "send")

        # 抽象メソッドのフラグ確認
        assert getattr(Output.send, "__isabstractmethod__", False)

    def test_concrete_output_implementation(self):
        """具象Outputクラスが正しく実装できることをテスト。"""

        class ConcreteOutput(Output):
            def __init__(self):
                self.sent_data = []

            async def send(self, data, config):
                self.sent_data.append(
                    {"data": data, "config": config, "timestamp": datetime.now()}
                )

        # 具象クラスはインスタンス化可能
        output = ConcreteOutput()
        assert isinstance(output, Output)
        assert len(output.sent_data) == 0

    @pytest.mark.asyncio
    async def test_concrete_output_send_method(self):
        """具象Outputのsendメソッドをテスト。"""

        class TestOutput(Output):
            def __init__(self):
                self.messages = []

            async def send(self, data, config):
                message = {
                    "level": config.get("level", "info"),
                    "destination": config.get("destination", "console"),
                    "content": f"Status: {data.get('status', 'unknown')}",
                    "data": data,
                }
                self.messages.append(message)

        output = TestOutput()

        # テスト用のデータと設定
        data = {"status": "success", "message": "File processed", "file_count": 5}
        config = {"level": "debug", "destination": "file", "format": "json"}

        # sendメソッドの実行
        await output.send(data, config)

        assert len(output.messages) == 1
        message = output.messages[0]
        assert message["level"] == "debug"
        assert message["destination"] == "file"
        assert message["content"] == "Status: success"
        assert message["data"]["file_count"] == 5

    def test_incomplete_output_implementation(self):
        """不完全なOutput実装でのエラーをテスト。"""

        # sendメソッドが未実装
        class IncompleteOutput(Output):
            def __init__(self):
                self.data = []

            # sendメソッドが未実装

        # インスタンス化時にTypeErrorが発生
        with pytest.raises(TypeError):
            IncompleteOutput()


class TestInterfaceInteraction:
    """インターフェース間の相互作用をテスト。"""

    @pytest.mark.asyncio
    async def test_full_component_interaction(self):
        """Trigger、Agent、Outputの完全な相互作用をテスト。"""

        class TestTrigger(Trigger):
            async def start(self, event_bus, config):
                self.event_bus = event_bus
                # テスト用のイベントを即座に発火
                event = Event(
                    id="test-interaction",
                    type="test_event",
                    data={"source": "test_trigger"},
                    timestamp=datetime.now(),
                    source="TestTrigger",
                )
                await event_bus.publish(event)

            async def stop(self):
                pass

        class TestAgent(Agent):
            def __init__(self):
                self.processed = False

            async def process(self, event, config):
                self.processed = True
                return {
                    "agent": "TestAgent",
                    "processed_event": event.id,
                    "source_data": event.data,
                }

        class TestOutput(Output):
            def __init__(self):
                self.received = False
                self.last_data = None

            async def send(self, data, config):
                self.received = True
                self.last_data = data

        # コンポーネントのインスタンス作成
        trigger = TestTrigger()
        agent = TestAgent()
        output = TestOutput()

        # すべてが適切なインターフェースを実装していることを確認
        assert isinstance(trigger, Trigger)
        assert isinstance(agent, Agent)
        assert isinstance(output, Output)

        # 初期状態の確認
        assert not agent.processed
        assert not output.received

        # エージェント単体での処理テスト
        test_event = Event(
            id="manual-test",
            type="manual_event",
            data={"test": "data"},
            timestamp=datetime.now(),
            source="manual",
        )

        config = {"param": "value"}
        result = await agent.process(test_event, config)

        # エージェントが正しく処理したことを確認
        assert agent.processed
        assert result["processed_event"] == "manual-test"
        assert result["source_data"]["test"] == "data"

        # 出力との連携テスト
        output_config = {"destination": "test"}
        await output.send(result, output_config)

        # 出力が正しく処理したことを確認
        assert output.received
        assert output.last_data["agent"] == "TestAgent"
        assert output.last_data["processed_event"] == "manual-test"

    @pytest.mark.asyncio
    async def test_full_integration_with_event_bus(self):
        """EventBusを通じた完全なコンポーネント統合テスト。"""

        # 統合テスト用のトリガー（手動でイベントを発火可能）
        class IntegrationTestTrigger(Trigger):
            def __init__(self):
                self.event_bus = None
                self.config = None

            async def start(self, event_bus, config):
                self.event_bus = event_bus
                self.config = config

            async def stop(self):
                pass

            async def trigger_event(self, data):
                """手動でイベントを発火する"""
                if self.event_bus:
                    event = Event(
                        id="",
                        type=self.config.get("event_type", "integration_event"),
                        data=data,
                        timestamp=datetime.now(),
                        source="IntegrationTestTrigger",
                    )
                    await self.event_bus.publish(event)

        # 統合テスト用のエージェント
        class IntegrationTestAgent(Agent):
            def __init__(self):
                self.processed_events = []

            async def process(self, event, config):
                self.processed_events.append((event, config))
                return {
                    "agent": "IntegrationTestAgent",
                    "processed_event": event.id,
                    "source_data": event.data,
                    "config": config,
                }

        # 統合テスト用の出力
        class IntegrationTestOutput(Output):
            def __init__(self):
                self.sent_data = []

            async def send(self, data, config):
                self.sent_data.append((data, config))

        # 実際のエンジンを使用した統合テスト
        engine = ScarfyEngine()

        # テストコンポーネントを登録
        trigger = IntegrationTestTrigger()
        agent = IntegrationTestAgent()
        output = IntegrationTestOutput()

        engine.register_trigger("integration_trigger", trigger)
        engine.register_agent("integration_agent", agent)
        engine.register_output("integration_output", output)

        # ワークフローを追加
        workflow = Workflow(
            name="integration_workflow",
            trigger_config={
                "type": "integration_trigger",
                "event_type": "integration_event",
            },
            agent_config={"type": "integration_agent", "integration": True},
            output_config={
                "type": "integration_output",
                "destination": "integration_test",
            },
        )
        engine.add_workflow(workflow)

        # エンジンを開始
        engine_task = asyncio.create_task(engine.start())
        await asyncio.sleep(0.1)

        # トリガーを通じてイベントを発生
        await trigger.trigger_event(
            {"integration": "test_data", "workflow": "full_test"}
        )

        # イベント処理の完了を待機
        await asyncio.sleep(0.2)

        # エンジンを停止
        await engine.stop()

        try:
            await asyncio.wait_for(engine_task, timeout=1.0)
        except asyncio.TimeoutError:
            pass

        # 完全な統合フローが動作したことを確認
        assert (
            len(agent.processed_events) == 1
        ), "Agent should have processed exactly one event"

        processed_event, processed_config = agent.processed_events[0]
        assert processed_event.type == "integration_event"
        assert processed_event.data["integration"] == "test_data"
        assert processed_config["integration"] is True

        assert (
            len(output.sent_data) == 1
        ), "Output should have received exactly one result"

        sent_data, sent_config = output.sent_data[0]
        assert sent_data["processed_event"] == processed_event.id
        assert sent_data["agent"] == "IntegrationTestAgent"
        assert sent_config["destination"] == "integration_test"
