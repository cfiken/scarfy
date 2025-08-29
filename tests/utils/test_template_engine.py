"""TemplateEngineクラスのテストモジュール。

プロンプトテンプレートのプレースホルダー置換や
コンテキスト構築機能のテストを提供します。
"""

from pathlib import Path
from datetime import datetime
import tempfile
import os

from src.scarfy.utils.template_engine import TemplateEngine
from src.scarfy.core.events import Event


class TestTemplateEngine:
    """TemplateEngineクラスのテストケース。"""

    def setup_method(self):
        """各テストメソッド実行前の初期化。"""
        self.engine = TemplateEngine()

    def test_replace_placeholders_success(self):
        """プレースホルダーの正常な置換をテスト。"""
        template = "Hello {name}, you are {age} years old!"
        context = {"name": "Alice", "age": 25}

        result = self.engine.replace_placeholders(template, context)

        assert result == "Hello Alice, you are 25 years old!"

    def test_replace_placeholders_missing_key(self):
        """存在しないキーの処理をテスト。"""
        template = "Hello {name}, you are {missing_key} years old!"
        context = {"name": "Alice"}

        result = self.engine.replace_placeholders(template, context)

        assert result == "Hello Alice, you are {MISSING:missing_key} years old!"

    def test_replace_placeholders_special_characters(self):
        """特殊文字を含むプレースホルダーの処理をテスト。"""
        # スペースやコンマを含むプレースホルダー（現実的でない例）
        template = "File: {file_path} Status: {non_existent_key}"
        context = {"file_path": "/path/to/file.txt"}

        result = self.engine.replace_placeholders(template, context)

        # 存在するキーは置換され、存在しないキーはMISSINGになる
        expected = "File: /path/to/file.txt Status: {MISSING:non_existent_key}"
        assert result == expected

    def test_replace_placeholders_empty_template(self):
        """空のテンプレートをテスト。"""
        template = ""
        context = {"name": "Alice"}

        result = self.engine.replace_placeholders(template, context)

        assert result == ""

    def test_replace_placeholders_no_placeholders(self):
        """プレースホルダーがないテンプレートをテスト。"""
        template = "Hello world"
        context = {"name": "Alice"}

        result = self.engine.replace_placeholders(template, context)

        assert result == "Hello world"

    def test_build_context_basic(self):
        """基本的なコンテキスト構築をテスト。"""
        # 実際のEventオブジェクトを作成
        event = Event(
            id="test-build-context",
            type="manual_trigger",
            data={"user_input": "test", "timestamp": "2024-01-01"},
            timestamp=datetime.now(),
            source="test",
        )

        config = {}

        result = self.engine.build_context(event, config)

        assert result["user_input"] == "test"
        assert result["timestamp"] == "2024-01-01"
        assert result["event_type"] == "manual_trigger"

    def test_build_context_with_file_path(self):
        """ファイルパス情報を含むコンテキスト構築をテスト。"""
        # テスト用一時ファイルを作成
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as temp_file:
            temp_file.write("# Test Python file\\nprint('Hello')")
            temp_file_path = temp_file.name

        try:
            file_path = Path(temp_file_path)

            event = Event(
                id="test-file-context",
                type="file_change",
                data={"file_path": str(file_path)},
                timestamp=datetime.now(),
                source="test",
            )

            config = {}
            file_content = "# Test Python file\\nprint('Hello')"

            result = self.engine.build_context(event, config, file_path, file_content)

            assert result["file_name"] == file_path.stem
            assert result["file_extension"] == ".py"
            assert result["file_path"] == str(file_path.absolute())
            assert result["file_basename"] == file_path.name
            assert result["file_content"] == file_content
            assert result["event_type"] == "file_change"

        finally:
            # 一時ファイルを削除
            os.unlink(temp_file_path)

    def test_build_context_with_output_paths(self):
        """出力パス情報を含むコンテキスト構築をテスト。"""
        event = Event(
            id="test-output-paths",
            type="processing",
            data={"task": "process_file"},
            timestamp=datetime.now(),
            source="test",
        )

        config = {}
        output_paths = {
            "output_path": "/path/to/output.txt",
            "output_dir": "/path/to",
            "output_name": "output.txt",
            "output_basename": "output",
        }

        result = self.engine.build_context(event, config, None, None, output_paths)

        assert result["task"] == "process_file"
        assert result["event_type"] == "processing"
        assert result["output_path"] == "/path/to/output.txt"
        assert result["output_dir"] == "/path/to"
        assert result["output_name"] == "output.txt"
        assert result["output_basename"] == "output"

    def test_build_context_complete(self):
        """全ての情報を含む完全なコンテキスト構築をテスト。"""
        # テスト用一時ファイルを作成
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as temp_file:
            temp_file.write("# Test Markdown\\nThis is a test.")
            temp_file_path = temp_file.name

        try:
            file_path = Path(temp_file_path)

            event = Event(
                id="test-comprehensive-context",
                type="document_processing",
                data={
                    "file_path": str(file_path),
                    "user_id": "user123",
                    "priority": "high",
                },
                timestamp=datetime.now(),
                source="test",
            )

            config = {"max_size": 1024}
            file_content = "# Test Markdown\\nThis is a test."
            output_paths = {
                "output_path": "/output/test_processed.md",
                "output_dir": "/output",
                "output_name": "test_processed.md",
                "output_basename": "test_processed",
            }

            result = self.engine.build_context(
                event, config, file_path, file_content, output_paths
            )

            # イベントデータの確認
            assert result["user_id"] == "user123"
            assert result["priority"] == "high"

            # ファイル情報の確認
            assert result["file_extension"] == ".md"
            assert result["file_content"] == file_content

            # 出力パス情報の確認
            assert result["output_path"] == "/output/test_processed.md"

            # イベントタイプの確認
            assert result["event_type"] == "document_processing"

        finally:
            # 一時ファイルを削除
            os.unlink(temp_file_path)

    def test_build_context_no_file_info(self):
        """ファイル情報なしでのコンテキスト構築をテスト。"""
        event = Event(
            id="test-no-file-info",
            type="command",
            data={"command": "help"},
            timestamp=datetime.now(),
            source="test",
        )

        config = {"timeout": 30}

        result = self.engine.build_context(event, config)

        assert result["command"] == "help"
        assert result["event_type"] == "command"
        # ファイル関連の情報は含まれない
        assert "file_path" not in result
        assert "file_content" not in result
        assert "output_path" not in result
