"""FileOperationsクラスのテストモジュール。

ファイル操作、検証、出力パス計算などの
機能のテストを提供します。
"""

from pathlib import Path
from unittest.mock import patch
import tempfile
import os

from src.scarfy.utils.file_operations import FileOperations


class TestFileOperations:
    """FileOperationsクラスのテストケース。"""

    def setup_method(self):
        """各テストメソッド実行前の初期化。"""
        self.file_ops = FileOperations()

    def test_validate_file_success(self):
        """ファイル検証の正常ケースをテスト。"""
        # テスト用一時ファイルを作成
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as temp_file:
            temp_file.write("print('Hello, World!')")
            temp_file_path = temp_file.name

        try:
            file_path = Path(temp_file_path)
            config = {
                "max_file_size": 1024 * 1024,  # 1MB
                "allowed_extensions": [".py", ".txt", ".md"],
            }

            result = self.file_ops.validate_file(file_path, config)

            assert result is True

        finally:
            os.unlink(temp_file_path)

    def test_validate_file_size_exceeded(self):
        """ファイルサイズ制限超過をテスト。"""
        # テスト用一時ファイルを作成
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as temp_file:
            temp_file.write("x" * 100)  # 100文字のファイル
            temp_file_path = temp_file.name

        try:
            file_path = Path(temp_file_path)
            config = {
                "max_file_size": 50,  # 50バイト制限
                "allowed_extensions": [".txt"],
            }

            result = self.file_ops.validate_file(file_path, config)

            assert isinstance(result, str)
            assert "ファイルサイズが制限を超えています" in result

        finally:
            os.unlink(temp_file_path)

    def test_validate_file_extension_not_allowed(self):
        """許可されていない拡張子をテスト。"""
        # テスト用一時ファイルを作成
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".exe", delete=False
        ) as temp_file:
            temp_file.write("dummy content")
            temp_file_path = temp_file.name

        try:
            file_path = Path(temp_file_path)
            config = {
                "max_file_size": 1024,
                "allowed_extensions": [".py", ".txt", ".md"],
            }

            result = self.file_ops.validate_file(file_path, config)

            assert isinstance(result, str)
            assert "許可されていないファイル拡張子です" in result
            assert ".exe" in result

        finally:
            os.unlink(temp_file_path)

    def test_validate_file_no_extension_restriction(self):
        """拡張子制限なしの場合をテスト。"""
        # テスト用一時ファイルを作成
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".xyz", delete=False
        ) as temp_file:
            temp_file.write("dummy content")
            temp_file_path = temp_file.name

        try:
            file_path = Path(temp_file_path)
            config = {
                "max_file_size": 1024
                # allowed_extensionsを指定しない
            }

            result = self.file_ops.validate_file(file_path, config)

            assert result is True

        finally:
            os.unlink(temp_file_path)

    def test_validate_file_stat_error(self):
        """ファイル情報取得エラーをテスト。"""
        # 存在しないファイルのパスを作成
        non_existent_file = Path("/non/existent/file.txt")
        config = {"max_file_size": 1024}

        result = self.file_ops.validate_file(non_existent_file, config)

        assert isinstance(result, str)
        assert "ファイル情報の取得に失敗しました" in result

    def test_read_file_safe_success(self):
        """ファイル読み込みの正常ケースをテスト。"""
        content = "Hello, World!\\nThis is a test file.\\n日本語テスト"

        # テスト用一時ファイルを作成
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", delete=False
        ) as temp_file:
            temp_file.write(content)
            temp_file_path = temp_file.name

        try:
            file_path = Path(temp_file_path)

            result = self.file_ops.read_file_safe(file_path)

            assert result == content

        finally:
            os.unlink(temp_file_path)

    def test_read_file_safe_unicode_error(self):
        """UnicodeDecodeErrorの処理をテスト。"""
        # バイナリデータでファイルを作成
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as temp_file:
            temp_file.write(b"\\xff\\xfe\\x00\\x00invalid utf-8")
            temp_file_path = temp_file.name

        try:
            file_path = Path(temp_file_path)

            result = self.file_ops.read_file_safe(file_path)

            # エラー処理付きで読み込まれ、何らかの内容が返される
            assert isinstance(result, str)
            assert len(result) > 0

        finally:
            os.unlink(temp_file_path)

    def test_read_file_safe_file_not_found(self):
        """FileNotFoundErrorの処理をテスト。"""
        non_existent_file = Path("/non/existent/file.txt")

        result = self.file_ops.read_file_safe(non_existent_file)

        assert "[ファイルが見つかりません:" in result

    @patch("builtins.open")
    def test_read_file_safe_permission_error(self, mock_open_func):
        """PermissionErrorの処理をテスト。"""
        mock_open_func.side_effect = PermissionError("Permission denied")

        file_path = Path("/some/file.txt")

        result = self.file_ops.read_file_safe(file_path)

        assert "[ファイル読み込み権限がありません:" in result

    @patch("builtins.open")
    def test_read_file_safe_general_error(self, mock_open_func):
        """一般的な例外の処理をテスト。"""
        mock_open_func.side_effect = IOError("Disk error")

        file_path = Path("/some/file.txt")

        result = self.file_ops.read_file_safe(file_path)

        assert "[ファイル読み込みエラー:" in result
        assert "Disk error" in result

    def test_calculate_output_paths_with_output_dir(self):
        """出力ディレクトリ指定ありのパス計算をテスト。"""
        input_file_path = "/input/document.md"
        config = {"output_dir": "/output", "output_suffix": "_processed"}

        result = self.file_ops.calculate_output_paths(input_file_path, config)

        expected_output_path = str(Path("/output/document_processed.md").absolute())
        expected_output_dir = str(Path("/output").absolute())

        assert result["output_path"] == expected_output_path
        assert result["output_dir"] == expected_output_dir
        assert result["output_name"] == "document_processed.md"
        assert result["output_basename"] == "document_processed"

    def test_calculate_output_paths_without_output_dir(self):
        """出力ディレクトリ指定なしのパス計算をテスト。"""
        input_file_path = "/input/document.md"
        config = {"output_suffix": "_reviewed"}

        result = self.file_ops.calculate_output_paths(input_file_path, config)

        expected_output_path = str(Path("/input/document_reviewed.md").absolute())
        expected_output_dir = str(Path("/input").absolute())

        assert result["output_path"] == expected_output_path
        assert result["output_dir"] == expected_output_dir
        assert result["output_name"] == "document_reviewed.md"
        assert result["output_basename"] == "document_reviewed"

    def test_calculate_output_paths_default_suffix(self):
        """デフォルト接尾辞でのパス計算をテスト。"""
        input_file_path = "/data/report.txt"
        config = {}  # output_suffixを指定しない

        result = self.file_ops.calculate_output_paths(input_file_path, config)

        expected_output_path = str(Path("/data/report.txt").absolute())

        assert result["output_path"] == expected_output_path
        assert result["output_name"] == "report.txt"
        assert result["output_basename"] == "report"

    def test_calculate_output_paths_empty_input(self):
        """空の入力ファイルパスでのパス計算をテスト。"""
        input_file_path = ""
        config = {"output_dir": "/output"}

        result = self.file_ops.calculate_output_paths(input_file_path, config)

        assert result["output_path"] == ""
        assert result["output_dir"] == ""
        assert result["output_name"] == ""
        assert result["output_basename"] == ""

    def test_calculate_output_paths_none_input(self):
        """None入力でのパス計算をテスト。"""
        input_file_path = None
        config = {"output_dir": "/output"}

        result = self.file_ops.calculate_output_paths(input_file_path, config)

        assert result["output_path"] == ""
        assert result["output_dir"] == ""
        assert result["output_name"] == ""
        assert result["output_basename"] == ""

    def test_calculate_output_paths_complex_extension(self):
        """複雑な拡張子でのパス計算をテスト。"""
        input_file_path = "/data/backup.tar.gz"
        config = {"output_dir": "/processed", "output_suffix": "_extracted"}

        result = self.file_ops.calculate_output_paths(input_file_path, config)

        expected_output_path = str(
            Path("/processed/backup.tar_extracted.gz").absolute()
        )

        assert result["output_path"] == expected_output_path
        assert result["output_name"] == "backup.tar_extracted.gz"
        assert result["output_basename"] == "backup.tar_extracted"

    def test_calculate_output_paths_no_extension(self):
        """拡張子なしファイルでのパス計算をテスト。"""
        input_file_path = "/data/README"
        config = {"output_dir": "/output", "output_suffix": "_updated"}

        result = self.file_ops.calculate_output_paths(input_file_path, config)

        expected_output_path = str(Path("/output/README_updated").absolute())

        assert result["output_path"] == expected_output_path
        assert result["output_name"] == "README_updated"
        assert result["output_basename"] == "README_updated"
