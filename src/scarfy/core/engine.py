"""Scarfyのコアエンジン。

このモジュールはScarfy自動化フレームワークのメインオーケストレーションロジックを
含んでいます。ScarfyEngineはトリガー、エージェント、出力を調整して
自動化ワークフローを実行します。

主要コンポーネント：
- Workflow: 単一自動化ワークフローの設定
- ScarfyEngine: すべてのコンポーネントとワークフローを管理するメインコーディネーター
"""

import asyncio
import copy
from typing import Dict, Any, List
from .events import EventBus, Event
from .interfaces import Trigger, Agent, Output


class Workflow:
    """単一ワークフロー設定を表現します。

    ワークフローは特定のタイプのイベントをどのように処理するかを定義します：
    1. トリガー設定はどのイベントをリッスンするかを指定
    2. エージェント設定はそれらのイベントをどのように処理するかを定義
    3. 出力設定は結果をどこに送るかを決定

    属性：
        name: このワークフローの人間に読みやすい名前
        trigger_config: トリガーコンポーネントの設定辞書
        agent_config: エージェントコンポーネントの設定辞書
        output_config: 出力コンポーネントの設定辞書

    例：
        >>> workflow = Workflow(
        ...     name="file_processor",
        ...     trigger_config={"type": "file_watcher", "path": "/tmp"},
        ...     agent_config={"type": "file_analyzer", "deep_scan": True},
        ...     output_config={"type": "slack", "channel": "#alerts"}
        ... )
    """

    def __init__(
        self,
        name: str,
        trigger_config: Dict[str, Any],
        agent_config: Dict[str, Any],
        output_config: Dict[str, Any],
    ):
        """新しいワークフローを初期化します。

        Args:
            name: このワークフローの説明的な名前
            trigger_config: トリガーコンポーネントの設定
            agent_config: エージェントコンポーネントの設定
            output_config: 出力コンポーネントの設定
        """
        self.name = name
        self.trigger_config = copy.deepcopy(trigger_config)
        self.agent_config = copy.deepcopy(agent_config)
        self.output_config = copy.deepcopy(output_config)


class ScarfyEngine:
    """Main engine that orchestrates triggers, agents, and outputs.

    The ScarfyEngine is the central coordinator of the automation framework.
    It manages:
    - Component registration (triggers, agents, outputs)
    - Workflow configuration and event routing
    - Lifecycle management (starting/stopping components)
    - Event processing coordination

    The engine uses an event-driven architecture where:
    1. Triggers detect events and publish them to the event bus
    2. The engine routes events to appropriate workflows
    3. Agents process events and generate results
    4. Outputs handle the results

    Example usage:
        >>> engine = ScarfyEngine()
        >>>
        >>> # Register components
        >>> engine.register_trigger("file_watcher", FileWatcherTrigger())
        >>> engine.register_agent("processor", FileProcessorAgent())
        >>> engine.register_output("logger", FileOutput())
        >>>
        >>> # Add workflow
        >>> workflow = Workflow("my_workflow", trigger_cfg, agent_cfg, output_cfg)
        >>> engine.add_workflow(workflow)
        >>>
        >>> # Start processing
        >>> await engine.start()
    """

    def __init__(self) -> None:
        """Initialize a new ScarfyEngine instance.

        Creates the event bus and initializes component registries.
        The engine starts in a stopped state.
        """
        self.event_bus = EventBus()
        self.triggers: Dict[str, Trigger] = {}
        self.agents: Dict[str, Agent] = {}
        self.outputs: Dict[str, Output] = {}
        self.workflows: List[Workflow] = []
        self._running = False

    def register_trigger(self, name: str, trigger: Trigger) -> None:
        """Register a trigger implementation.

        Args:
            name: Unique identifier for this trigger type
            trigger: Trigger implementation instance

        Example:
            >>> engine.register_trigger("file_watcher", FileWatcherTrigger())
        """
        self.triggers[name] = trigger

    def register_agent(self, name: str, agent: Agent) -> None:
        """Register an agent implementation.

        Args:
            name: Unique identifier for this agent type
            agent: Agent implementation instance

        Example:
            >>> engine.register_agent("llm_processor", ClaudeAgent())
        """
        self.agents[name] = agent

    def register_output(self, name: str, output: Output) -> None:
        """Register an output implementation.

        Args:
            name: Unique identifier for this output type
            output: Output implementation instance

        Example:
            >>> engine.register_output("slack", SlackOutput())
        """
        self.outputs[name] = output

    def add_workflow(self, workflow: Workflow) -> None:
        """Add a workflow to the engine.

        Registers the workflow and sets up event routing so that when
        matching events are published, they will be processed by this workflow.

        Args:
            workflow: Workflow instance to add

        Note:
            The workflow's trigger must already be registered with the engine
            before adding the workflow.
        """
        self.workflows.append(workflow)

        # Subscribe to events for this workflow
        event_type = workflow.trigger_config.get("event_type", "default")

        # Create a proper async callback that awaits the workflow processing
        async def workflow_callback(event: Event) -> None:
            await self._process_workflow(workflow, event)

        self.event_bus.subscribe(event_type, workflow_callback)

    async def start(self) -> None:
        """Start the engine and all configured workflows.

        This method:
        1. Starts the event bus for message routing
        2. Starts all triggers configured in workflows
        3. Runs indefinitely until stop() is called

        The method will block until the engine is stopped, so it should
        typically be run as the main task of the application.

        Raises:
            ValueError: If a workflow references unregistered components
        """
        self._running = True

        # Start event bus
        event_bus_task = asyncio.create_task(self.event_bus.start())

        # Start all triggers used by workflows
        started_triggers = set()  # Avoid starting same trigger multiple times

        for workflow in self.workflows:
            trigger_type = workflow.trigger_config.get("type")
            if not trigger_type:
                continue

            if trigger_type not in self.triggers:
                raise ValueError(
                    f"Trigger '{trigger_type}' not registered for workflow '{workflow.name}'"
                )

            # Only start each trigger type once, even if multiple workflows use it
            if trigger_type not in started_triggers:
                trigger = self.triggers[trigger_type]
                await trigger.start(self.event_bus, workflow.trigger_config)
                started_triggers.add(trigger_type)

        # Wait for event bus (this blocks until stop() is called)
        await event_bus_task

    async def stop(self) -> None:
        """Stop the engine and clean up all resources.

        This method:
        1. Stops the event bus
        2. Stops all running triggers
        3. Cleans up any remaining resources

        After calling this method, the engine should not be restarted
        without creating a new instance.
        """
        self._running = False

        # Stop event bus
        self.event_bus.stop()

        # Stop all triggers
        for trigger in self.triggers.values():
            await trigger.stop()

    async def _process_workflow(self, workflow: Workflow, event: Event) -> None:
        """Process a single workflow when triggered by an event.

        This is the core workflow execution logic that:
        1. Finds the appropriate agent for the workflow
        2. Processes the event with the agent
        3. Sends the result to the configured output

        Errors in individual workflows are caught and logged to prevent
        one failing workflow from affecting others.

        Args:
            workflow: The workflow configuration to execute
            event: The triggering event to process
        """
        try:
            # Get the configured agent
            agent_type = workflow.agent_config.get("type")
            if not agent_type or agent_type not in self.agents:
                print(f"Agent '{agent_type}' not found for workflow '{workflow.name}'")
                return

            agent = self.agents[agent_type]

            # Process the event with the agent
            result = await agent.process(event, workflow.agent_config)

            # Send result to the configured output
            output_type = workflow.output_config.get("type")
            if output_type and output_type in self.outputs:
                output = self.outputs[output_type]
                await output.send(result, workflow.output_config)
            else:
                print(
                    f"Output '{output_type}' not found for workflow '{workflow.name}'"
                )

        except Exception as e:
            # Log error but don't let it crash other workflows
            print(f"Error processing workflow '{workflow.name}': {e}")
            # In production, use proper logging instead of print
