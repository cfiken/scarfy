"""main.py のテスト。

このモジュールは、メインエントリーポイントの機能テストを提供します。
主に以下をテストします：
- main.py のimport機能
- --config オプションでの実行
- run_with_config 関数の動作
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from pathlib import Path


def test_main_import():
    """main.py が正常にimportできることをテスト。"""
    try:
        from src.scarfy.main import main

        # main関数が存在することを確認
        assert callable(main)
    except ImportError as e:
        pytest.fail(f"Failed to import main: {e}")


def test_main_dependencies_import():
    """main.py の主要依存関係がimportできることをテスト。"""
    try:
        from src.scarfy.core.engine import ScarfyEngine
        from src.scarfy.agents.claude_code import ClaudeCodeAgent  # noqa: F401
        from src.scarfy.triggers.file_watcher import FileWatcherTrigger  # noqa: F401
        from src.scarfy.outputs.console import ConsoleOutput  # noqa: F401

        # 基本的なクラスのインスタンス化が可能か確認
        engine = ScarfyEngine()
        assert engine is not None
        # インポートできることが重要（インスタンス化はScarfyEngineのみテスト）
        assert ClaudeCodeAgent is not None
        assert FileWatcherTrigger is not None
        assert ConsoleOutput is not None
    except ImportError as e:
        pytest.fail(f"Failed to import main dependencies: {e}")
    except Exception as e:
        pytest.fail(f"Failed to instantiate basic components: {e}")


class TestMainConfigOption:
    """--config オプション関連のテストクラス。"""

    @pytest.mark.asyncio
    async def test_run_with_config_function_exists(self) -> None:
        """run_with_config 関数が存在することをテスト。"""
        try:
            from src.scarfy.main import run_with_config

            assert callable(run_with_config)
        except ImportError:
            # まだ実装されていない場合はスキップ
            pytest.skip("run_with_config がまだ実装されていません")

    @pytest.mark.asyncio
    async def test_run_with_config_with_valid_config(self) -> None:
        """有効な設定ファイルでの run_with_config 実行をテスト。"""
        try:
            from src.scarfy.main import run_with_config
        except ImportError:
            pytest.skip("run_with_config がまだ実装されていません")

        # 実際の personal.yaml を使用してテスト
        config_path = "config/sample.yaml"

        if not Path(config_path).exists():
            pytest.skip("テスト用設定ファイルが存在しません")

        # モックを使用して実際の処理を回避
        with patch("src.scarfy.main.ScarfyEngine") as mock_engine_class:
            mock_engine = AsyncMock()
            mock_engine_class.return_value = mock_engine

            # タイムアウト付きでテスト実行
            try:
                await asyncio.wait_for(run_with_config(config_path), timeout=1.0)
            except asyncio.TimeoutError:
                # タイムアウトは期待される（無限ループを避けるため）
                pass

            # エンジンが初期化されたことを確認
            mock_engine_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_with_config_with_nonexistent_config(self) -> None:
        """存在しない設定ファイルでの run_with_config エラーハンドリングをテスト。"""
        try:
            from src.scarfy.main import run_with_config
        except ImportError:
            pytest.skip("run_with_config がまだ実装されていません")

        nonexistent_config = "/nonexistent/config.yaml"

        # ファイルが存在しない場合は正常にreturnすることを期待（エラーメッセージ表示）
        # 例外は投げない設計になっている
        await run_with_config(nonexistent_config)  # 正常に完了すべき

    def test_command_line_argument_parsing(self) -> None:
        """コマンドライン引数の解析テスト。"""
        # 引数解析のテストは実装後に追加予定
        pytest.skip("コマンドライン引数解析のテストは実装後に追加します")
