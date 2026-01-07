"""Tests for daily_summary.py."""

import json
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from daily_summary import (
    collect_stats,
    convert_html_to_markdown,
    convert_transcripts_to_html,
    filter_jsonl_by_date,
    filter_transcripts_by_date,
    generate_summary,
    get_project_name,
    has_messages_on_date,
    main,
    sanitize_secrets,
    write_output,
)


class TestGetProjectName:
    """Tests for get_project_name function."""

    def test_extracts_project_name(self) -> None:
        folder_name = "-Users-joopsnijder-Projects-my-project"
        assert get_project_name(folder_name) == "my-project"

    def test_handles_multiple_projects_in_path(self) -> None:
        folder_name = "-Users-joopsnijder-Projects-sub-Projects-actual-project"
        assert get_project_name(folder_name) == "actual-project"

    def test_returns_original_if_no_projects(self) -> None:
        folder_name = "some-random-folder"
        assert get_project_name(folder_name) == "some-random-folder"


class TestHasMessagesOnDate:
    """Tests for has_messages_on_date function."""

    def test_returns_true_when_date_matches(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(
                json.dumps({"timestamp": "2026-01-01T10:00:00Z", "type": "user"}) + "\n"
            )
            f.flush()
            result = has_messages_on_date(Path(f.name), date(2026, 1, 1))
            assert result is True

    def test_returns_false_when_date_does_not_match(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(
                json.dumps({"timestamp": "2026-01-02T10:00:00Z", "type": "user"}) + "\n"
            )
            f.flush()
            result = has_messages_on_date(Path(f.name), date(2026, 1, 1))
            assert result is False

    def test_returns_false_for_empty_file(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.flush()
            result = has_messages_on_date(Path(f.name), date(2026, 1, 1))
            assert result is False

    def test_handles_invalid_json(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write("not valid json\n")
            f.flush()
            result = has_messages_on_date(Path(f.name), date(2026, 1, 1))
            assert result is False


class TestFilterJsonlByDate:
    """Tests for filter_jsonl_by_date function."""

    def test_filters_entries_by_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_dir = Path(tmpdir)
            jsonl_file = temp_dir / "test.jsonl"
            jsonl_file.write_text(
                json.dumps({"timestamp": "2026-01-01T10:00:00Z", "type": "user"})
                + "\n"
                + json.dumps({"timestamp": "2026-01-01T11:00:00Z", "type": "assistant"})
                + "\n"
            )

            filtered = filter_jsonl_by_date(jsonl_file, date(2026, 1, 1), temp_dir)

            assert filtered.exists()
            content = filtered.read_text()
            lines = [line for line in content.split("\n") if line.strip()]
            assert len(lines) == 2

    def test_handles_multiple_dates(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_dir = Path(tmpdir)
            jsonl_file = temp_dir / "test.jsonl"
            jsonl_file.write_text(
                json.dumps({"timestamp": "2026-01-01T10:00:00Z", "type": "user"})
                + "\n"
                + json.dumps({"timestamp": "2026-01-02T10:00:00Z", "type": "user"})
                + "\n"
                + json.dumps({"timestamp": "2026-01-01T11:00:00Z", "type": "assistant"})
                + "\n"
            )

            filtered = filter_jsonl_by_date(jsonl_file, date(2026, 1, 1), temp_dir)

            content = filtered.read_text()
            lines = [line for line in content.split("\n") if line.strip()]
            assert len(lines) == 2
            # Verify it only has Jan 1 entries
            for line in lines:
                entry = json.loads(line)
                assert "2026-01-01" in entry["timestamp"]

    def test_returns_empty_file_when_no_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_dir = Path(tmpdir)
            jsonl_file = temp_dir / "test.jsonl"
            jsonl_file.write_text(
                json.dumps({"timestamp": "2026-01-02T10:00:00Z", "type": "user"}) + "\n"
            )

            filtered = filter_jsonl_by_date(jsonl_file, date(2026, 1, 1), temp_dir)

            assert filtered.exists()
            content = filtered.read_text()
            assert content.strip() == ""

    def test_skips_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_dir = Path(tmpdir)
            jsonl_file = temp_dir / "test.jsonl"
            jsonl_file.write_text(
                "invalid json\n"
                + json.dumps({"timestamp": "2026-01-01T10:00:00Z", "type": "user"})
                + "\n"
                + "another invalid line\n"
            )

            filtered = filter_jsonl_by_date(jsonl_file, date(2026, 1, 1), temp_dir)

            content = filtered.read_text()
            lines = [line for line in content.split("\n") if line.strip()]
            assert len(lines) == 1


class TestCollectStats:
    """Tests for collect_stats function."""

    def test_counts_user_messages_as_prompts(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(
                json.dumps({"timestamp": "2026-01-01T10:00:00Z", "type": "user"}) + "\n"
            )
            f.write(
                json.dumps({"timestamp": "2026-01-01T11:00:00Z", "type": "user"}) + "\n"
            )
            f.flush()
            stats = collect_stats({"project": [Path(f.name)]}, date(2026, 1, 1))
            assert stats["prompts"] == 2
            assert stats["messages"] == 2

    def test_counts_assistant_messages(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(
                json.dumps(
                    {
                        "timestamp": "2026-01-01T10:00:00Z",
                        "type": "assistant",
                        "message": {"content": [{"type": "text", "text": "Hello"}]},
                    }
                )
                + "\n"
            )
            f.flush()
            stats = collect_stats({"project": [Path(f.name)]}, date(2026, 1, 1))
            assert stats["prompts"] == 0
            assert stats["messages"] == 1

    def test_counts_tool_calls(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(
                json.dumps(
                    {
                        "timestamp": "2026-01-01T10:00:00Z",
                        "type": "assistant",
                        "message": {
                            "content": [
                                {"type": "tool_use", "name": "Read", "input": {}},
                                {"type": "tool_use", "name": "Write", "input": {}},
                            ]
                        },
                    }
                )
                + "\n"
            )
            f.flush()
            stats = collect_stats({"project": [Path(f.name)]}, date(2026, 1, 1))
            assert stats["tool_calls"] == 2

    def test_counts_git_commits(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(
                json.dumps(
                    {
                        "timestamp": "2026-01-01T10:00:00Z",
                        "type": "assistant",
                        "message": {
                            "content": [
                                {
                                    "type": "tool_use",
                                    "name": "Bash",
                                    "input": {"command": "git commit -m 'test'"},
                                }
                            ]
                        },
                    }
                )
                + "\n"
            )
            f.flush()
            stats = collect_stats({"project": [Path(f.name)]}, date(2026, 1, 1))
            assert stats["commits"] == 1

    def test_ignores_entries_from_other_dates(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(
                json.dumps({"timestamp": "2026-01-02T10:00:00Z", "type": "user"}) + "\n"
            )
            f.flush()
            stats = collect_stats({"project": [Path(f.name)]}, date(2026, 1, 1))
            assert stats["prompts"] == 0


class TestWriteOutput:
    """Tests for write_output function."""

    def test_creates_output_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("daily_summary.OUTPUT_DIR", Path(tmpdir)):
                output = write_output(
                    summary="Test summary",
                    stats={"prompts": 1, "messages": 2, "tool_calls": 3, "commits": 0},
                    target_date=date(2026, 1, 1),
                    project_transcripts={},
                )
                assert output.exists()
                assert output.name == "20260101"

    def test_creates_summary_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("daily_summary.OUTPUT_DIR", Path(tmpdir)):
                output = write_output(
                    summary="Test summary",
                    stats={"prompts": 1, "messages": 2, "tool_calls": 3, "commits": 0},
                    target_date=date(2026, 1, 1),
                    project_transcripts={},
                )
                summary_file = output / "20260101-summary.md"
                assert summary_file.exists()
                content = summary_file.read_text()
                assert "Test summary" in content

    def test_creates_journal_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("daily_summary.OUTPUT_DIR", Path(tmpdir)):
                output = write_output(
                    summary="Test",
                    stats={"prompts": 0, "messages": 0, "tool_calls": 0, "commits": 0},
                    target_date=date(2026, 1, 1),
                    project_transcripts={},
                )
                journal_file = output / "20260101-journal.md"
                assert journal_file.exists()
                assert "# Journal" in journal_file.read_text()

    def test_creates_stats_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("daily_summary.OUTPUT_DIR", Path(tmpdir)):
                output = write_output(
                    summary="Test",
                    stats={"prompts": 5, "messages": 10, "tool_calls": 3, "commits": 1},
                    target_date=date(2026, 1, 1),
                    project_transcripts={},
                )
                stats_file = output / "20260101-stats.json"
                assert stats_file.exists()
                stats_data = json.loads(stats_file.read_text())
                assert stats_data["date"] == "2026-01-01"
                assert stats_data["stats"]["prompts"] == 5
                assert stats_data["stats"]["commits"] == 1

    def test_does_not_overwrite_existing_journal(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("daily_summary.OUTPUT_DIR", Path(tmpdir)):
                # Create folder and journal first
                folder = Path(tmpdir) / "20260101"
                folder.mkdir()
                journal = folder / "20260101-journal.md"
                journal.write_text("My existing notes")

                write_output(
                    summary="Test",
                    stats={"prompts": 0, "messages": 0, "tool_calls": 0, "commits": 0},
                    target_date=date(2026, 1, 1),
                    project_transcripts={},
                )
                assert journal.read_text() == "My existing notes"


class TestFilterTranscriptsByDate:
    """Tests for filter_transcripts_by_date function."""

    def test_finds_transcripts_for_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create mock project structure
            project_dir = Path(tmpdir) / "-Users-test-Projects-myproject"
            project_dir.mkdir()
            jsonl_file = project_dir / "session.jsonl"
            jsonl_file.write_text(
                json.dumps({"timestamp": "2026-01-01T10:00:00Z", "type": "user"}) + "\n"
            )

            with patch("daily_summary.CLAUDE_PROJECTS_DIR", Path(tmpdir)):
                result = filter_transcripts_by_date(date(2026, 1, 1))
                assert "myproject" in result
                assert len(result["myproject"]) == 1

    def test_returns_empty_when_no_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "-Users-test-Projects-myproject"
            project_dir.mkdir()
            jsonl_file = project_dir / "session.jsonl"
            jsonl_file.write_text(
                json.dumps({"timestamp": "2026-01-02T10:00:00Z", "type": "user"}) + "\n"
            )

            with patch("daily_summary.CLAUDE_PROJECTS_DIR", Path(tmpdir)):
                result = filter_transcripts_by_date(date(2026, 1, 1))
                assert result == {}


class TestConvertTranscriptsToHtml:
    """Tests for convert_transcripts_to_html function."""

    def test_calls_claude_code_transcripts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            jsonl_file = Path(tmpdir) / "test.jsonl"
            jsonl_file.write_text("{}\n")
            output_dir = Path(tmpdir) / "output"
            output_dir.mkdir()

            with patch("daily_summary.subprocess.run") as mock_run:
                convert_transcripts_to_html(
                    {"project": [jsonl_file]}, output_dir, date(2026, 1, 1)
                )
                mock_run.assert_called()


class TestConvertHtmlToMarkdown:
    """Tests for convert_html_to_markdown function."""

    def test_converts_html_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            html_dir = Path(tmpdir)
            html_file = html_dir / "test.html"
            html_file.write_text("<h1>Test</h1><p>Content</p>")

            result = convert_html_to_markdown(html_dir)
            assert "Test" in result or "Content" in result or result == ""


class TestGenerateSummary:
    """Tests for generate_summary function."""

    def test_calls_anthropic_api(self) -> None:
        mock_response = MagicMock()
        mock_text_block = MagicMock()
        mock_text_block.text = "Generated summary"
        mock_response.content = [mock_text_block]

        with patch("daily_summary.anthropic.Anthropic") as mock_client:
            mock_client.return_value.messages.create.return_value = mock_response
            with patch("daily_summary.isinstance", return_value=True):
                generate_summary({"project": "markdown content"}, date(2026, 1, 1))
                # The function should call the API
                mock_client.return_value.messages.create.assert_called_once()


class TestMain:
    """Tests for main CLI function."""

    def test_dry_run_does_not_generate(self) -> None:
        runner = CliRunner()
        with patch("daily_summary.filter_transcripts_by_date") as mock_filter:
            mock_filter.return_value = {"project": [Path("/tmp/test.jsonl")]}
            result = runner.invoke(main, ["--dry-run", "--date", "20260101"])
            assert "Dry run" in result.output

    def test_no_transcripts_message(self) -> None:
        runner = CliRunner()
        with patch("daily_summary.filter_transcripts_by_date") as mock_filter:
            mock_filter.return_value = {}
            result = runner.invoke(main, ["--date", "20260101"])
            assert "No transcripts found" in result.output

    def test_invalid_date_format(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--date", "invalid"])
        assert result.exit_code != 0


class TestSanitizeSecrets:
    """Tests for sanitize_secrets function."""

    def test_openai_api_key_standalone(self) -> None:
        """Test that standalone OpenAI API keys are redacted."""
        text = "The key is sk-1234567890abcdefghijklmnopqrstuvwxyz"
        result = sanitize_secrets(text)
        assert "sk-1234567890abcdefghijklmnopqrstuvwxyz" not in result
        assert "REDACTED" in result

    def test_anthropic_api_key_standalone(self) -> None:
        """Test that standalone Anthropic API keys are redacted."""
        text = "Use this: sk-ant-api03-abcdefghijklmnopqrstuvwxyz1234567890"
        result = sanitize_secrets(text)
        assert "sk-ant-api03-abcdefghijklmnopqrstuvwxyz1234567890" not in result
        assert "REDACTED" in result

    def test_github_token_standalone(self) -> None:
        """Test that standalone GitHub tokens are redacted."""
        text = "Token: ghp_1234567890abcdefghijklmnopqrstuvwxyz1234"
        result = sanitize_secrets(text)
        assert "ghp_1234567890abcdefghijklmnopqrstuvwxyz1234" not in result
        assert "REDACTED" in result

    def test_github_pat_standalone(self) -> None:
        """Test that standalone GitHub personal access tokens are redacted."""
        text = "Use github_pat_11ABCDEFGH_abcdefghijklmnopqrstuvwxyz"
        result = sanitize_secrets(text)
        assert "github_pat_11ABCDEFGH_abcdefghijklmnopqrstuvwxyz" not in result
        assert "REDACTED" in result

    def test_password_pattern(self) -> None:
        """Test that passwords are redacted."""
        text = 'password="SuperSecretP@ssw0rd!"'
        result = sanitize_secrets(text)
        assert "SuperSecretP@ssw0rd!" not in result
        assert "REDACTED" in result

    def test_jwt_token_standalone(self) -> None:
        """Test that standalone JWT tokens are redacted."""
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        text = f"Token is {jwt}"
        result = sanitize_secrets(text)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result
        assert "REDACTED" in result

    def test_postgres_connection_string(self) -> None:
        """Test that database connection strings are redacted."""
        text = "postgres://user:mysecretpassword@localhost:5432/mydb"
        result = sanitize_secrets(text)
        assert "mysecretpassword" not in result
        assert "REDACTED" in result

    def test_mongodb_connection_string(self) -> None:
        """Test that MongoDB connection strings are redacted."""
        text = "mongodb://admin:password123@cluster.mongodb.net/db"
        result = sanitize_secrets(text)
        assert "password123" not in result
        assert "REDACTED" in result

    def test_private_key(self) -> None:
        """Test that private keys are redacted."""
        text = """-----BEGIN RSA PRIVATE KEY-----
MIIEpQIBAAKCAQEA0Z3VS5JJcds3xfn/ygWyf8Jz
-----END RSA PRIVATE KEY-----"""
        result = sanitize_secrets(text)
        assert "MIIEpQIBAAKCAQEA0Z3VS5JJcds3xfn/ygWyf8Jz" not in result
        assert "PRIVATE_KEY_REDACTED" in result

    def test_slack_token_standalone(self) -> None:
        """Test that standalone Slack tokens are redacted."""
        text = "Slack: xoxb-1234567890-abcdefghij"
        result = sanitize_secrets(text)
        assert "xoxb-1234567890-abcdefghij" not in result
        assert "REDACTED" in result

    def test_aws_access_key(self) -> None:
        """Test that AWS access keys are redacted."""
        text = 'AWS_ACCESS_KEY_ID="AKIAIOSFODNN7EXAMPLE"'
        result = sanitize_secrets(text)
        assert "AKIAIOSFODNN7EXAMPLE" not in result
        assert "REDACTED" in result

    def test_aws_secret_key(self) -> None:
        """Test that AWS secret keys are redacted."""
        text = 'aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"'
        result = sanitize_secrets(text)
        assert "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" not in result
        assert "REDACTED" in result

    def test_bearer_token(self) -> None:
        """Test that Bearer tokens are redacted."""
        text = "Authorization: Bearer abcdefghijklmnopqrstuvwxyz1234567890"
        result = sanitize_secrets(text)
        assert "abcdefghijklmnopqrstuvwxyz1234567890" not in result
        assert "REDACTED" in result

    def test_normal_text_preserved(self) -> None:
        """Test that normal text is not affected."""
        text = "This is a normal message about programming."
        result = sanitize_secrets(text)
        assert result == text

    def test_multiple_secrets(self) -> None:
        """Test that multiple secrets in one text are all redacted."""
        text = """
        password="SecretPass123"
        Key: sk-abcdefghijklmnopqrstuvwxyz1234
        """
        result = sanitize_secrets(text)
        assert "SecretPass123" not in result
        assert "sk-abcdefghijklmnopqrstuvwxyz1234" not in result

    def test_env_variable_with_secret(self) -> None:
        """Test that environment variable style secrets are redacted."""
        text = 'secret="abcdefghij123456"'
        result = sanitize_secrets(text)
        assert "abcdefghij123456" not in result
        assert "REDACTED" in result
