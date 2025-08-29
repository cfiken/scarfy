"""Scarfyのメインエントリーポイント。

Scarfy自動化フレームワークのコマンドラインインターフェースと
使用例を提供します。異なるタイプのワークフローを設定・実行する
方法を示すデモンストレーションモードを含みます。

main()関数はコマンドライン引数を処理し、異なる実行モードを
設定します：
- デモモード：ファイル監視とコンソール出力
- ファイル監視モード：特定のディレクトリを監視
- 手動モード：対話的なコマンドライン実行

各モードはフレームワークの異なる側面を示し、カスタム自動化
ワークフローを構築するための出発点として使用できます。
"""

import asyncio
import argparse
from pathlib import Path
from datetime import datetime

from .core.engine import ScarfyEngine, Workflow
from .core.interfaces import ControllableTrigger
from .triggers.file_watcher import FileWatcherTrigger
from .triggers.manual import ManualTrigger
from .agents.echo import EchoAgent
from .agents.file_print import FilePrintAgent
from .agents.claude_code import ClaudeCodeAgent
from .outputs.console import ConsoleOutput
from .outputs.file import FileOutput
from .config.loader import ConfigLoader


def add_workflow_with_auto_trigger(engine: ScarfyEngine, workflow: Workflow) -> None:
    """ワークフローを追加し、必要に応じて自動でトリガーインスタンスを作成。

    Args:
        engine: ScarfyEngineインスタンス
        workflow: 追加するワークフロー
    """
    trigger_type = workflow.trigger_config.get("type")
    if trigger_type == "file_watcher":
        # ファイル監視の場合、パス別にユニークなトリガー名を生成
        path = workflow.trigger_config.get("path", ".")
        trigger_name = f"file_watcher_{abs(hash(path))}"

        # まだ登録されていない場合は新しいトリガーインスタンスを作成
        if trigger_name not in engine.triggers:
            print(f"🔧 新しいトリガー作成: {trigger_name} (path: {path})")
            engine.register_trigger(trigger_name, FileWatcherTrigger())

        # ワークフローの設定を更新
        workflow.trigger_config["type"] = trigger_name

    engine.add_workflow(workflow)


def main_sync() -> None:
    """同期エントリーポイント。"""
    asyncio.run(main())


async def main() -> None:
    """メインエントリーポイント。

    コマンドライン引数を解析し、適切なモードを実行します。
    利用可能なすべてのコンポーネントでエンジンを設定し、
    異なるワークフロー設定を実演します。

    コマンドライン引数:
        --config <file>: 設定ファイルを指定してワークフローを実行
        --demo: デモモード（現在のディレクトリを監視）
        --watch <dir>: 特定のディレクトリの変更を監視
        --manual: 対話的な手動トリガーモード

    使用例:
        uv run scarfy --config config/sample.yaml
        python -m scarfy --demo
        python -m scarfy --watch /path/to/monitor
        python -m scarfy --manual
    """
    parser = argparse.ArgumentParser(
        description="Scarfy - Agent Automation Framework",
        epilog="Use Ctrl+C to stop any running mode.",
    )
    parser.add_argument(
        "--config", type=str, help="Configuration file to load workflows from"
    )
    parser.add_argument(
        "--manual", action="store_true", help="Interactive manual trigger mode"
    )

    args = parser.parse_args()

    # エンジンを作成・設定
    engine = ScarfyEngine()

    # 利用可能なすべてのコンポーネントを登録
    # file_watcher はワークフローごとに自動作成されるため、ここでは登録しない
    engine.register_trigger("manual", ManualTrigger())
    engine.register_agent("echo", EchoAgent())
    engine.register_agent("file_print", FilePrintAgent())
    engine.register_agent("claude_code", ClaudeCodeAgent())
    engine.register_output("console", ConsoleOutput())
    engine.register_output("file", FileOutput())

    # 引数に基づいて適切なモードを実行
    if args.config:
        await run_with_config(args.config)
    elif args.manual:
        await run_manual_mode(engine)
    else:
        print("Please specify one of: --config <file> or --manual")
        print("Use --help for more information.")


async def run_with_config(config_path: str) -> None:
    """設定ファイルからワークフローを読み込んで実行。

    指定された設定ファイルからワークフローを読み込み、
    外部プロンプトファイルと組み合わせて実行します。

    Args:
        config_path: 読み込む設定ファイルのパス
    """
    try:
        # 設定ファイルを読み込み
        loader = ConfigLoader()
        config_file_path = Path(config_path)

        if not config_file_path.exists():
            print(f"❌ 設定ファイルが見つかりません: {config_path}")
            return

        print(f"📁 設定ファイル読み込み中: {config_path}")
        config = loader.load_config(config_file_path)

        if "workflows" not in config:
            print("❌ 設定ファイルに workflows が定義されていません")
            return

        workflows_config = config["workflows"]
        print(f"📝 {len(workflows_config)}個のワークフローを読み込みました")

        # エンジンを作成・設定
        engine = ScarfyEngine()

        # 利用可能なすべてのコンポーネントを登録
        engine.register_trigger("manual", ManualTrigger())
        engine.register_agent("echo", EchoAgent())
        engine.register_agent("file_print", FilePrintAgent())
        engine.register_agent("claude_code", ClaudeCodeAgent())
        engine.register_output("console", ConsoleOutput())
        engine.register_output("file", FileOutput())

        # 設定からワークフローを作成
        for workflow_config in workflows_config:
            try:
                # プロンプトファイルが指定されている場合は読み込み
                agent_config = workflow_config.get("agent", {}).copy()
                prompt_file = agent_config.get("prompt_file")

                if prompt_file:
                    # 相対パスの場合はsrc/scarfyを基準とする
                    if not prompt_file.startswith("/"):
                        prompt_path = Path("src/scarfy") / prompt_file
                    else:
                        prompt_path = Path(prompt_file)

                    if prompt_path.exists():
                        prompt_content = loader.load_prompt_from_file(prompt_path)
                        agent_config["prompt"] = prompt_content
                        del agent_config["prompt_file"]  # prompt_file は削除
                        print(f"   📄 プロンプト読み込み: {prompt_path}")
                    else:
                        print(f"   ⚠️ プロンプトファイルが見つかりません: {prompt_path}")

                # パスの環境変数展開
                trigger_config = workflow_config.get("trigger", {}).copy()
                if "path" in trigger_config:
                    trigger_config["path"] = loader.expand_env_vars(
                        trigger_config["path"]
                    )

                if "output_dir" in agent_config:
                    agent_config["output_dir"] = loader.expand_env_vars(
                        agent_config["output_dir"]
                    )

                # ワークフローを作成・登録
                workflow = Workflow(
                    name=workflow_config["name"],
                    trigger_config=trigger_config,
                    agent_config=agent_config,
                    output_config=workflow_config.get("output", {}),
                )

                print(f"   ✅ ワークフロー登録: {workflow_config['name']}")
                add_workflow_with_auto_trigger(engine, workflow)

            except Exception as e:
                print(
                    f"   ❌ ワークフロー '{workflow_config.get('name', '不明')}' の設定エラー: {e}"
                )
                continue

        print("\n🚀 Scarfy開始 - 設定ファイルベースモード")
        print("⏹️  Press Ctrl+C to stop\n")

        # エンジン開始
        await engine.start()

    except KeyboardInterrupt:
        print("\n⏹️  Stopping Scarfy...")
        if "engine" in locals():
            await engine.stop()
        print("✅ Scarfy stopped.")
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")


async def run_manual_mode(engine: ScarfyEngine) -> None:
    """対話的な手動トリガーモードを実行。

    ユーザーがコマンドを入力することで手動でイベントを
    トリガーできるコマンドラインインターフェースを提供します。
    このモードはワークフローの対話的テストや、システムがイベントに
    どのように応答するかを理解するのに便利です。

    Args:
        engine: 設定済みのScarfyEngineインスタンス

    コマンド:
        trigger - 手動トリガーイベントを送信
        quit - 対話モードを終了
    """
    workflow = Workflow(
        name="manual_workflow",
        trigger_config={"type": "manual", "event_type": "manual_trigger"},
        agent_config={
            "type": "claude_code",
            "prompt": "ファイルの内容を分析してください",
            "timeout": 180,
            "max_file_size": 1048576,
        },
        output_config={
            "type": "console",
            "prefix": "[MANUAL]",
            "pretty": True,
            "timestamp": True,
        },
    )

    engine.add_workflow(workflow)

    # エンジンをバックグラウンドで開始
    engine_task = asyncio.create_task(engine.start())

    print("🎮 Manual trigger mode - Interactive workflow testing")
    print("📝 Available commands:")
    print("   'trigger' - Send a manual trigger event")
    print("   'claude <file_path> <prompt>' - Analyze file with Claude Code")
    print("   'quit'    - Exit manual mode")
    print("⏹️  Or press Ctrl+C to exit\n")

    try:
        while True:
            try:
                command = input("> ").strip().lower()
            except EOFError:
                # Ctrl+D を処理
                break

            if command == "quit" or command == "q":
                break
            elif command == "trigger" or command == "t":
                manual_trigger: ControllableTrigger = engine.triggers["manual"]  # type: ignore
                await manual_trigger.trigger(
                    {
                        "user_input": "manual_command",
                        "timestamp": datetime.now().isoformat(),
                    }
                )
                print("✅ Trigger sent!")
            elif command.startswith("claude "):
                # Claude Code実行コマンド: claude <file_path> <prompt>
                parts = command.split(" ", 2)
                if len(parts) < 3:
                    print("❌ Usage: claude <file_path> <prompt>")
                    print("   Example: claude test.py このコードをレビューしてください")
                else:
                    file_path = parts[1]
                    custom_prompt = parts[2]
                    manual_trigger: ControllableTrigger = engine.triggers["manual"]  # type: ignore
                    await manual_trigger.trigger(
                        {
                            "file_path": file_path,
                            "custom_prompt": custom_prompt,
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
                    print(f"✅ Claude Code analysis started for: {file_path}")
            elif command == "help" or command == "h":
                print("Commands:")
                print("  'trigger' (or 't') - Send a manual trigger event")
                print("  'claude <file> <prompt>' - Analyze file with Claude Code")
                print("  'quit' (or 'q') - Exit manual mode")
                print("  'help' (or 'h') - Show this help")
            elif command == "":
                continue  # Ignore empty input
            else:
                print(
                    f"❌ Unknown command: '{command}'. Type 'help' for available commands."
                )

    except KeyboardInterrupt:
        pass

    print("\n⏹️  Stopping manual mode...")
    engine_task.cancel()
    await engine.stop()
    print("✅ Manual mode stopped.")


if __name__ == "__main__":
    main_sync()
