"""ConfigLoaderのテスト。

このモジュールは、YAML設定ファイル読み込みと環境変数展開機能のテストを提供します。
"""

import os
import pytest
import tempfile
from pathlib import Path

from scarfy.config.loader import ConfigLoader


class TestConfigLoader:
    """ConfigLoaderのテストクラス。"""

    def setup_method(self) -> None:
        """各テストメソッドの前に実行される初期化処理。"""
        self.loader = ConfigLoader()

    def test_load_config_yaml_valid(self) -> None:
        """有効なYAML設定ファイルを正常に読み込めることをテスト。"""
        test_config = """
workflows:
  - name: "test_workflow"
    trigger:
      type: "file_watcher"
      path: "/tmp"
    agent:
      type: "claude_code"
      timeout: 300
    output:
      type: "console"

settings:
  log_level: "INFO"
  debug: true
"""

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            f.write(test_config)
            f.flush()

            result = self.loader.load_config(Path(f.name))

            # 期待される構造を検証
            assert "workflows" in result
            assert "settings" in result
            assert len(result["workflows"]) == 1
            assert result["workflows"][0]["name"] == "test_workflow"
            assert result["settings"]["log_level"] == "INFO"
            assert result["settings"]["debug"] is True

            # クリーンアップ
            Path(f.name).unlink()

    def test_load_config_yaml_file_not_found(self) -> None:
        """存在しない設定ファイルに対する適切なエラーハンドリングをテスト。"""
        non_existent_path = Path("/non/existent/config.yaml")

        with pytest.raises(FileNotFoundError):
            self.loader.load_config(non_existent_path)

    def test_load_config_yaml_invalid_syntax(self) -> None:
        """不正なYAML構文に対するエラーハンドリングをテスト。"""
        invalid_yaml = """
workflows:
  - name: "test"
    trigger:
      type: file_watcher
    # 不正なインデント
  missing_key:
value_without_key
"""

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            f.write(invalid_yaml)
            f.flush()

            with pytest.raises(Exception):  # yaml.YAMLError or similar
                self.loader.load_config(Path(f.name))

            # クリーンアップ
            Path(f.name).unlink()

    def test_load_config_yaml_empty_file(self) -> None:
        """空のYAMLファイルを読み込む場合をテスト。"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            # 空ファイルを作成
            f.flush()

            result = self.loader.load_config(Path(f.name))
            assert result == {}

            # クリーンアップ
            Path(f.name).unlink()

    def test_expand_env_vars_tilde(self) -> None:
        """チルダ（~）の環境変数展開をテスト。"""
        home_dir = os.path.expanduser("~")

        test_cases = [
            ("~/Documents", f"{home_dir}/Documents"),
            ("~/Downloads/test.txt", f"{home_dir}/Downloads/test.txt"),
            ("/absolute/path", "/absolute/path"),  # 絶対パスは変更されない
            ("relative/path", "relative/path"),  # 相対パスは変更されない
        ]

        for input_path, expected in test_cases:
            result = self.loader.expand_env_vars(input_path)
            assert result == expected

    def test_expand_env_vars_environment_variables(self) -> None:
        """$変数の環境変数展開をテスト。"""
        # テスト用環境変数を設定
        os.environ["TEST_SCARFY_VAR"] = "/test/path"

        try:
            test_cases = [
                ("$TEST_SCARFY_VAR/subfolder", "/test/path/subfolder"),
                ("${TEST_SCARFY_VAR}/file.txt", "/test/path/file.txt"),
                ("$HOME/Documents", f"{os.environ.get('HOME', '')}/Documents"),
                ("no_env_var_here", "no_env_var_here"),  # 環境変数なしは変更されない
            ]

            for input_path, expected in test_cases:
                result = self.loader.expand_env_vars(input_path)
                assert result == expected

        finally:
            # クリーンアップ
            if "TEST_SCARFY_VAR" in os.environ:
                del os.environ["TEST_SCARFY_VAR"]

    def test_expand_env_vars_combined(self) -> None:
        """チルダと$変数の組み合わせをテスト。"""
        home_dir = os.path.expanduser("~")

        # まず ~ を展開し、その後 $HOME を展開
        result = self.loader.expand_env_vars("~/test/$USER/folder")
        expected_user = os.environ.get(
            "USER", "$USER"
        )  # $USERが存在しない場合はそのまま
        expected = f"{home_dir}/test/{expected_user}/folder"

        assert result == expected

    def test_load_config_with_japanese_content(self) -> None:
        """日本語を含むYAML設定ファイルの読み込みをテスト。"""
        japanese_config = """
workflows:
  - name: "会議録処理"
    trigger:
      type: "file_watcher" 
      path: "~/ダウンロード"
    agent:
      type: "claude_code"
      prompt: "会議の内容を要約してください"
    output:
      type: "console"
      prefix: "[会議]"
"""

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            f.write(japanese_config)
            f.flush()

            result = self.loader.load_config(Path(f.name))

            assert result["workflows"][0]["name"] == "会議録処理"
            assert (
                result["workflows"][0]["agent"]["prompt"]
                == "会議の内容を要約してください"
            )
            assert result["workflows"][0]["output"]["prefix"] == "[会議]"

            # クリーンアップ
            Path(f.name).unlink()
