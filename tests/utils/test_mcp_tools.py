"""MCPToolsManager の MCP サーバー自動設定機能のテスト。"""

import pytest
from unittest.mock import patch, AsyncMock
from typing import List

from src.scarfy.utils.mcp_tools import MCPToolsManager, MCPServerCommandError


class TestMCPToolsManagerEnsure:
    """MCPToolsManager の自動設定機能テスト。"""

    @pytest.mark.asyncio
    async def test_ensure_servers_configured_success_new_server(self):
        """未設定サーバーの自動設定成功のテスト。"""
        server_names = ["arxiv-mcp-server"]

        with (
            patch.object(
                MCPToolsManager, "is_server_configured", return_value=False
            ) as mock_is_configured,
            patch.object(
                MCPToolsManager, "add_server", return_value=None
            ) as mock_add_server,
        ):

            result = await MCPToolsManager.ensure_servers_configured(server_names)

            # 期待結果の検証
            assert result == {"arxiv-mcp-server": True}
            mock_is_configured.assert_called_once_with("arxiv-mcp-server")
            mock_add_server.assert_called_once_with(
                "arxiv-mcp-server",
                [
                    "uvx",
                    "arxiv-mcp-server",
                    "--storage-path",
                    "~/.scarfy/arxiv-papers",
                ],
            )

    @pytest.mark.asyncio
    async def test_ensure_servers_configured_already_exists(self):
        """既設定サーバーのスキップテスト。"""
        server_names = ["arxiv-mcp-server"]

        with (
            patch.object(
                MCPToolsManager, "is_server_configured", return_value=True
            ) as mock_is_configured,
            patch.object(MCPToolsManager, "add_server") as mock_add_server,
        ):

            result = await MCPToolsManager.ensure_servers_configured(server_names)

            # 期待結果の検証
            assert result == {"arxiv-mcp-server": True}
            mock_is_configured.assert_called_once_with("arxiv-mcp-server")
            mock_add_server.assert_not_called()  # 既存の場合は add_server を呼ばない

    @pytest.mark.asyncio
    async def test_ensure_servers_configured_unknown_server(self):
        """未定義サーバーのエラーハンドリングテスト。"""
        server_names = ["unknown-server"]

        result = await MCPToolsManager.ensure_servers_configured(server_names)

        # 期待結果の検証
        assert result == {"unknown-server": False}

    @pytest.mark.asyncio
    async def test_ensure_servers_configured_command_failure(self):
        """claude mcp add コマンド失敗時の処理テスト。"""
        server_names = ["arxiv-mcp-server"]

        with (
            patch.object(
                MCPToolsManager, "is_server_configured", return_value=False
            ) as mock_is_configured,
            patch.object(
                MCPToolsManager,
                "add_server",
                side_effect=MCPServerCommandError(
                    "arxiv-mcp-server", ["test"], "error"
                ),
            ) as mock_add_server,
        ):

            result = await MCPToolsManager.ensure_servers_configured(server_names)

            # 期待結果の検証: 例外が発生しても適切にFalseを返す
            assert result == {"arxiv-mcp-server": False}
            mock_is_configured.assert_called_once_with("arxiv-mcp-server")
            mock_add_server.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_servers_configured_multiple_servers(self):
        """複数サーバーの混在ケース（成功・失敗・既存）テスト。"""
        server_names = ["arxiv-mcp-server", "unknown-server", "existing-server"]

        # arxiv-mcp-server: 新規追加成功
        # unknown-server: 未定義でエラー
        # existing-server: 既に設定済み（仮想的なサーバー）

        def mock_is_configured(server_name: str) -> bool:
            if server_name == "existing-server":
                return True
            return False

        def mock_add_server(server_name: str, command: List[str]) -> bool:
            if server_name == "arxiv-mcp-server":
                return True
            return False

        with (
            patch.object(
                MCPToolsManager, "is_server_configured", side_effect=mock_is_configured
            ),
            patch.object(MCPToolsManager, "add_server", side_effect=mock_add_server),
            patch.dict(
                "src.scarfy.utils.mcp_tools.MCP_SERVER_COMMANDS",
                {"existing-server": ["test-command"]},
                clear=False,
            ),
        ):

            result = await MCPToolsManager.ensure_servers_configured(server_names)

            # 期待結果の検証
            expected = {
                "arxiv-mcp-server": True,
                "unknown-server": False,
                "existing-server": True,
            }
            assert result == expected


class TestMCPToolsManagerServerCheck:
    """MCPToolsManager のサーバー状態確認機能テスト。"""

    @pytest.mark.asyncio
    async def test_is_server_configured_exists(self):
        """設定済みサーバーの確認テスト。"""
        server_name = "arxiv-mcp-server"

        # claude mcp get が成功（exit code 0）を模擬
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"server config", b"")
        mock_process.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await MCPToolsManager.is_server_configured(server_name)

            assert result is True

    @pytest.mark.asyncio
    async def test_is_server_configured_not_exists(self):
        """未設定サーバーの確認テスト。"""
        server_name = "nonexistent-server"

        # claude mcp get が失敗（exit code 1）を模擬
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"Server not found")
        mock_process.returncode = 1

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await MCPToolsManager.is_server_configured(server_name)

            assert result is False

    @pytest.mark.asyncio
    async def test_is_server_configured_exception(self):
        """コマンド実行例外時の処理テスト。"""
        server_name = "test-server"

        with patch(
            "asyncio.create_subprocess_exec", side_effect=Exception("Command failed")
        ):
            result = await MCPToolsManager.is_server_configured(server_name)

            assert result is False


class TestMCPToolsManagerServerAdd:
    """MCPToolsManager のサーバー追加機能テスト。"""

    @pytest.mark.asyncio
    async def test_add_server_success(self):
        """サーバー追加成功テスト。"""
        server_name = "arxiv-mcp-server"
        command = [
            "uv",
            "tool",
            "run",
            "arxiv-mcp-server",
            "--storage-path",
            "~/.scarfy/arxiv-papers",
        ]

        # claude mcp add が成功（exit code 0）を模擬
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"Server added successfully", b"")
        mock_process.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            # 成功時は例外を投げずに完了する
            await MCPToolsManager.add_server(server_name, command)
            # 例外が発生しなければテスト成功

    @pytest.mark.asyncio
    async def test_add_server_failure(self):
        """サーバー追加失敗テスト。"""
        server_name = "test-server"
        command = ["invalid-command"]

        # claude mcp add が失敗（exit code 1）を模擬
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"Command not found")
        mock_process.returncode = 1

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            # 失敗時はMCPServerCommandErrorを投げる
            with pytest.raises(MCPServerCommandError) as exc_info:
                await MCPToolsManager.add_server(server_name, command)

            assert exc_info.value.server_name == server_name
            assert exc_info.value.command == command

    @pytest.mark.asyncio
    async def test_add_server_exception(self):
        """サーバー追加例外時の処理テスト。"""
        server_name = "test-server"
        command = ["test-command"]

        with patch(
            "asyncio.create_subprocess_exec", side_effect=Exception("System error")
        ):
            # システム例外もMCPServerCommandErrorとして包装される
            with pytest.raises(MCPServerCommandError) as exc_info:
                await MCPToolsManager.add_server(server_name, command)

            assert exc_info.value.server_name == server_name
            assert exc_info.value.command == command
            assert exc_info.value.stderr == "システムエラー: System error"
