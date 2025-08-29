"""テンプレート処理エンジン。

プロンプトテンプレートのプレースホルダー置換や、
テンプレート用コンテキストの構築を担当します。
"""

from pathlib import Path
from typing import Dict, Any, Optional

from ..core.events import Event


class TemplateEngine:
    """プロンプトテンプレートの処理を担当するクラス。

    {key} 形式のプレースホルダーを含むテンプレート文字列を、
    イベントデータやファイル情報で動的に置換します。

    利用可能なプレースホルダー:
        - {file_name}: ファイル名（拡張子なし）
        - {file_extension}: ファイル拡張子（.を含む）
        - {file_path}: 完全なファイルパス
        - {file_basename}: ファイル名（拡張子含む）
        - {file_content}: ファイル内容
        - {event_type}: イベントタイプ
        - {output_path}: 出力ファイルの完全パス
        - {output_dir}: 出力ディレクトリ
        - {output_name}: 出力ファイル名（拡張子含む）
        - {output_basename}: 出力ファイル名（拡張子なし）
        - その他event.dataの任意のキー
    """

    def replace_placeholders(self, template: str, context: Dict[str, Any]) -> str:
        """テンプレート内のプレースホルダーを置換。

        {key} 形式のプレースホルダーをコンテキストの値で置換します。
        存在しないキーが指定された場合は、{MISSING:key} 形式で残します。

        Args:
            template: プレースホルダーを含むテンプレート文字列
            context: 置換に使用する辞書

        Returns:
            プレースホルダーが置換された文字列
        """
        import re

        def replacement_func(match: Any) -> str:
            key = match.group(1)
            if key in context:
                return str(context[key])
            else:
                return f"{{MISSING:{key}}}"

        try:
            # {key}形式のプレースホルダーを全て見つけて置換
            result = re.sub(r"\{([^}]+)\}", replacement_func, template)
            return result
        except Exception:
            # その他のエラーの場合、元のテンプレートを返す
            return template

    def build_context(
        self,
        event: Event,
        config: Dict[str, Any],
        file_path: Optional[Path] = None,
        file_content: Optional[str] = None,
        output_paths: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """テンプレート置換用のコンテキストを構築。

        イベントデータ、ファイル情報、出力パス情報をマージして、
        テンプレート置換に使用できる統合されたコンテキスト辞書を作成します。

        Args:
            event: イベントオブジェクト
            config: エージェント設定
            file_path: ファイルパス（オプション）
            file_content: ファイル内容（オプション、file_pathが指定された場合に使用）
            output_paths: 出力パス情報の辞書（オプション）

        Returns:
            テンプレート置換に使用できるコンテキスト辞書
        """
        # イベントデータをベースにする
        context = dict(event.data)

        # ファイルパス関連の情報を追加
        if file_path:
            context.update(
                {
                    "file_name": file_path.stem,  # 拡張子なしファイル名
                    "file_extension": file_path.suffix,  # 拡張子（.含む）
                    "file_path": str(file_path.absolute()),  # 絶対パス
                    "file_basename": file_path.name,  # ファイル名（拡張子含む）
                }
            )

            # ファイル内容が提供されている場合は追加
            if file_content is not None:
                context["file_content"] = file_content

        # イベントタイプを追加
        context["event_type"] = event.type

        # 出力パス情報を追加
        if output_paths:
            context.update(output_paths)

        return context
