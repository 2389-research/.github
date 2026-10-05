#!/usr/bin/env python3
# ABOUTME: Builds the organization profile from public GitHub activity and research RSS.
# ABOUTME: Fetches all sources before writing and leaves identical output untouched.
import argparse
import html
import json
import os
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

API_URL = "https://api.github.com"
FEED_URL = "https://2389.ai/research/writing/index.xml"
DEFAULT_OUTPUT = Path(__file__).resolve().with_name("README.md")


@dataclass(frozen=True)
class Repository:
    name: str
    url: str
    description: str
    archived: bool
    fork: bool
    pushed: datetime | None
    stars: int
    topics: list[str]


@dataclass(frozen=True)
class Release:
    repository: str
    title: str
    tag: str
    url: str
    published: datetime
    prerelease: bool


@dataclass(frozen=True)
class Post:
    title: str
    url: str
    published: datetime


def text_field(record: dict[str, Any], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing or invalid {key}")
    return value.strip()


def flag(record: dict[str, Any], key: str) -> bool:
    value = record.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"Missing or invalid {key}")
    return value


def link(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Source contains an invalid web link")
    return quote(url, safe=":/?#@!$&'*+,;=%~-._")


def timestamp(value: str) -> datetime:
    date = datetime.fromisoformat(value)
    if date.tzinfo is None:
        raise ValueError("Source date is missing its timezone")
    return date.astimezone(UTC)


def parse_repositories(records: list[dict[str, Any]]) -> list[Repository]:
    repositories = []
    for record in records:
        if flag(record, "private"):
            continue
        description = record.get("description")
        if description is not None and not isinstance(description, str):
            raise ValueError("Invalid repository description")
        stars = record.get("stargazers_count")
        if type(stars) is not int or stars < 0:
            raise ValueError("Missing or invalid stargazers_count")
        topics = record.get("topics")
        if not isinstance(topics, list) or any(
            not isinstance(topic, str) for topic in topics
        ):
            raise ValueError("Missing or invalid topics")
        repositories.append(
            Repository(
                text_field(record, "name"),
                link(text_field(record, "html_url")),
                description or "",
                flag(record, "archived"),
                flag(record, "fork"),
                timestamp(text_field(record, "pushed_at"))
                if record.get("pushed_at") is not None
                else None,
                stars,
                topics,
            )
        )
    return repositories


def parse_releases(repository: str, records: list[dict[str, Any]]) -> list[Release]:
    releases = []
    for record in records:
        if flag(record, "draft"):
            continue
        tag = text_field(record, "tag_name")
        title = record.get("name")
        if title is not None and not isinstance(title, str):
            raise ValueError("Invalid release name")
        releases.append(
            Release(
                repository,
                title or tag,
                tag,
                link(text_field(record, "html_url")),
                timestamp(text_field(record, "published_at")),
                flag(record, "prerelease"),
            )
        )
    return releases


def parse_posts(data: bytes) -> list[Post]:
    root = ET.fromstring(data)
    if root.tag != "rss" or root.find("channel") is None:
        raise ValueError("Research source is not an RSS feed")
    posts = []
    for item in root.findall("./channel/item"):
        fields = {key: item.findtext(key) for key in ("title", "link", "pubDate")}
        date = parsedate_to_datetime(text_field(fields, "pubDate"))
        if date.tzinfo is None:
            raise ValueError("Research date is missing its timezone")
        posts.append(
            Post(
                text_field(fields, "title"),
                link(text_field(fields, "link")),
                date.astimezone(UTC),
            )
        )
    return posts


class NoRedirect(HTTPRedirectHandler):
    # GitHub credentials must not follow a redirect to another host.
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def fetch(url: str, token: str = "") -> tuple[bytes, str]:
    headers = {"User-Agent": "2389-research-profile"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    try:
        with build_opener(NoRedirect()).open(request, timeout=30) as response:
            if response.status != 200:
                raise ValueError(f"Unexpected HTTP status {response.status} from {url}")
            return response.read(), response.headers.get("Link", "")
    except HTTPError as error:
        error.close()
        raise OSError(f"HTTP {error.code} from {url}") from None


def pages(url: str, token: str) -> list[dict[str, Any]]:
    origin = urlsplit(url)[:2]
    seen = set()
    records = []
    while url:
        if urlsplit(url)[:2] != origin or url in seen:
            raise ValueError("Invalid GitHub pagination link")
        seen.add(url)
        data, links = fetch(url, token)
        page = json.loads(data)
        if not isinstance(page, list) or any(not isinstance(row, dict) for row in page):
            raise ValueError("GitHub source did not return a list of objects")
        records.extend(page)
        match = re.search(r'<([^>]+)>;\s*rel="next"', links)
        url = urljoin(url, match[1]) if match else ""
    return records


def collect(
    *, api_url: str = API_URL, feed_url: str = FEED_URL, token: str = ""
) -> tuple[list[Repository], list[Release], list[Post]]:
    repositories = parse_repositories(
        pages(f"{api_url}/orgs/2389-research/repos?type=public&per_page=100", token)
    )
    releases = []
    for repository in repositories:
        name = quote(repository.name, safe="")
        releases.extend(
            parse_releases(
                repository.name,
                pages(
                    f"{api_url}/repos/2389-research/{name}/releases?per_page=100", token
                ),
            )
        )
    data, _ = fetch(feed_url)
    return repositories, releases, parse_posts(data)


def markdown(value: str) -> str:
    value = html.escape(" ".join(value.split()), quote=False)
    return re.sub(r"([\\`*_{}\[\]()#+.!|~-])", r"\\\1", value)


def repository_name(repository: Repository) -> str:
    line = f"[{markdown(repository.name)}]({repository.url})"
    labels = []
    if repository.archived:
        labels.append("archived")
    if repository.fork:
        labels.append("fork")
    if labels:
        line += f" ({', '.join(labels)})"
    return line


def repository_line(repository: Repository) -> str:
    line = f"- {repository_name(repository)}"
    if repository.description:
        line += f" — {markdown(repository.description)}"
    return line


def render_profile(
    repositories: list[Repository], releases: list[Release], posts: list[Post]
) -> str:
    lines = [
        "# 2389 Research",
        "",
        "We're an applied AI lab in Chicago. We build tools for agents, share our "
        "research, and help engineering teams work with coding agents.",
        "",
        "[Website](https://2389.ai/) · [Research](https://2389.ai/research/) · "
        "[Work with us](https://2389.ai/work-with-us/) · "
        "[Say hello](mailto:hello@2389.ai)",
        "",
        "## Recent activity",
        "",
    ]
    active = [
        repository
        for repository in repositories
        if not repository.archived
        and repository.name != ".github"
        and repository.pushed is not None
    ]
    active.sort(
        key=lambda r: (
            -(r.pushed or datetime.min.replace(tzinfo=UTC)).timestamp(),
            r.name.casefold(),
            r.name,
        )
    )
    lines.extend(
        f"{repository_line(repo)} — pushed {repo.pushed:%Y-%m-%d}"
        for repo in active[:8]
    )
    if not active:
        lines.append("No recent public repository activity.")
    lines.extend(["", "## Latest releases", ""])
    ordered_releases = sorted(
        releases,
        key=lambda r: (-r.published.timestamp(), r.repository.casefold(), r.tag, r.url),
    )
    released_projects: set[str] = set()
    for release in ordered_releases:
        if release.repository in released_projects:
            continue
        released_projects.add(release.repository)
        title = f"{release.repository}: {release.tag}"
        if release.title != release.tag:
            title += f" — {release.title}"
        title = markdown(title)
        label = " · prerelease" if release.prerelease else ""
        lines.append(
            f"- [{title}]({release.url}) — {release.published:%Y-%m-%d}{label}"
        )
        if len(released_projects) == 10:
            break
    if not releases:
        lines.append("No published releases yet.")
    lines.extend(["", "## Latest research", ""])
    for post in sorted(posts, key=lambda p: (-p.published.timestamp(), p.url, p.title))[
        :5
    ]:
        lines.append(
            f"- [{markdown(post.title)}]({post.url}) — {post.published:%Y-%m-%d}"
        )
    if not posts:
        lines.append("No research posts yet.")
    lines.extend(["", "## Top starred repos", ""])
    top_starred = sorted(
        repositories, key=lambda r: (-r.stars, r.name.casefold(), r.name)
    )[:10]
    lines.extend(
        f"{repository_line(repo)} — {repo.stars} stars" for repo in top_starred
    )
    if not top_starred:
        lines.append("No public repositories yet.")
    lines.extend(
        [
            "",
            "## Repository directory",
            "",
            "<details>",
            f"<summary>Browse all {len(repositories)} public repositories</summary>",
            "",
            "| Name | Description | Topics |",
            "| --- | --- | --- |",
        ]
    )
    for repo in sorted(repositories, key=lambda r: (r.name.casefold(), r.name)):
        topics = ", ".join(
            markdown(topic)
            for topic in sorted(
                repo.topics, key=lambda topic: (topic.casefold(), topic)
            )
        )
        lines.append(
            f"| {repository_name(repo)} | {markdown(repo.description) or '—'} "
            f"| {topics or '—'} |"
        )
    lines.extend(
        [
            "",
            "</details>",
            "",
            "Updated daily from public GitHub activity and our research feed.",
            "",
        ]
    )
    return "\n".join(lines)


def write_profile(path: Path, content: str) -> bool:
    data = content.encode("utf-8")
    if path.exists() and path.read_bytes() == data:
        return False
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as output:
            temporary = Path(output.name)
            output.write(data)
        temporary.chmod(0o644)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return True


def refresh(
    path: Path, *, api_url: str = API_URL, feed_url: str = FEED_URL, token: str = ""
) -> bool:
    repositories, releases, posts = collect(
        api_url=api_url, feed_url=feed_url, token=token
    )
    return write_profile(path, render_profile(repositories, releases, posts))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Refresh the profile from public GitHub activity and research RSS."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Markdown output path (default: profile/README.md beside this script)",
    )
    args = parser.parse_args()
    try:
        changed = refresh(
            args.output,
            token=os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", ""),
        )
    except (OSError, ValueError, ET.ParseError) as error:
        print(f"Profile refresh failed: {error}", file=sys.stderr)
        return 1
    print(f"{'Updated' if changed else 'Unchanged'}: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
