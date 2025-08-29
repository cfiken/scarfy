"""新規作成ファイルの内容を標準出力に表示するエージェント。

このモジュールは、ファイル作成イベントを受信し、そのファイルの内容を
標準出力に表示するエージェントを提供します。主な用途：
- ファイル作成の監視とログ出力
- 開発時のファイル変更確認
- 自動化ワークフローでのファイル内容検証

FilePrintAgentは安全性を考慮し、大きなファイルやバイナリファイルの
読み込みを制限します。
"""

from pathlib import Path
from typing import Dict, Any

from ..core.interfaces import Agent
from ..core.events import Event
from ..utils.logger import get_logger


class FilePrintAgent(Agent):
    """新規作成されたファイルの内容を標準出力に表示するエージェント。

    ファイル作成イベントを受信し、そのファイルの内容を読み込んで
    標準出力に表示します。安全性のため、ファイルサイズとタイプの
    チェックを行います。

    設定オプション:
        max_size (int): 読み込む最大ファイルサイズ（バイト）（デフォルト: 1048576 = 1MB）
        encoding (str): ファイルエンコーディング（デフォルト: 'utf-8'）
        show_path (bool): ファイルパスも表示するか（デフォルト: True）
        show_size (bool): ファイルサイズも表示するか（デフォルト: True）

    設定例:
        {
            "type": "file_print",
            "max_size": 524288,  # 512KB
            "encoding": "utf-8",
            "show_path": True,
            "show_size": False
        }

    出力例:
        {
            "agent": "FilePrintAgent",
            "action": "file_content_displayed",
            "file_path": "/path/to/file.txt",
            "file_size": 1234,
            "encoding": "utf-8",
            "content_displayed": True,
            "processing_time": "2024-01-01T12:00:01"
        }
    """

    async def process(self, event: Event, config: Dict[str, Any]) -> Dict[str, Any]:
        """ファイル作成イベントを処理し、ファイル内容を標準出力に表示。

        イベントからファイルパスを取得し、ファイルが存在して読み込み可能な場合に
        その内容を標準出力に表示します。安全性のためサイズとエンコーディングを
        チェックします。

        Args:
            event: 処理するEvent オブジェクト（file_created アクション想定）
            config: このエージェントの設定辞書

        Returns:
            処理結果を含む辞書:
            - agent: エージェント名
            - action: 実行されたアクション
            - file_path: 処理されたファイルのパス
            - file_size: ファイルサイズ（バイト）
            - encoding: 使用されたエンコーディング
            - content_displayed: 内容が表示されたかどうか
            - error: エラーが発生した場合のメッセージ
            - processing_time: 処理時刻のISO形式文字列

        例:
            >>> event = Event(id="123", type="file_change",
            ...               data={"action": "file_created", "file_path": "/tmp/test.txt"})
            >>> config = {"max_size": 1024, "encoding": "utf-8"}
            >>> result = await agent.process(event, config)
            >>> print(result["content_displayed"])
            True
        """
        from datetime import datetime

        # 設定値の取得
        max_size = config.get("max_size", 1048576)  # 1MB
        encoding = config.get("encoding", "utf-8")
        show_path = config.get("show_path", True)
        show_size = config.get("show_size", True)

        # 基本的な結果辞書を作成
        result = {
            "agent": "FilePrintAgent",
            "action": "file_content_displayed",
            "trigger_action": event.data.get(
                "action", "unknown"
            ),  # どのイベントで呼ばれたかを記録
            "file_path": None,
            "file_size": None,
            "encoding": encoding,
            "content_displayed": False,
            "processing_time": datetime.now().isoformat(),
        }

        try:
            # イベントデータからファイルパスを取得
            file_path = event.data.get("file_path")
            if not file_path:
                result["error"] = "ファイルパスがイベントデータに含まれていません"
                return result

            result["file_path"] = file_path
            file_path_obj = Path(file_path)

            # ファイルの存在確認
            if not file_path_obj.exists():
                result["error"] = f"ファイルが存在しません: {file_path}"
                return result

            # ファイルが通常ファイルかチェック
            if not file_path_obj.is_file():
                result["error"] = f"ディレクトリまたは特殊ファイルです: {file_path}"
                return result

            # ファイルサイズをチェック
            file_size = file_path_obj.stat().st_size
            result["file_size"] = file_size

            if file_size > max_size:
                result["error"] = (
                    f"ファイルサイズが制限を超えています: {file_size} > {max_size} バイト"
                )
                return result

            # ファイル内容を読み込み
            try:
                with open(file_path_obj, "r", encoding=encoding) as f:
                    content = f.read()
            except UnicodeDecodeError:
                result["error"] = (
                    f"ファイルを {encoding} エンコーディングで読み込めません（バイナリファイルの可能性）"
                )
                return result
            except PermissionError:
                result["error"] = f"ファイルの読み込み権限がありません: {file_path}"
                return result

            # 標準出力に表示
            logger = get_logger(__name__)
            trigger_action = result["trigger_action"]
            logger.info(
                "ファイル表示: %s (ファイル: %s, サイズ: %sバイト)",
                trigger_action,
                file_path,
                file_size,
            )

            print("=" * 60)
            print(f"🔔 トリガー: {trigger_action}")
            if show_path:
                print(f"📄 ファイル: {file_path}")
            if show_size:
                print(f"📊 サイズ: {file_size} バイト")
            print("=" * 60)
            print(content)
            print("=" * 60)

            result["content_displayed"] = True

        except Exception as e:
            result["error"] = f"予期しないエラー: {str(e)}"

        return result
