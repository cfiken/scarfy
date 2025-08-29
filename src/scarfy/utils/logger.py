"""Scarfy統一ロギング設定。

このモジュールは、Scarfyプロジェクト全体で一貫したロギングを提供します。
Python標準のloggingモジュールを使用し、シンプルで理解しやすい設定を提供します。
"""

import logging
import sys
from typing import Optional


def setup_logger(
    name: Optional[str] = None,
    level: str = "INFO",
    format_string: Optional[str] = None
) -> logging.Logger:
    """Scarfy用の統一ロガー設定。

    Args:
        name: ロガーの名前（モジュール名を推奨、省略時は'scarfy'）
        level: ログレベル ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
        format_string: カスタムフォーマット文字列

    Returns:
        設定済みのロガー

    Example:
        >>> from scarfy.utils.logger import setup_logger
        >>> logger = setup_logger(__name__)
        >>> logger.info("アプリケーション開始")
        >>> logger.debug("デバッグ情報: user_id=%s", 123)
    """
    logger_name = name or 'scarfy'
    logger = logging.getLogger(logger_name)
    
    # 既にハンドラーが設定されている場合はスキップ
    if logger.handlers:
        return logger
    
    # ログレベルを設定
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(numeric_level)
    
    # コンソールハンドラーを作成
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    
    # フォーマッターを設定
    if format_string is None:
        # デフォルトフォーマット: 見やすい日本語対応
        format_string = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    
    formatter = logging.Formatter(
        format_string,
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(formatter)
    
    # ハンドラーをロガーに追加
    logger.addHandler(console_handler)
    
    # 親ロガーへの伝播を防ぐ（重複ログ出力を避ける）
    logger.propagate = False
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """指定された名前のロガーを取得。

    Args:
        name: ロガー名（通常は __name__ を使用）

    Returns:
        ロガーインスタンス（未設定の場合は自動設定）

    Example:
        >>> from scarfy.utils.logger import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("処理開始 file_path=%s", "/tmp/file.txt")
    """
    logger = logging.getLogger(name)
    
    # まだ設定されていない場合は自動設定
    if not logger.handlers:
        return setup_logger(name)
    
    return logger


# デフォルトロガー（アプリケーション全体用）
def get_default_logger() -> logging.Logger:
    """デフォルトロガーを取得。

    Returns:
        'scarfy'名のデフォルトロガー
    """
    return get_logger('scarfy')


def init_logging(level: str = "INFO") -> None:
    """アプリケーション開始時のロギング初期化。

    Args:
        level: ログレベル
    """
    # ルートロガーの設定をクリア
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    
    # デフォルトロガーを設定
    setup_logger('scarfy', level=level)