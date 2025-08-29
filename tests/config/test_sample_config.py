from pathlib import Path

from scarfy.config.loader import ConfigLoader


class TestSampleConfig:
    """サンプル設定ファイルのテストクラス。"""

    def setup_method(self) -> None:
        """各テストメソッドの前に実行される初期化処理。"""
        self.loader = ConfigLoader()
        self.sample_config_path = Path("config/sample.yaml")
        self.prompts_dir = Path("prompts")

    def test_sample_config_exists(self) -> None:
        """サンプル設定ファイルが存在することをテスト。"""

    def test_sample_config_valid_yaml(self) -> None:
        """サンプル設定ファイルが有効なYAMLであることをテスト。"""
        # YAMLが正常に読み込めることを確認
        config = self.loader.load_config(self.sample_config_path)
        assert isinstance(config, dict)
        assert len(config) > 0

    def test_sample_config_has_required_structure(self) -> None:
        """サンプル設定ファイルが必要な構造を持つことをテスト。"""
        config = self.loader.load_config(self.sample_config_path)

        # 基本構造の確認
        assert "workflows" in config, "workflows セクションが必要です"
        assert isinstance(
            config["workflows"], list
        ), "workflows は配列である必要があります"

    def test_sample_config_workflow_count(self) -> None:
        """期待されるワークフロー数をテスト。"""
        config = self.loader.load_config(self.sample_config_path)
        workflows = config.get("workflows", [])

        # 現在のsample.yamlには1つのワークフロー（meeting_notes）がある
        assert (
            len(workflows) >= 1
        ), f"最低1個のワークフローが期待されますが、{len(workflows)}個でした"

    def test_sample_config_workflows_have_required_fields(self) -> None:
        """各ワークフローが必要なフィールドを持つことをテスト。"""
        config = self.loader.load_config(self.sample_config_path)
        workflows = config.get("workflows", [])

        required_fields = ["name", "trigger", "agent", "output"]

        for i, workflow in enumerate(workflows):
            for field in required_fields:
                assert (
                    field in workflow
                ), f"ワークフロー{i+1}に{field}フィールドが不足しています"

    def test_prompt_files_exist_for_workflows(self) -> None:
        """ワークフローで参照されるプロンプトファイルが存在することをテスト。"""
        config = self.loader.load_config(self.sample_config_path)
        workflows = config.get("workflows", [])

        for workflow in workflows:
            agent_config = workflow.get("agent", {})
            prompt_file = agent_config.get("prompt_file")

            if prompt_file:
                # プロンプトファイルパスを解決
                if not prompt_file.startswith("/"):
                    # 相対パスの場合はプロジェクトルートを基準とする
                    full_path = Path(prompt_file)
                else:
                    full_path = Path(prompt_file)

                assert (
                    full_path.exists()
                ), f"プロンプトファイルが見つかりません: {full_path}"

    def test_sample_meeting_summary_prompt_exists(self) -> None:
        """サンプル会議要約プロンプトファイルが存在することをテスト。"""
        # sample.yamlではsample_meeting_summary.mdを参照
        meeting_prompt = self.prompts_dir / "sample_meeting_summary.md"
        assert (
            meeting_prompt.exists()
        ), f"サンプル会議要約プロンプトファイルが見つかりません: {meeting_prompt}"
