"""プロンプトローダーのテスト。

このモジュールは、外部ファイルからプロンプトを読み込む機能のテストを提供します。
主に以下の機能をテストします：
- プロンプトファイルの読み込み
- ファイル未存在エラーのハンドリング
- エンコーディングエラーのハンドリング
"""

import pytest
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

from scarfy.config.loader import ConfigLoader


class TestPromptLoader:
    """プロンプトローダーのテストクラス。"""

    def setup_method(self) -> None:
        """各テストメソッドの前に実行される初期化処理。"""
        self.loader = ConfigLoader()

    def test_load_prompt_from_file(self) -> None:
        """プロンプトファイルを正常に読み込めることをテスト。"""
        test_prompt = """これはテスト用のプロンプトです。
複数行にわたって記述されています。

テンプレート変数: {file_path}
ファイル内容: {file_content}
"""

        with NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(test_prompt)
            f.flush()

            # ファイルパスを使用してプロンプトを読み込み
            result = self.loader.load_prompt_from_file(Path(f.name))

            assert result == test_prompt

            # クリーンアップ
            Path(f.name).unlink()

    def test_prompt_file_not_found(self) -> None:
        """存在しないプロンプトファイルに対する適切なエラーハンドリングをテスト。"""
        non_existent_path = Path("/non/existent/prompt.md")

        with pytest.raises(FileNotFoundError):
            self.loader.load_prompt_from_file(non_existent_path)

    def test_prompt_file_empty(self) -> None:
        """空のプロンプトファイルを読み込む場合をテスト。"""
        with NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            # 空ファイルを作成
            f.flush()

            result = self.loader.load_prompt_from_file(Path(f.name))
            assert result == ""

            # クリーンアップ
            Path(f.name).unlink()

    def test_prompt_file_with_different_encodings(self) -> None:
        """異なるエンコーディングのプロンプトファイルを読み込むテスト。"""
        test_prompt_japanese = "これは日本語のテストプロンプトです。\n特殊文字: 「」・…"

        with NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(test_prompt_japanese)
            f.flush()

            result = self.loader.load_prompt_from_file(Path(f.name))
            assert result == test_prompt_japanese

            # クリーンアップ
            Path(f.name).unlink()

    def test_prompt_directory_structure(self) -> None:
        """プロンプトディレクトリ構造内のファイル読み込みをテスト。"""
        test_prompt = "ディレクトリ内のプロンプト"

        with TemporaryDirectory() as temp_dir:
            prompts_dir = Path(temp_dir) / "prompts"
            prompts_dir.mkdir()

            prompt_file = prompts_dir / "test_prompt.md"
            prompt_file.write_text(test_prompt, encoding="utf-8")

            result = self.loader.load_prompt_from_file(prompt_file)
            assert result == test_prompt
