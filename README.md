# Scarfy - Agent Automation Framework

シンプルなイベント駆動の自動化フレームワークです。ファイル変更やコマンド実行をトリガーにして、エージェント処理を自動実行できます。

## 構成

- **Trigger**: イベントを検知 (ファイル監視、手動実行)
- **Agent**: イベントを処理 (Echo、Claude Code統合など)
- **Output**: 結果を出力 (コンソール、ファイル)

## 使用方法

### インストール

```bash
uv sync
```

### 実行方法

#### 設定ファイルベース実行 (推奨)
```bash
uv run scarfy --config config/sample.yaml
```

#### 手動トリガーモード
```bash
uv run scarfy --manual
```

## 設定ファイル

ワークフローはYAMLファイルで定義できます。`config/sample.yaml`を参考にしてください：

```yaml
workflows:
  - name: "meeting_notes_workflow"
    trigger:
      type: "file_watcher"
      event_type: "mtgs_file_change"
      path: "~/Downloads"
      recursive: false
      filename_patterns: ["*_Meet_*.txt"]
      watch_events: ["created", "modified"]
      debounce_delay: 10.0
    agent:
      type: "claude_code"
      prompt_file: "prompts/meeting_summary.md"
      timeout: 600
      max_file_size: 10485760  # 10MB
      allowed_extensions: [".txt"]
      output_dir: "~/Documents/obsidian-cfiken/meeting_notes"
      # デバッグ用設定
      verbose: true  # Claude Code CLIの詳細ログを有効化
      show_realtime_output: true  # リアルタイム出力を表示
    output:
      type: "console"
      prefix: "[DOCS-REVIEW]"
      pretty: true
      timestamp: true
```

## エージェント設定

### ClaudeCodeAgent
Claude Code CLIを使用してファイル処理を自動化するエージェントです。

#### 基本設定
```yaml
agent:
  type: "claude_code"
  prompt_file: "prompts/your_prompt.md"  # 外部プロンプトファイル
  timeout: 300  # 実行タイムアウト（秒）
  max_file_size: 1048576  # 最大ファイルサイズ（1MB）
  allowed_extensions: [".py", ".js", ".md"]  # 許可する拡張子
```

#### デバッグ設定
```yaml
agent:
  type: "claude_code"
  verbose: true  # --verbose --output-format stream-json フラグを有効化
  show_realtime_output: true  # Claude Codeの出力をリアルタイム表示
```

#### MCP統合
```yaml
agent:
  type: "claude_code"
  mcp_servers: ["arxiv-mcp-server"]  # 使用するMCPサーバー
  additional_tools: ["Bash", "WebSearch"]  # 追加ツール
```

## プロンプトテンプレート

プロンプトファイルでは以下の変数が利用可能です：

- `{file_name}`: ファイル名（拡張子なし）
- `{file_extension}`: ファイル拡張子
- `{file_path}`: 完全なファイルパス
- `{file_content}`: ファイル内容
- `{event_type}`: イベントタイプ
- その他のイベントデータ

## 拡張方法

### 新しいAgent追加
`src/scarfy/agents/` に新しいファイルを作成し、`Agent`インターフェースを実装してください。

### 新しいOutput追加
`src/scarfy/outputs/` に新しいファイルを作成し、`Output`インターフェースを実装してください。

## プロジェクト構造

```
scarfy/
├── src/scarfy/
│   ├── agents/          # エージェント実装
│   │   ├── claude_code.py    # Claude Code CLI統合
│   │   ├── echo.py           # シンプルなエコーエージェント
│   │   └── file_print.py     # ファイル出力エージェント
│   ├── config/          # 設定管理
│   │   └── loader.py         # YAML設定ローダー
│   ├── core/            # コアフレームワーク
│   │   ├── engine.py         # メインエンジン
│   │   ├── events.py         # イベントシステム
│   │   └── interfaces.py     # 基底インターフェース
│   ├── outputs/         # 出力ハンドラー
│   │   ├── console.py        # コンソール出力
│   │   └── file.py           # ファイル出力
│   ├── prompts/         # 外部プロンプトファイル
│   │   ├── meeting_summary.md
│   │   └── paper_review.md
│   ├── triggers/        # イベントトリガー
│   │   ├── file_watcher.py   # ファイル監視
│   │   └── manual.py         # 手動トリガー
│   └── utils/           # ユーティリティ
├── config/              # 設定ファイル
│   └── sample.yaml           # 設定例
└── tests/              # テストファイル
```

## 開発

```bash
# 依存関係インストール
uv sync

# テスト実行
uv run pytest

# 型チェック
uv run mypy src/

# リント
uv run ruff check .

# フォーマット
uv run black src/ tests/
```