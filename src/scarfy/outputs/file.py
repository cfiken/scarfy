"""永続的なログ記録とデータストレージ用のファイル出力。

結果をディスク上のファイルに書き込む出力を提供します。
以下の用途に有用です：
- ワークフロー結果の永続的なログ記録
- 自動化アクティビティの監査証跡作成
- 後の分析のための処理済みデータの保存
- ワークフロー出力からのデータセット構築

出力は既存ファイルに追記したり上書きしたりでき、必要に応じて
ディレクトリ構造を自動作成します。
"""

import json
import aiofiles
from pathlib import Path
from typing import Dict, Any
from datetime import datetime
from ..core.interfaces import Output


class FileOutput(Output):
    """結果をディスク上のファイルに書き込む出力。

    この出力はファイルに書き込むことでワークフロー結果の永続的な
    ストレージを提供します。自動化ワークフローからのログ、監査証跡、
    データセットの作成に有用です。

    出力はディレクトリ構造を自動作成し、既存ファイルに追記したり
    上書きしたりできます。各出力エントリにはタイムスタンプと
    元のデータが含まれます。

    設定オプション:
        path (str): 書き込み先ファイルパス（デフォルト: "output.json"）
        append (bool): 既存ファイルに追記するか（デフォルト: True）
        format (str): 出力フォーマット - "json"または"jsonl"（デフォルト: "json"）
        include_timestamp (bool): 出力にタイムスタンプを含めるか（デフォルト: True）
        pretty (bool): JSON出力を美しくフォーマットするか（デフォルト: False）

    設定例:
        {
            "type": "file",
            "path": "/var/log/scarfy/workflow.jsonl",
            "append": True,
            "format": "jsonl",
            "pretty": False
        }

    ファイルフォーマット:
        include_timestamp=True（デフォルト）の場合:
        {
          "timestamp": "2024-01-01T12:00:00",
          "data": { ... 元のエージェント出力 ... }
        }

        include_timestamp=Falseの場合:
        { ... 元のエージェント出力 ... }
    """

    async def send(self, data: Dict[str, Any], config: Dict[str, Any]) -> None:
        """設定されたファイルにデータを書き込み。

        対象ディレクトリが存在しない場合は作成し、設定に従ってデータを
        フォーマットし、ファイルに書き込みます。

        Args:
            data: エージェントからの結果を含む辞書
            config: ファイル出力の設定辞書

        設定キー:
            path (str): 対象ファイルパス（デフォルト: "output.json"）
            append (bool): 既存ファイルに追記（デフォルト: True）
            format (str): "json"または"jsonl"フォーマット（デフォルト: "json"）
            include_timestamp (bool): タイムスタンプラッパーを追加（デフォルト: True）
            pretty (bool): JSONを美しく印刷（デフォルト: False）

        Raises:
            OSError: ファイルを作成または書き込みできない場合

        例:
            >>> data = {"status": "success", "file": "test.txt"}
            >>> config = {
            ...     "path": "/tmp/results.jsonl",
            ...     "append": True,
            ...     "format": "jsonl"
            ... }
            >>> await output.send(data, config)
        """
        output_path = Path(config.get("path", "output.json"))

        # ディレクトリの存在を確認
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 出力データを準備
        if config.get("include_timestamp", True):
            output_data = {"timestamp": datetime.now().isoformat(), "data": data}
        else:
            output_data = data

        # ファイルモードを決定
        mode = "a" if config.get("append", True) else "w"

        # 設定に基づいて出力をフォーマット
        output_format = config.get("format", "json").lower()
        pretty = config.get("pretty", False)

        if pretty and output_format == "json":
            output_text = json.dumps(
                output_data, indent=2, ensure_ascii=False, default=str
            )
        else:
            output_text = json.dumps(output_data, ensure_ascii=False, default=str)

        # ファイルに書き込み
        async with aiofiles.open(str(output_path), mode=mode, encoding="utf-8") as f:  # type: ignore
            if mode == "a" and output_format == "jsonl":
                # JSONLフォーマット: 1行に1つのJSONオブジェクト
                await f.write(output_text + "\n")
            elif mode == "a":
                # JSONフォーマット: エントリを改行で区切る
                await f.write("\n" + output_text)
            else:
                # 上書きモード: データをそのまま書き込み
                await f.write(output_text)
                if output_format == "jsonl":
                    await f.write("\n")
