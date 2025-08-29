"""Claude Code統合エージェント。

このモジュールは、Claude Code CLIを使用してファイル処理を自動化するエージェントを
提供します。ワークフロー別に異なるプロンプトを指定でき、以下の用途に活用できます：
- コードレビューとリファクタリング提案
- ドキュメントの校正と改善
- ログファイルの分析
- 手動でのファイル分析とカスタムプロンプト実行
- プロンプトテンプレートによる動的プロンプト生成

Claude Code CLIを非同期で実行し、結果を構造化された形式で返します。
プロンプトテンプレート機能により、イベントデータを使った動的なプロンプト生成が可能です。
"""

import asyncio
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from ..core.interfaces import Agent
from ..core.events import Event
from ..utils.mcp_tools import MCPToolsManager
from ..utils.template_engine import TemplateEngine
from ..utils.file_operations import FileOperations


class ClaudeCodeAgent(Agent):
    """Claude Code CLIを使用してファイル処理を行うエージェント。

    このエージェントは、設定されたプロンプトでClaude Code CLIを実行し、
    ファイルの分析・処理を自動化します。ワークフロー別に異なるプロンプトを
    設定でき、手動トリガーではカスタムプロンプトの指定も可能です。

    設定オプション:
        prompt (str): Claude Codeに送信するプロンプト（テンプレート対応、必須）
        claude_path (str): Claude Code CLI実行パス（デフォルト: "claude"）
        timeout (int): 実行タイムアウト秒数（デフォルト: 300）
        max_file_size (int): 処理する最大ファイルサイズ（バイト、デフォルト: 1048576 = 1MB）
        allowed_extensions (list): 許可するファイル拡張子リスト（デフォルト: なし＝全て許可）
        include_file_path (bool): プロンプトにファイルパスを含めるか（デフォルト: True）
        output_dir (str): 出力ディレクトリのパス（任意、デフォルト: 入力ファイルと同じディレクトリ）
        output_suffix (str): 出力ファイル名に追加する接尾辞（デフォルト: "_processed"）
        show_realtime_output (bool): Claude Codeの途中出力をリアルタイム表示するか（デフォルト: True）
        mcp_servers (list): 使用するMCPサーバー名のリスト（空配列または未設定でMCP無効）
        additional_tools (list): 追加で許可するツール名のリスト（任意）

    プロンプトテンプレート機能:
        プロンプトには {key} 形式のプレースホルダーを使用可能：
        - {file_name}: ファイル名（拡張子なし）
        - {file_extension}: ファイル拡張子（.を含む）
        - {file_path}: 完全なファイルパス
        - {file_basename}: ファイル名（拡張子含む）
        - {file_content}: ファイル内容
        - {event_type}: イベントタイプ
        - {output_path}: 出力ファイルの完全パス
        - {output_dir}: 出力ディレクトリ
        - {output_name}: 出力ファイル名（拡張子含む）
        - {output_basename}: 出力ファイル名（拡張子なし）
        - その他event.dataの任意のキー

    設定例:
        {
            "type": "claude_code",
            "prompt": "ファイル {file_basename} （拡張子: {file_extension}）を分析して、{event_type} イベントに対する対応を提案してください。\n\nファイルパス: {file_path}\n\nファイル内容:\n```\n{file_content}\n```",
            "timeout": 180,
            "max_file_size": 524288,
            "allowed_extensions": [".py", ".js", ".ts", ".md"]
        }

    出力例:
        {
            "agent": "ClaudeCodeAgent",
            "action": "claude_code_executed",
            "prompt_used": "このコードをレビューして...",
            "file_path": "/path/to/file.py",
            "file_size": 1234,
            "execution_time": 45.2,
            "claude_output": "コードレビュー結果...",
            "success": True,
            "processing_time": "2024-01-01T12:00:01"
        }
    """

    def __init__(self) -> None:
        """ClaudeCodeAgentを初期化。

        必要なユーティリティクラスをインスタンス化します。
        """
        self.template_engine = TemplateEngine()
        self.file_operations = FileOperations()
        self._mcp_servers_initialized: set[str] = set()  # 初期化済みサーバーを記録

    async def process(self, event: Event, config: Dict[str, Any]) -> Dict[str, Any]:
        """Claude Code CLIでファイルを処理。

        設定されたプロンプトまたはイベントデータのカスタムプロンプトを使用して
        Claude Code CLIを実行し、ファイルを処理します。

        Args:
            event: 処理するEventオブジェクト（file_pathが必要）
            config: このエージェントの設定辞書

        Returns:
            処理結果を含む辞書:
            - agent: エージェント名
            - action: 実行されたアクション
            - prompt_used: 使用されたプロンプト
            - file_path: 処理されたファイルのパス
            - file_size: ファイルサイズ（バイト）
            - execution_time: Claude Code実行時間（秒）
            - claude_output: Claude Codeの出力結果
            - success: 処理が成功したかどうか
            - error: エラーが発生した場合のメッセージ
            - processing_time: 処理時刻のISO形式文字列

        例:
            >>> event = Event(data={"file_path": "/tmp/test.py"})
            >>> config = {"prompt": "このコードをレビューして"}
            >>> result = await agent.process(event, config)
            >>> print(result["success"])
            True
        """
        start_time = datetime.now()

        # トリガー発火ログ
        file_path = event.data.get("file_path", "Unknown")
        print(
            f"🚀 [ClaudeCodeAgent] トリガー発火: {file_path} (イベント: {event.type}) - {start_time.strftime('%H:%M:%S')}"
        )

        # 基本的な結果辞書を作成
        result = {
            "agent": "ClaudeCodeAgent",
            "action": "claude_code_executed",
            "prompt_used": None,
            "file_path": None,
            "file_size": None,
            "execution_time": None,
            "claude_output": None,
            "success": False,
            "processing_time": start_time.isoformat(),
        }

        try:
            # MCP サーバーの自動設定（初回実行時のみ）
            mcp_servers = config.get("mcp_servers", [])
            if mcp_servers:
                await self._ensure_mcp_servers(mcp_servers)

            # ファイルパスの取得と検証
            file_path = event.data.get("file_path")
            if not file_path:
                result["error"] = "ファイルパスがイベントデータに含まれていません"
                return result

            file_path_obj = Path(file_path)
            result["file_path"] = str(file_path_obj.absolute())

            # ファイルの存在確認
            if not file_path_obj.exists():
                result["error"] = f"ファイルが存在しません: {file_path}"
                return result

            # ファイルが通常ファイルかチェック
            if not file_path_obj.is_file():
                result["error"] = f"ディレクトリまたは特殊ファイルです: {file_path}"
                return result

            # セキュリティチェック（新しいFileOperationsを使用）
            security_check = self.file_operations.validate_file(file_path_obj, config)
            if security_check is not True:
                result["error"] = security_check
                return result

            # プロンプトの取得（ファイルパス情報も含めて処理）
            prompt = self._get_prompt(event, config, file_path_obj)
            if not prompt:
                result["error"] = (
                    'プロンプトが設定されていません（config["prompt"]またはevent.data["custom_prompt"]が必要）'
                )
                return result

            result["prompt_used"] = prompt

            file_size = file_path_obj.stat().st_size
            result["file_size"] = file_size  # type: ignore

            # Claude Code CLI実行
            claude_output, execution_time = await self._execute_claude_code(
                prompt, file_path_obj, config
            )

            result["claude_output"] = claude_output
            result["execution_time"] = execution_time  # type: ignore
            result["success"] = True

        except asyncio.TimeoutError:
            result["error"] = (
                f'Claude Code実行がタイムアウトしました（{config.get("timeout", 300)}秒）'
            )
        except Exception as e:
            result["error"] = f"予期しないエラー: {str(e)}"

        return result

    def _get_prompt(
        self, event: Event, config: Dict[str, Any], file_path_obj: Optional[Path] = None
    ) -> Optional[str]:
        """プロンプトを取得してテンプレート置換を実行。

        TemplateEngineを使用してプロンプトのテンプレート置換を行います。

        Args:
            event: イベントオブジェクト
            config: エージェント設定
            file_path_obj: ファイルパス（テンプレート用）

        Returns:
            テンプレート置換済みのプロンプト文字列、または None
        """
        # 手動トリガーでのカスタムプロンプトを優先
        custom_prompt = event.data.get("custom_prompt")
        if custom_prompt:
            prompt_template = custom_prompt
        else:
            # ワークフロー設定のプロンプト
            prompt_template = config.get("prompt")

        if not prompt_template:
            return None

        # ファイル内容を読み込み（file_path_objが提供されている場合）
        file_content = None
        if file_path_obj:
            file_content = self.file_operations.read_file_safe(file_path_obj)

        # 出力パス情報を計算
        output_paths = None
        if file_path_obj:
            output_paths = self.file_operations.calculate_output_paths(
                str(file_path_obj), config
            )

        # テンプレートエンジンでコンテキストを構築してテンプレート置換を実行
        context = self.template_engine.build_context(
            event, config, file_path_obj, file_content, output_paths
        )
        return self.template_engine.replace_placeholders(prompt_template, context)

    async def _execute_claude_code(
        self, prompt: str, file_path: Path, config: Dict[str, Any]
    ) -> tuple[str, float]:
        """Claude Code CLIを非同期実行。

        Args:
            prompt: Claude Codeに送信するプロンプト
            file_path: 処理するファイルのPath
            config: エージェント設定

        Returns:
            (claude_output, execution_time) のタプル

        Raises:
            asyncio.TimeoutError: タイムアウト時
            Exception: 実行エラー時
        """
        claude_path = config.get("claude_path", "claude")
        timeout = config.get("timeout", 300)

        full_prompt = prompt

        mcp_servers = config.get("mcp_servers", [])
        cmd_args = [claude_path]

        # setup tools
        base_tools = ["Edit", "Write", "Read"]
        mcp_tools = MCPToolsManager.get_tools_for_servers(mcp_servers)
        print(f"🔍 [DEBUG] MCP tools: {mcp_tools}")
        additional_tools = config.get("additional_tools", [])
        all_tools = base_tools + mcp_tools + additional_tools
        cmd_args.extend(["--allowedTools"] + all_tools)

        # プロンプトの追加
        cmd_args.extend(["--print", full_prompt])
        if config.get("verbose", False):
            cmd_args.extend(["--verbose"])
            # stream-json は大きなファイルでバッファ制限に引っかかるため無効化
            cmd_args.extend(["--output-format", "stream-json"])

        start_time = datetime.now()

        # リアルタイム出力を有効にするかどうか
        show_realtime_output = config.get("show_realtime_output", True)

        # 環境変数設定（大きなファイル処理対応）
        env = dict(os.environ)
        if mcp_servers:
            # Python の I/O エンコーディング設定（大きなファイル処理用）
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUNBUFFERED"] = "1"

        # Claude Code CLI実行
        process = await asyncio.create_subprocess_exec(
            *cmd_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        claude_output = ""
        try:
            if show_realtime_output:
                # リアルタイム出力モード
                print("🤖 [Claude Code] 実行開始...")

                # 標準出力をリアルタイムで読み取り
                while True:
                    try:
                        line = await asyncio.wait_for(
                            process.stdout.readline(), timeout=1.0  # type: ignore
                        )
                        if not line:
                            break

                        decoded_line = line.decode("utf-8", errors="replace")
                        claude_output += decoded_line
                        # リアルタイムで出力を表示（空行以外）
                        stripped_line = decoded_line.rstrip()
                        if stripped_line:
                            print(f"💬 [Claude]: {stripped_line}")
                    except asyncio.TimeoutError:
                        # タイムアウトしてもプロセスが生きていれば続行
                        if process.returncode is not None:
                            break
                        continue

                # プロセスの終了を待つ
                await asyncio.wait_for(process.wait(), timeout=timeout)

                # stderr も読み取り
                stderr_output = await process.stderr.read()  # type: ignore
                stderr = stderr_output.decode("utf-8", errors="replace")

            else:
                # 従来の一括出力モード
                stdout, stderr_bytes = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
                claude_output = stdout.decode("utf-8", errors="replace")
                stderr = stderr_bytes.decode("utf-8", errors="replace")

            execution_time = (datetime.now() - start_time).total_seconds()

            if process.returncode != 0:
                raise Exception(
                    f"Claude Code実行エラー (exit code {process.returncode}): {stderr}"
                )

            if show_realtime_output:
                print(f"✅ [Claude Code] 実行完了 ({execution_time:.1f}秒)")
                print(f"🔍 [DEBUG] Claude出力長: {len(claude_output)} 文字")
                print(f"🔍 [DEBUG] Stderr内容: {stderr[:200]}...")

            return claude_output, execution_time

        except asyncio.TimeoutError:
            # プロセス強制終了
            process.kill()
            await process.wait()
            raise

        except Exception:
            # プロセスクリーンアップ
            if process.returncode is None:
                process.kill()
                await process.wait()
            raise

    async def _ensure_mcp_servers(self, server_names: List[str]) -> None:
        """必要なMCPサーバーが設定されていることを確認し、未設定なら自動追加。

        Args:
            server_names: 必要なMCPサーバー名のリスト
        """

        # 未初期化のサーバーのみを抽出
        new_servers = [
            s for s in server_names if s not in self._mcp_servers_initialized
        ]
        if not new_servers:
            print(f"🔍 [DEBUG] すべてのMCPサーバーが初期化済み: {server_names}")
            return  # 全て初期化済み

        try:
            print(f"🔧 [MCP] サーバー自動設定を開始: {', '.join(new_servers)}")
            results = await MCPToolsManager.ensure_servers_configured(new_servers)

            for server, success in results.items():
                if success:
                    self._mcp_servers_initialized.add(server)
                    print(f"✅ [MCP] {server} の設定が完了しました")
                else:
                    print(f"⚠️ [MCP] {server} の自動設定に失敗しました")

        except Exception as e:
            print(f"❌ [MCP] サーバー設定中にエラーが発生しました: {str(e)}")
            # エラーが発生してもワークフロー実行は継続
