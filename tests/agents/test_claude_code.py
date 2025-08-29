"""ClaudeCodeAgent の MCP サーバー自動設定統合テスト。"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from src.scarfy.agents.claude_code import ClaudeCodeAgent
from src.scarfy.core.events import Event


class TestClaudeCodeMCPIntegration:
    """ClaudeCodeAgent の MCP 統合機能テスト。"""

    @pytest.fixture
    def mock_file_operations(self):
        """FileOperations のモック。"""
        mock = Mock()
        mock.validate_file.return_value = True
        mock.read_file_safe.return_value = "test file content"
        mock.calculate_output_paths.return_value = {
            "output_path": "/test/output.md",
            "output_dir": "/test",
            "output_name": "output.md",
            "output_basename": "output",
        }
        return mock

    @pytest.fixture
    def mock_template_engine(self):
        """TemplateEngine のモック。"""
        mock = Mock()
        mock.build_context.return_value = {}
        mock.replace_placeholders.return_value = "test prompt"
        return mock

    @pytest.fixture
    def agent(self, mock_file_operations, mock_template_engine):
        """ClaudeCodeAgent インスタンス。"""
        agent = ClaudeCodeAgent()
        agent.file_operations = mock_file_operations
        agent.template_engine = mock_template_engine
        return agent

    @pytest.fixture
    def test_event(self, tmp_path):
        """テスト用のEvent。"""
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')")

        return Event(
            id="test-event",
            type="file_change",
            data={"file_path": str(test_file)},
            timestamp=datetime.now(),
            source="test",
        )

    @pytest.mark.asyncio
    async def test_mcp_server_auto_configuration_first_time(self, agent, test_event):
        """初回実行時のMCPサーバー自動設定テスト。"""
        config = {
            "prompt": "Test prompt",
            "mcp_servers": ["arxiv-mcp-server"],
            "timeout": 30,
        }

        # MCPToolsManager.ensure_servers_configured をモック
        with (
            patch(
                "src.scarfy.utils.mcp_tools.MCPToolsManager.ensure_servers_configured"
            ) as mock_ensure,
            patch.object(
                agent, "_execute_claude_code", return_value=("output", 10.0)
            ) as mock_execute,
        ):

            mock_ensure.return_value = {"arxiv-mcp-server": True}

            result = await agent.process(test_event, config)

            # 期待結果の検証
            assert result["success"] is True  # ワークフロー全体が成功すること
            mock_ensure.assert_called_once_with(
                ["arxiv-mcp-server"]
            )  # MCP自動設定が呼ばれること
            assert (
                "arxiv-mcp-server" in agent._mcp_servers_initialized
            )  # 成功したサーバーが記録されること
            mock_execute.assert_called_once()  # Claude Code実行が行われること

    @pytest.mark.asyncio
    async def test_mcp_servers_not_reconfigured_on_second_call(self, agent, test_event):
        """2回目実行時は設定をスキップするテスト。"""
        config = {
            "prompt": "Test prompt",
            "mcp_servers": ["arxiv-mcp-server"],
            "timeout": 30,
        }

        # 最初から初期化済みに設定
        agent._mcp_servers_initialized.add("arxiv-mcp-server")

        with (
            patch(
                "src.scarfy.utils.mcp_tools.MCPToolsManager.ensure_servers_configured"
            ) as mock_ensure,
            patch.object(agent, "_execute_claude_code", return_value=("output", 10.0)),
        ):

            result = await agent.process(test_event, config)

            # 期待結果の検証
            assert result["success"] is True  # ワークフロー全体が成功すること
            mock_ensure.assert_not_called()  # 2回目実行時はMCP設定をスキップすること

    @pytest.mark.asyncio
    async def test_no_mcp_servers_config(self, agent, test_event):
        """mcp_servers設定なしの場合のテスト。"""
        config = {
            "prompt": "Test prompt",
            "timeout": 30,
            # mcp_servers なし
        }

        with (
            patch(
                "src.scarfy.utils.mcp_tools.MCPToolsManager.ensure_servers_configured"
            ) as mock_ensure,
            patch.object(agent, "_execute_claude_code", return_value=("output", 10.0)),
        ):

            result = await agent.process(test_event, config)

            # 期待結果の検証
            assert result["success"] is True  # ワークフロー全体が成功すること
            mock_ensure.assert_not_called()  # mcp_servers設定なしならMCP設定は呼ばれないこと

    @pytest.mark.asyncio
    async def test_empty_mcp_servers_config(self, agent, test_event):
        """空のmcp_servers設定の場合のテスト。"""
        config = {"prompt": "Test prompt", "mcp_servers": [], "timeout": 30}  # 空配列

        with (
            patch(
                "src.scarfy.utils.mcp_tools.MCPToolsManager.ensure_servers_configured"
            ) as mock_ensure,
            patch.object(agent, "_execute_claude_code", return_value=("output", 10.0)),
        ):

            result = await agent.process(test_event, config)

            # 期待結果の検証
            assert result["success"] is True  # ワークフロー全体が成功すること
            mock_ensure.assert_not_called()  # 空のmcp_servers配列ならMCP設定は呼ばれないこと

    @pytest.mark.asyncio
    async def test_mcp_configuration_partial_failure(self, agent, test_event):
        """一部サーバーの設定失敗時の処理テスト。"""
        config = {
            "prompt": "Test prompt",
            "mcp_servers": ["arxiv-mcp-server", "unknown-server"],
            "timeout": 30,
        }

        with (
            patch(
                "src.scarfy.utils.mcp_tools.MCPToolsManager.ensure_servers_configured"
            ) as mock_ensure,
            patch.object(agent, "_execute_claude_code", return_value=("output", 10.0)),
        ):

            # 一部成功、一部失敗
            mock_ensure.return_value = {
                "arxiv-mcp-server": True,
                "unknown-server": False,
            }

            result = await agent.process(test_event, config)

            # 期待結果の検証
            assert (
                result["success"] is True
            )  # 部分失敗でもワークフロー全体は継続すること
            mock_ensure.assert_called_once_with(
                ["arxiv-mcp-server", "unknown-server"]
            )  # 全サーバーでMCP設定が試行されること
            # 成功したサーバーのみ初期化済みに追加されること
            assert (
                "arxiv-mcp-server" in agent._mcp_servers_initialized
            )  # 成功サーバーが記録されること
            assert (
                "unknown-server" not in agent._mcp_servers_initialized
            )  # 失敗サーバーは記録されないこと

    @pytest.mark.asyncio
    async def test_mcp_configuration_complete_failure(self, agent, test_event):
        """全サーバーの設定失敗時の処理テスト。"""
        config = {
            "prompt": "Test prompt",
            "mcp_servers": ["unknown-server"],
            "timeout": 30,
        }

        with (
            patch(
                "src.scarfy.utils.mcp_tools.MCPToolsManager.ensure_servers_configured"
            ) as mock_ensure,
            patch.object(agent, "_execute_claude_code", return_value=("output", 10.0)),
        ):

            mock_ensure.return_value = {"unknown-server": False}

            result = await agent.process(test_event, config)

            # 期待結果の検証
            assert (
                result["success"] is True
            )  # 全MCP設定失敗でもワークフロー全体は継続すること
            mock_ensure.assert_called_once_with(
                ["unknown-server"]
            )  # MCP設定が試行されること
            assert (
                "unknown-server" not in agent._mcp_servers_initialized
            )  # 失敗サーバーは記録されないこと

    @pytest.mark.asyncio
    async def test_mcp_multiple_servers_mixed_initialization(self, agent, test_event):
        """複数サーバーの混在初期化テスト。"""
        config = {
            "prompt": "Test prompt",
            "mcp_servers": ["arxiv-mcp-server", "already-initialized", "new-server"],
            "timeout": 30,
        }

        # 一部はすでに初期化済み
        agent._mcp_servers_initialized.add("already-initialized")

        with (
            patch(
                "src.scarfy.utils.mcp_tools.MCPToolsManager.ensure_servers_configured"
            ) as mock_ensure,
            patch.object(agent, "_execute_claude_code", return_value=("output", 10.0)),
        ):

            mock_ensure.return_value = {"arxiv-mcp-server": True, "new-server": False}

            result = await agent.process(test_event, config)

            # 期待結果の検証
            assert result["success"] is True  # ワークフロー全体が成功すること
            # 初期化済みでないサーバーのみを ensure_servers_configured に渡されること
            mock_ensure.assert_called_once_with(
                ["arxiv-mcp-server", "new-server"]
            )  # 未初期化サーバーのみ処理されること
            # 成功したサーバーのみ追加されること
            assert (
                "arxiv-mcp-server" in agent._mcp_servers_initialized
            )  # 新規成功サーバーが追加されること
            assert (
                "already-initialized" in agent._mcp_servers_initialized
            )  # 既存の初期化済みサーバーが保持されること
            assert (
                "new-server" not in agent._mcp_servers_initialized
            )  # 失敗サーバーは追加されないこと

    @pytest.mark.asyncio
    async def test_mcp_ensure_exception_handling(self, agent, test_event):
        """MCP設定中の例外処理テスト。"""
        config = {
            "prompt": "Test prompt",
            "mcp_servers": ["arxiv-mcp-server"],
            "timeout": 30,
        }

        with (
            patch(
                "src.scarfy.utils.mcp_tools.MCPToolsManager.ensure_servers_configured"
            ) as mock_ensure,
            patch.object(agent, "_execute_claude_code", return_value=("output", 10.0)),
        ):

            # ensure_servers_configured が例外を投げる
            mock_ensure.side_effect = Exception("MCP configuration failed")

            result = await agent.process(test_event, config)

            # 期待結果の検証：MCP設定で例外発生してもワークフロー実行は継続する
            assert (
                result["success"] is True
            )  # MCP例外にも関わらずワークフロー全体は成功すること
            mock_ensure.assert_called_once_with(
                ["arxiv-mcp-server"]
            )  # MCP設定が試行されること
            # MCP設定例外により初期化済みには追加されないこと
            assert (
                "arxiv-mcp-server" not in agent._mcp_servers_initialized
            )  # 例外発生時はサーバーが記録されないこと
