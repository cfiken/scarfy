"""MCPツール管理ユーティリティ。

MCPサーバーとそのツールの対応関係を管理し、
ClaudeCodeAgentなどでMCPツールを使用する際の
ツール名解決を提供します。

また、MCPサーバーの自動設定機能も提供します。
"""

import asyncio
from typing import List, Dict


class MCPServerError(Exception):
    """MCP サーバー関連エラーの基底クラス。"""

    pass


class MCPServerNotFoundError(MCPServerError):
    """MCP サーバーが見つからない場合のエラー。"""

    pass


class MCPServerCommandError(MCPServerError):
    """MCP サーバーコマンド実行エラー。"""

    def __init__(self, server_name: str, command: List[str], stderr: str = ""):
        self.server_name = server_name
        self.command = command
        self.stderr = stderr
        super().__init__(
            f"MCP server command failed for '{server_name}': {' '.join(command)}"
        )


class MCPServerConfigError(MCPServerError):
    """MCP サーバー設定エラー。"""

    def __init__(self, server_name: str, reason: str):
        self.server_name = server_name
        self.reason = reason
        super().__init__(
            f"MCP server configuration error for '{server_name}': {reason}"
        )


# MCPサーバーとツールの事前定義マッピング（実際のツール名に基づく）
MCP_TOOLS_MAP = {
    "filesystem": ["read_file", "write_file", "list_directory", "create_directory"],
    "fetch": ["fetch_url", "get_content"],
    "memory": ["store_memory", "retrieve_memory", "search_memory"],
    "sequential-thinking": ["think_step", "analyze_problem"],
    # community server
    "arxiv-mcp-server": [
        "mcp__arxiv-mcp-server__search_papers",
        "mcp__arxiv-mcp-server__download_paper",
        "mcp__arxiv-mcp-server__list_papers",
    ],  # , 'mcp__arxiv-mcp-server__read_paper'
}

# MCPサーバーの起動コマンドマッピング
MCP_SERVER_COMMANDS = {
    "arxiv-mcp-server": [
        "uvx",
        "arxiv-mcp-server",
        "--storage-path",
        "~/.scarfy/arxiv-papers",
    ],
}


class MCPToolsManager:
    """MCPサーバーのツール管理を担当するユーティリティクラス。

    MCPサーバー名からそのサーバーが提供するツール一覧を取得したり、
    新しいサーバーとツールの組み合わせを登録したりする機能を提供します。
    """

    @staticmethod
    def get_tools_for_servers(server_names: List[str]) -> List[str]:
        """指定されたMCPサーバー群から利用可能なツール一覧を取得。

        Args:
            server_names: MCPサーバー名のリスト

        Returns:
            利用可能なツール名のリスト（重複除去済み）
        """
        if not server_names:
            return []

        all_tools = []
        for server in server_names:
            if server in MCP_TOOLS_MAP:
                tools = MCP_TOOLS_MAP[server]
                all_tools.extend(tools)
                print(
                    f"📋 [MCP] {server} から {len(tools)} 個のツールを追加: {', '.join(tools)}"
                )
            else:
                print(
                    f"⚠️ [MCP] {server} は事前定義されていません（MCP_TOOLS_MAPに追加してください）"
                )

        return list(set(all_tools))  # 重複を除去

    @staticmethod
    def add_server_mapping(server_name: str, tools: List[str]) -> None:
        """新しいMCPサーバーとツールのマッピングを追加。

        Args:
            server_name: MCPサーバー名
            tools: そのサーバーが提供するツール名のリスト
        """
        MCP_TOOLS_MAP[server_name] = tools
        print(f"✅ [MCP] {server_name} のツールマッピングを追加: {', '.join(tools)}")

    @staticmethod
    def get_available_servers() -> List[str]:
        """利用可能なMCPサーバー一覧を取得。

        Returns:
            事前定義されているMCPサーバー名のリスト
        """
        return list(MCP_TOOLS_MAP.keys())

    @staticmethod
    def get_tools_for_server(server_name: str) -> List[str]:
        """指定されたMCPサーバーのツール一覧を取得。

        Args:
            server_name: MCPサーバー名

        Returns:
            そのサーバーが提供するツール名のリスト
        """
        return MCP_TOOLS_MAP.get(server_name, [])

    @staticmethod
    async def ensure_servers_configured(server_names: List[str]) -> Dict[str, bool]:
        """指定されたMCPサーバーがClaude Code CLIに設定されていることを確認し、未設定なら追加。

        Args:
            server_names: MCPサーバー名のリスト

        Returns:
            サーバー名と設定成功状態の辞書（True=成功、False=失敗）
        """
        results = {}

        for server_name in server_names:
            try:
                # 1. 既に設定されているかチェック
                if await MCPToolsManager.is_server_configured(server_name):
                    print(f"🔍 [MCP] {server_name} は既に設定済みです")
                    results[server_name] = True
                    continue

                # 2. サーバーコマンドを取得
                if server_name not in MCP_SERVER_COMMANDS:
                    raise MCPServerConfigError(server_name, "起動コマンドが未定義")

                command = MCP_SERVER_COMMANDS[server_name]

                # 3. サーバーを追加（失敗時は例外を投げる）
                await MCPToolsManager.add_server(server_name, command)
                results[server_name] = True

            except MCPServerConfigError as e:
                print(f"❌ [MCP] 設定エラー: {e}")
                results[server_name] = False

            except MCPServerCommandError as e:
                print(f"❌ [MCP] コマンド実行エラー: {e}")
                results[server_name] = False

            except Exception as e:
                print(f"❌ [MCP] {server_name} の設定中に予期しないエラー: {str(e)}")
                results[server_name] = False

        return results

    @staticmethod
    async def is_server_configured(server_name: str) -> bool:
        """指定されたMCPサーバーが設定されているかチェック。

        Args:
            server_name: MCPサーバー名

        Returns:
            設定されている場合True、されていない場合False
        """
        try:
            process = await asyncio.create_subprocess_exec(
                "claude",
                "mcp",
                "get",
                server_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            # exit code 0 = サーバーが存在
            return process.returncode == 0

        except Exception:
            return False

    @staticmethod
    async def add_server(server_name: str, command: List[str]) -> None:
        """MCPサーバーをClaude Code CLIに追加。

        Args:
            server_name: MCPサーバー名
            command: サーバー起動コマンド

        Raises:
            MCPServerCommandError: コマンド実行が失敗した場合
        """
        try:
            cmd_args = ["claude", "mcp", "add", server_name] + command

            process = await asyncio.create_subprocess_exec(
                *cmd_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                print(f"✅ [MCP] {server_name} を追加しました: {' '.join(command)}")
            else:
                stderr_text = stderr.decode()
                print(f"🔍 [DEBUG] MCP add failed - stderr: {stderr_text}")
                print(f"🔍 [DEBUG] MCP add failed - stdout: {stdout.decode()}")
                print(f"🔍 [DEBUG] MCP add failed - return code: {process.returncode}")
                raise MCPServerCommandError(server_name, command, stderr_text)

        except MCPServerCommandError:
            raise  # 再発生
        except Exception as e:
            raise MCPServerCommandError(
                server_name, command, f"システムエラー: {str(e)}"
            )
