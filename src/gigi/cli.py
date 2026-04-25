"""Gigi CLI: discover and analyze Reddit communities."""

from __future__ import annotations

import sys

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from .analyze import analyze_subreddit
from .client import MissingCredentials, get_reddit
from .find import find_subreddits

console = Console()


def _humanize(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


@click.group()
def cli() -> None:
    """Find and analyze Reddit communities to engage with."""


@cli.command()
@click.argument("topic")
@click.option("--limit", default=25, show_default=True, help="Max subreddits to fetch from search.")
@click.option("--min-subscribers", default=1_000, show_default=True, help="Filter out tiny subs.")
def find(topic: str, limit: int, min_subscribers: int) -> None:
    """Search for subreddits matching TOPIC, ranked by active-user ratio."""
    try:
        reddit = get_reddit()
    except MissingCredentials as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    with console.status(f"Searching subreddits for '{topic}'..."):
        matches = find_subreddits(reddit, topic, limit=limit, min_subscribers=min_subscribers)

    if not matches:
        console.print(f"[yellow]No subreddits found for '{topic}'.[/yellow]")
        return

    table = Table(title=f"Subreddits matching '{topic}'", show_lines=False)
    table.add_column("Subreddit", style="cyan", no_wrap=True)
    table.add_column("Subs", justify="right")
    table.add_column("Active", justify="right")
    table.add_column("Active%", justify="right", style="green")
    table.add_column("NSFW", justify="center")
    table.add_column("Description", overflow="fold")

    for m in matches:
        active_pct = f"{m.activity_ratio * 100:.2f}%" if m.active_users else "—"
        active = _humanize(m.active_users) if m.active_users else "—"
        table.add_row(
            f"r/{m.name}",
            _humanize(m.subscribers),
            active,
            active_pct,
            "yes" if m.over_18 else "",
            m.public_description[:140],
        )

    console.print(table)
    console.print(
        "[dim]Active% = currently-online users ÷ subscribers. Higher = more engaged community.[/dim]"
    )


@cli.command()
@click.argument("subreddit")
@click.option("--sample-size", default=200, show_default=True, help="Recent posts to sample for cadence analysis.")
def analyze(subreddit: str, sample_size: int) -> None:
    """Pull rules, cadence, top posts, and posting-time patterns for SUBREDDIT."""
    try:
        reddit = get_reddit()
    except MissingCredentials as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    with console.status(f"Analyzing r/{subreddit}..."):
        report = analyze_subreddit(reddit, subreddit, sample_size=sample_size)

    header = (
        f"[bold cyan]r/{report.name}[/bold cyan] · "
        f"{_humanize(report.subscribers)} subscribers · "
        f"{_humanize(report.active_users) if report.active_users else '—'} online"
    )
    console.print(Panel(header + "\n\n" + report.description, title="Community"))

    stats = Table(show_header=False, box=None)
    stats.add_column(style="bold")
    stats.add_column()
    stats.add_row("Posts/day", str(report.posts_per_day))
    stats.add_row("Median top-quartile score", str(report.median_score_for_top_quartile))
    stats.add_row("Best post hours (UTC)", ", ".join(str(h) for h in report.best_hours_utc) or "—")
    stats.add_row("Best weekdays", ", ".join(report.best_weekdays) or "—")
    stats.add_row("Allowed post types", ", ".join(report.allowed_post_types) or "—")
    if report.common_flairs:
        stats.add_row("Common flairs", ", ".join(f"{name} ({n})" for name, n in report.common_flairs))
    console.print(Panel(stats, title="Posting patterns"))

    if report.rules:
        rules_md = "\n".join(f"- {r}" for r in report.rules)
        console.print(Panel(Markdown(rules_md), title="Rules"))

    if report.top_posts_week:
        tp = Table(title="Top posts this week")
        tp.add_column("Score", justify="right", style="green")
        tp.add_column("Comments", justify="right")
        tp.add_column("Flair")
        tp.add_column("Title", overflow="fold")
        for p in report.top_posts_week:
            tp.add_row(_humanize(p.score), _humanize(p.num_comments), p.flair or "", p.title)
        console.print(tp)


if __name__ == "__main__":
    cli()
