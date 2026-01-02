#!/usr/bin/env python3
"""Generate daily summaries of Claude Code transcripts."""

import json
import subprocess
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

import anthropic
from anthropic.types import TextBlock
import click
from dotenv import load_dotenv
from markitdown import MarkItDown

load_dotenv()

CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"
OUTPUT_DIR = Path(__file__).parent / "claude-transcripts"


def get_project_name(folder_name: str) -> str:
    """Extract project name from Claude folder name."""
    # Format: -Users-joopsnijder-Projects-<project-name>
    parts = folder_name.split("-Projects-")
    return parts[-1] if len(parts) > 1 else folder_name


def filter_transcripts_by_date(target_date: date) -> dict[str, list[Path]]:
    """Find all transcript files that contain messages from the target date."""
    projects_with_transcripts: dict[str, list[Path]] = {}

    for project_dir in CLAUDE_PROJECTS_DIR.iterdir():
        if not project_dir.is_dir():
            continue

        project_name = get_project_name(project_dir.name)
        matching_files = []

        for jsonl_file in project_dir.glob("*.jsonl"):
            if has_messages_on_date(jsonl_file, target_date):
                matching_files.append(jsonl_file)

        if matching_files:
            projects_with_transcripts[project_name] = matching_files

    return projects_with_transcripts


def has_messages_on_date(jsonl_file: Path, target_date: date) -> bool:
    """Check if a JSONL file contains messages from the target date."""
    try:
        with open(jsonl_file) as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    timestamp = entry.get("timestamp")
                    if timestamp:
                        entry_date = datetime.fromisoformat(
                            timestamp.replace("Z", "+00:00")
                        ).date()
                        if entry_date == target_date:
                            return True
                except (json.JSONDecodeError, ValueError):
                    continue
    except Exception:
        pass
    return False


def collect_stats(
    project_transcripts: dict[str, list[Path]], target_date: date
) -> dict[str, int]:
    """Collect statistics from transcripts for the target date."""
    stats = {
        "prompts": 0,
        "messages": 0,
        "tool_calls": 0,
        "commits": 0,
    }

    for jsonl_files in project_transcripts.values():
        for jsonl_file in jsonl_files:
            try:
                with open(jsonl_file) as f:
                    for line in f:
                        if not line.strip():
                            continue
                        try:
                            entry = json.loads(line)
                            timestamp = entry.get("timestamp")
                            if not timestamp:
                                continue

                            entry_date = datetime.fromisoformat(
                                timestamp.replace("Z", "+00:00")
                            ).date()
                            if entry_date != target_date:
                                continue

                            entry_type = entry.get("type")
                            if entry_type == "user":
                                stats["prompts"] += 1
                                stats["messages"] += 1
                            elif entry_type == "assistant":
                                stats["messages"] += 1
                                # Count tool calls in assistant messages
                                message = entry.get("message", {})
                                content = message.get("content", [])
                                if isinstance(content, list):
                                    for block in content:
                                        if (
                                            isinstance(block, dict)
                                            and block.get("type") == "tool_use"
                                        ):
                                            stats["tool_calls"] += 1
                                            # Check for git commit
                                            tool_name = block.get("name", "")
                                            tool_input = block.get("input", {})
                                            if tool_name == "Bash":
                                                cmd = tool_input.get("command", "")
                                                if "git commit" in cmd:
                                                    stats["commits"] += 1
                        except (json.JSONDecodeError, ValueError):
                            continue
            except Exception:
                continue

    return stats


def convert_transcripts_to_html(
    project_transcripts: dict[str, list[Path]], output_dir: Path
) -> dict[str, Path]:
    """Convert transcript files to HTML using claude-code-transcripts."""
    project_html_files: dict[str, Path] = {}

    for project_name, jsonl_files in project_transcripts.items():
        project_output = output_dir / project_name
        project_output.mkdir(parents=True, exist_ok=True)

        for jsonl_file in jsonl_files:
            subprocess.run(
                [
                    "claude-code-transcripts",
                    "json",
                    str(jsonl_file),
                    "-o",
                    str(project_output),
                ],
                capture_output=True,
                check=False,
            )

        # Collect all generated HTML files
        html_files = list(project_output.glob("**/*.html"))
        if html_files:
            project_html_files[project_name] = project_output

    return project_html_files


def convert_html_to_markdown(html_dir: Path) -> str:
    """Convert all HTML files in a directory to markdown."""
    md = MarkItDown()
    markdown_parts = []

    for html_file in sorted(html_dir.glob("**/*.html")):
        try:
            result = md.convert(str(html_file))
            if result.text_content:
                markdown_parts.append(result.text_content)
        except Exception:
            continue

    return "\n\n---\n\n".join(markdown_parts)


def generate_summary(transcripts_markdown: dict[str, str], target_date: date) -> str:
    """Generate a summary using Claude API."""
    client = anthropic.Anthropic()

    # Build context from all projects
    context_parts = []
    for project_name, markdown in transcripts_markdown.items():
        # Truncate very long transcripts
        truncated = markdown[:50000] if len(markdown) > 50000 else markdown
        context_parts.append(f"## Project: {project_name}\n\n{truncated}")

    full_context = "\n\n---\n\n".join(context_parts)

    prompt = f"""Analyseer de volgende Claude Code transcripties van {target_date.strftime("%d %B %Y")} en maak een beknopte samenvatting in het Nederlands.

{full_context}

Maak een samenvatting met de volgende secties:

## Wat is er gemaakt?
Beschrijf per project wat er is gebouwd, geimplementeerd of opgelost. Wees specifiek over features, bugfixes, of verbeteringen.

## Wat is de stijl van aansturing?
Beschrijf hoe ik de AI heb aangestuurd, welke technieken ik gebruik en hoe ik samenwerk met de AI. Beschrijf de stijl.

## Waar heb ik bijgestuurd?
Beschrijf beslissingen die zijn genomen, aanpassingen in de aanpak, of veranderingen in de architectuur.

## Wat was lastig?
Beschrijf uitdagingen, problemen die moesten worden opgelost, of complexe situaties die zich voordeden.

## Wat heb ik geleerd?
Beschrijf nieuwe inzichten, technieken, of kennis die is opgedaan tijdens het programmeren.

Houd de samenvatting beknopt maar informatief. Focus op de belangrijkste punten."""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    first_block = message.content[0]
    if isinstance(first_block, TextBlock):
        return first_block.text
    return ""


def write_output(
    summary: str,
    stats: dict[str, int],
    target_date: date,
    project_transcripts: dict[str, list[Path]],
) -> Path:
    """Write all output files to a dated folder."""
    date_str = target_date.strftime("%Y%m%d")
    output_folder = OUTPUT_DIR / date_str
    output_folder.mkdir(parents=True, exist_ok=True)

    # Build sources section
    sources = "\n\n---\n\n## Bronnen\n\n"
    for project_name, files in sorted(project_transcripts.items()):
        if files:
            folder = files[0].parent
            sources += f"- **{project_name}**: `{folder}`\n"

    # Write summary
    summary_path = output_folder / f"{date_str}-summary.md"
    header = f"# AI Coding Highlights - {target_date.strftime('%d %B %Y')}\n\n"
    summary_path.write_text(header + summary + sources)

    # Write journal (empty template)
    journal_path = output_folder / f"{date_str}-journal.md"
    if not journal_path.exists():
        journal_path.write_text("# Journal\n\n")

    # Write stats as JSON
    stats_path = output_folder / f"{date_str}-stats.json"
    stats_data = {"date": target_date.strftime("%Y-%m-%d"), "stats": stats}
    stats_path.write_text(json.dumps(stats_data, indent=2))

    return output_folder


@click.command()
@click.option(
    "--date",
    "-d",
    "date_str",
    default=None,
    help="Date in YYYYMMDD format (default: yesterday)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be processed without generating summary",
)
def main(date_str: str | None, dry_run: bool) -> None:
    """Generate a daily summary of Claude Code transcripts."""
    # Parse date
    if date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y%m%d").date()
        except ValueError:
            raise click.BadParameter("Date must be in YYYYMMDD format")
    else:
        target_date = datetime.now().date() - timedelta(days=1)

    click.echo(f"Processing transcripts for {target_date.strftime('%Y-%m-%d')}...")

    # Find transcripts for the target date
    project_transcripts = filter_transcripts_by_date(target_date)

    if not project_transcripts:
        click.echo("No transcripts found for this date.")
        return

    click.echo(f"Found transcripts in {len(project_transcripts)} project(s):")
    for project_name, files in project_transcripts.items():
        click.echo(f"  - {project_name}: {len(files)} file(s)")

    if dry_run:
        click.echo("\nDry run - no summary generated.")
        return

    # Convert to HTML and then to Markdown
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        click.echo("\nConverting transcripts to HTML...")
        project_html = convert_transcripts_to_html(project_transcripts, temp_path)

        click.echo("Converting HTML to Markdown...")
        transcripts_markdown = {
            project: convert_html_to_markdown(html_dir)
            for project, html_dir in project_html.items()
        }

    # Collect stats
    click.echo("Collecting statistics...")
    stats = collect_stats(project_transcripts, target_date)

    # Generate summary with Claude
    click.echo("Generating summary with Claude...")
    summary = generate_summary(transcripts_markdown, target_date)

    # Write all output files
    output_folder = write_output(summary, stats, target_date, project_transcripts)
    click.echo(f"\nOutput written to: {output_folder}")


if __name__ == "__main__":
    main()
