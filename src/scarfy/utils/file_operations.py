"""ファイル操作ユーティリティ。

ファイルの読み込み、検証、出力パス計算などの
ファイル関連操作を担当します。
"""

from pathlib import Path
from typing import Dict, Any, Union


class FileOperations:
    """ファイル関連の操作を担当するクラス。

    ファイルのセキュリティ検証、安全な読み込み、
    出力パス計算などの機能を提供します。
    """

    def validate_file(
        self, file_path: Path, config: Dict[str, Any]
    ) -> Union[bool, str]:
        """ファイルのセキュリティ検証。

        ファイルサイズと拡張子の制限をチェックします。

        Args:
            file_path: 検証するファイルのPath
            config: 検証設定（max_file_size, allowed_extensions）

        Returns:
            True（検証成功）またはエラーメッセージ文字列
        """
        # ファイルサイズチェック
        max_size = config.get("max_file_size", 1048576)  # 1MB
        try:
            file_size = file_path.stat().st_size
            if file_size > max_size:
                return f"ファイルサイズが制限を超えています: {file_size} > {max_size} バイト"
        except OSError as e:
            return f"ファイル情報の取得に失敗しました: {e}"

        # ファイル拡張子チェック
        allowed_extensions = config.get("allowed_extensions")
        if allowed_extensions:
            file_extension = file_path.suffix.lower()
            allowed_ext_lower = [ext.lower() for ext in allowed_extensions]
            if file_extension not in allowed_ext_lower:
                return f"許可されていないファイル拡張子です: {file_extension}"

        return True

    def read_file_safe(self, file_path: Path) -> str:
        """ファイル内容を安全に読み込み。

        UTF-8エンコーディングで読み込みを試行し、
        失敗した場合はエラー処理付きで再試行します。

        Args:
            file_path: 読み込むファイルのPath

        Returns:
            ファイル内容の文字列、またはエラーメッセージ
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            # エンコーディングエラーの場合、エラー文字を置換して読み込み
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    return f.read()
            except Exception as e:
                return f"[ファイル読み込みエラー（エンコーディング問題）: {file_path}, {e}]"
        except FileNotFoundError:
            return f"[ファイルが見つかりません: {file_path}]"
        except PermissionError:
            return f"[ファイル読み込み権限がありません: {file_path}]"
        except Exception as e:
            return f"[ファイル読み込みエラー: {file_path}, {e}]"

    def calculate_output_paths(
        self, input_file_path: str, config: Dict[str, Any]
    ) -> Dict[str, str]:
        """出力パス関連の情報を計算。

        入力ファイルパスと設定から、出力先の各種パス情報を計算します。

        Args:
            input_file_path: 入力ファイルのパス
            config: 出力設定（output_dir, output_suffix）

        Returns:
            出力パス関連の辞書:
            - output_path: 出力ファイルの完全パス
            - output_dir: 出力ディレクトリ
            - output_name: 出力ファイル名（拡張子含む）
            - output_basename: 出力ファイル名（拡張子なし）
        """
        if not input_file_path:
            return {
                "output_path": "",
                "output_dir": "",
                "output_name": "",
                "output_basename": "",
            }

        input_path = Path(input_file_path)

        # 出力ディレクトリの決定
        output_dir = config.get("output_dir")
        if output_dir:
            output_dir_path = Path(output_dir)
        else:
            # 出力ディレクトリが未指定の場合は入力ファイルと同じディレクトリ
            output_dir_path = input_path.parent
        # 出力ファイル名の決定
        output_suffix = config.get("output_suffix", "")
        output_name = f"{input_path.stem}{output_suffix}{input_path.suffix}"

        # 完全な出力パス
        output_path = output_dir_path / output_name

        return {
            "output_path": str(output_path.absolute()),
            "output_dir": str(output_dir_path.absolute()),
            "output_name": output_name,
            "output_basename": f"{input_path.stem}{output_suffix}",
        }
