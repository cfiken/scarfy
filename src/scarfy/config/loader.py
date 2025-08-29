"""設定ファイルとプロンプト読み込み機能。

このモジュールは、YAML設定ファイルと外部プロンプトファイルの読み込み機能を提供します。
環境変数の展開（~/や$HOME）もサポートします。
"""

import os
from pathlib import Path
from typing import Dict, Any
import yaml


class ConfigLoader:
    """設定ファイルとプロンプトの読み込み機能を提供するクラス。"""

    def load_prompt_from_file(self, prompt_path: Path) -> str:
        """プロンプトファイルを読み込み、内容を文字列として返す。

        Args:
            prompt_path: 読み込むプロンプトファイルのパス

        Returns:
            プロンプトファイルの内容

        Raises:
            FileNotFoundError: ファイルが存在しない場合
            UnicodeDecodeError: ファイルのエンコーディングが不正な場合
        """
        if not prompt_path.exists():
            raise FileNotFoundError(
                f"プロンプトファイルが見つかりません: {prompt_path}"
            )

        return prompt_path.read_text(encoding="utf-8")

    def load_config(self, config_path: Path) -> Dict[str, Any]:
        """YAML設定ファイルを読み込み、設定辞書として返す。

        Args:
            config_path: 読み込む設定ファイルのパス

        Returns:
            設定内容の辞書

        Raises:
            FileNotFoundError: ファイルが存在しない場合
            yaml.YAMLError: YAML形式が不正な場合
        """
        if not config_path.exists():
            raise FileNotFoundError(f"設定ファイルが見つかりません: {config_path}")

        content = config_path.read_text(encoding="utf-8")
        result = yaml.safe_load(content)

        # yaml.safe_load は None や基本型も返す可能性があるので、辞書であることを保証
        if not isinstance(result, dict):
            return {}

        return result

    def expand_env_vars(self, text: str) -> str:
        """文字列内の環境変数を展開する（~/や$HOME等）。

        Args:
            text: 展開対象の文字列

        Returns:
            環境変数が展開された文字列
        """
        # ~ を $HOME に展開
        if text.startswith("~"):
            text = text.replace("~", os.path.expanduser("~"), 1)

        # $変数を環境変数に展開
        return os.path.expandvars(text)
