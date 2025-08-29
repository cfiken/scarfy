"""デバッグと開発用のコンソール出力。

結果をコンソール/stdoutに印刷する出力を提供します。
以下の用途に有用です：
- ワークフローの開発とデバッグ
- 外部依存なしの簡単テスト
- ターミナルへのシンプルログ記録
- ワークフロー実行のリアルタイム監視

出力はJSONを美しくフォーマットしたり、コンパクトな出力を印刷したりするよう設定できます。
"""

import json
from typing import Dict, Any
from ..core.interfaces import Output


class ConsoleOutput(Output):
    """結果をコンソール/stdoutに印刷する出力。

    この出力はワークフロー実行について即座に視觚的なフィードバックを
    提供するため、開発とデバッグ中に有用です。出力は美しく印刷された
    JSONまたはコンパクトな単一行JSONとしてフォーマットできます。

    設定オプション:
        prefix (str): 各出力行の前に付けるテキスト（デフォルト: "[SCARFY]"）
        pretty (bool): JSONをインデント付きでフォーマットするか（デフォルト: True）
        timestamp (bool): 出力にタイムスタンプを含めるか（デフォルト: False）
        color (bool): 色付き出力を使用するか（デフォルト: False）

    設定例:
        {
            "type": "console",
            "prefix": "[WORKFLOW]",
            "pretty": True,
            "timestamp": True
        }

    出力例:
        [WORKFLOW] 2024-01-01 12:00:00 {
          "status": "success",
          "message": "File processed",
          "file_path": "/tmp/test.txt"
        }
    """

    async def send(self, data: Dict[str, Any], config: Dict[str, Any]) -> None:
        """オプションのフォーマットでデータをコンソールに印刷。

        データをJSONとしてフォーマットし、stdoutに印刷します。出力は
        様々なフォーマットオプションでカスタマイズできます。

        Args:
            data: エージェントからの結果を含む辞書
            config: 出力フォーマットの設定辞書

        設定キー:
            prefix (str): 出力の前に付けるテキスト（デフォルト: "[SCARFY]"）
            pretty (bool): 美しく印刷されたJSONを使用（デフォルト: True）
            timestamp (bool): タイムスタンプを含める（デフォルト: False）
            color (bool): 色付き出力を使用（デフォルト: False）

        例:
            >>> data = {"status": "success", "file": "test.txt"}
            >>> config = {"prefix": "[DEMO]", "pretty": True}
            >>> await output.send(data, config)
            [DEMO] {
              "status": "success",
              "file": "test.txt"
            }
        """
        prefix = config.get("prefix", "[SCARFY]")

        # データをJSONとしてフォーマット
        if config.get("pretty", True):
            output = json.dumps(data, indent=2, ensure_ascii=False, default=str)
        else:
            output = json.dumps(data, ensure_ascii=False, default=str)

        # オプションでタイムスタンプを追加
        if config.get("timestamp", False):
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            prefix = f"{prefix} {timestamp}"

        # コンソールに印刷
        if config.get("pretty", True) and "\n" in output:
            # 複数行出力: プレフィックスを別行で印刷
            print(f"{prefix}")
            print(output)
        else:
            # 単一行出力: プレフィックスとデータを一緒に印刷
            print(f"{prefix} {output}")
