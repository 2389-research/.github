# ABOUTME: Checks profile selection, Markdown rendering, and complete HTTP collection.
# ABOUTME: Integration fixtures serve HTTP without replacing program functions.
import importlib.util
import json
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

SPEC = importlib.util.spec_from_file_location(
    "generate", Path(__file__).resolve().parents[1] / "profile/generate.py"
)
assert SPEC and SPEC.loader
generate = importlib.util.module_from_spec(SPEC)
sys.modules["generate"] = generate
SPEC.loader.exec_module(generate)


def repo(name: str, **fields: Any) -> dict[str, Any]:
    return {
        "name": name,
        "html_url": f"https://github.com/2389-research/{name}",
        "description": "Useful code",
        "private": False,
        "archived": False,
        "fork": False,
        "pushed_at": "2026-01-01T00:00:00Z",
        "stargazers_count": 0,
        **fields,
    }


def release(name: str, **fields: Any) -> dict[str, Any]:
    return {
        "name": name,
        "tag_name": name,
        "html_url": f"https://github.com/2389-research/alpha/releases/tag/{name}",
        "draft": False,
        "prerelease": False,
        "published_at": "2026-01-01T00:00:00Z",
        **fields,
    }


def rss(items: str = "") -> bytes:
    return f"<rss><channel>{items}</channel></rss>".encode()


def item(title: str, date: str) -> str:
    return (
        f"<item><title>{title}</title><link>https://2389.ai/{title}/</link>"
        f"<pubDate>{date}</pubDate></item>"
    )


class RenderingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(
            hasattr(generate, "render_profile"), "content generator missing"
        )

    def test_directory_is_complete_sorted_and_labels_archives_and_forks(self) -> None:
        repos = generate.parse_repositories(
            [
                repo("zeta", archived=True),
                repo("Alpha", fork=True),
                repo("private", private=True),
            ]
        )
        output = generate.render_profile(repos, [], [])
        directory = output.split("<details>")[1]
        self.assertIn("2 public repositories", directory)
        self.assertLess(directory.index("Alpha"), directory.index("zeta"))
        self.assertIn("archived", directory)
        self.assertIn("fork", directory)
        self.assertNotIn("private", directory)

    def test_top_starred_ranks_numerically_limits_to_ten_and_breaks_ties(self) -> None:
        records = [repo(f"repo-{n}", stargazers_count=n) for n in range(10)]
        records += [
            repo("zeta", stargazers_count=100),
            repo("beta", stargazers_count=20),
            repo("alpha", stargazers_count=20),
            repo("Alpha", stargazers_count=20),
        ]
        output = generate.render_profile(generate.parse_repositories(records), [], [])
        self.assertIn("## Top starred repos", output)
        section = output.split("## Top starred repos")[1].split("## ")[0]
        lines = [line for line in section.splitlines() if line.startswith("- [")]
        expected = ["zeta", "Alpha", "alpha", "beta"] + [
            f"repo-{n}" for n in range(9, 3, -1)
        ]
        self.assertEqual(len(lines), 10)
        for line, name in zip(lines, expected, strict=True):
            self.assertIn(f"](https://github.com/2389-research/{name})", line)
        self.assertTrue(lines[0].endswith(" — 100 stars"))
        self.assertTrue(lines[-1].endswith(" — 4 stars"))
        self.assertEqual(
            output.split("## Top starred repos")[1].split("## ")[1].splitlines()[0],
            "Repository directory",
        )

    def test_top_starred_includes_all_public_repo_types_and_existing_labels(
        self,
    ) -> None:
        records = [
            repo("archive", archived=True, stargazers_count=4),
            repo("fork", fork=True, stargazers_count=3),
            repo(".github", stargazers_count=2),
            repo("empty", pushed_at=None, stargazers_count=0),
            repo("secret", private=True, stargazers_count=100),
        ]
        output = generate.render_profile(generate.parse_repositories(records), [], [])
        self.assertIn("## Top starred repos", output)
        section = output.split("## Top starred repos")[1].split("## ")[0]
        self.assertEqual(section.count("- ["), 4)
        self.assertIn("(archived) — Useful code — 4 stars", section)
        self.assertIn("(fork) — Useful code — 3 stars", section)
        self.assertIn("/2389-research/.github)", section)
        self.assertIn("/2389-research/empty) — Useful code — 0 stars", section)
        self.assertNotIn("secret", section)

    def test_repository_star_counts_must_be_nonnegative_integers(self) -> None:
        for count in [-1, 1.5, "5", None, True, False]:
            with (
                self.subTest(count=count),
                self.assertRaisesRegex(ValueError, "stargazers_count"),
            ):
                generate.parse_repositories([repo("alpha", stargazers_count=count)])
        record = repo("alpha")
        del record["stargazers_count"]
        with self.assertRaisesRegex(ValueError, "stargazers_count"):
            generate.parse_repositories([record])

    def test_top_starred_empty_state(self) -> None:
        output = generate.render_profile([], [], [])
        self.assertIn("## Top starred repos", output)
        section = output.split("## Top starred repos")[1].split("## ")[0]
        self.assertIn("No public repositories yet.", section)

    def test_recent_activity_uses_push_time_and_limits_to_eight_active_repos(
        self,
    ) -> None:
        repos = [
            repo(f"repo-{n}", pushed_at=f"2026-01-{n:02}T00:00:00Z")
            for n in range(1, 11)
        ]
        repos += [
            repo(".github"),
            repo("archive", archived=True),
            repo("empty", pushed_at=None),
        ]
        output = generate.render_profile(generate.parse_repositories(repos), [], [])
        recent = output.split("## Recent activity")[1].split("## ")[0]
        self.assertEqual(recent.count("- ["), 8)
        self.assertLess(recent.index("repo-10"), recent.index("repo-9"))
        for name in [".github", "archive", "empty", "repo-1]"]:
            self.assertNotIn(name, recent)

    def test_releases_use_published_time_exclude_drafts_and_label_prereleases(
        self,
    ) -> None:
        releases = [
            release(f"v{n}", published_at=f"2026-01-{n:02}T00:00:00Z")
            for n in range(1, 13)
        ]
        releases += [release("draft", draft=True, published_at=None)]
        releases[11]["prerelease"] = True
        parsed = generate.parse_releases("alpha", releases)
        output = generate.render_profile([], parsed, [])
        section = output.split("## Latest releases")[1].split("## ")[0]
        self.assertEqual(section.count("- ["), 10)
        self.assertLess(section.index("v12"), section.index("v11"))
        self.assertIn("prerelease", section)
        self.assertIn("2026-01-12", section)
        self.assertIn("/releases/tag/v12", section)
        self.assertNotIn("draft", section)
        self.assertNotIn("v1]", section)

    def test_feed_sorts_actual_dates_and_keeps_five(self) -> None:
        data = rss(
            "".join(
                item(f"post-{n}", f"{n:02} Jan 2026 00:00:00 +0000")
                for n in range(1, 8)
            )
        )
        output = generate.render_profile([], [], generate.parse_posts(data))
        section = output.split("## Latest research")[1].split("## ")[0]
        self.assertEqual(section.count("- ["), 5)
        self.assertLess(section.index("post-7"), section.index("post-6"))
        self.assertIn("2026-01-07", section)
        self.assertNotIn("post-2", section)

    def test_friendly_release_name_keeps_version_visible(self) -> None:
        releases = generate.parse_releases(
            "alpha", [release("Spring edition", tag_name="v2.0")]
        )
        section = (
            generate.render_profile([], releases, [])
            .split("## Latest releases")[1]
            .split("## ")[0]
        )
        self.assertIn(r"v2\.0", section.split("](")[0])
        self.assertIn("Spring edition", section)

    def test_timezone_sorting_and_stable_ties(self) -> None:
        repos = generate.parse_repositories(
            [
                repo("zeta", pushed_at="2026-01-01T01:00:00+02:00"),
                repo("beta"),
                repo("alpha"),
            ]
        )
        output = generate.render_profile(repos, [], [])
        recent = output.split("## Recent activity")[1].split("## ")[0]
        self.assertLess(recent.index("alpha"), recent.index("beta"))
        self.assertLess(recent.index("beta"), recent.index("zeta"))

    def test_external_text_and_links_cannot_break_markdown(self) -> None:
        repos = generate.parse_repositories(
            [
                repo(
                    "a[b]",
                    description="<details> *bold*\n[link](evil) & text",
                    html_url="https://example.com/a(b)",
                )
            ]
        )
        output = generate.render_profile(repos, [], [])
        self.assertIn(r"a\[b\]", output)
        self.assertIn("&lt;details&gt;", output)
        self.assertIn(r"\*bold\*", output)
        self.assertIn("https://example.com/a%28b%29", output)
        self.assertNotIn("[link](evil)", output)

    def test_unchanged_output_keeps_inode_and_modified_time(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "README.md"
            self.assertTrue(generate.write_profile(path, "hello\n"))
            before = path.stat()
            self.assertFalse(generate.write_profile(path, "hello\n"))
            after = path.stat()
            self.assertEqual(before.st_ino, after.st_ino)
            self.assertEqual(before.st_mtime_ns, after.st_mtime_ns)
            self.assertTrue(generate.write_profile(path, "changed\n"))
            self.assertEqual(path.read_text(), "changed\n")

    def test_invalid_source_fields_fail(self) -> None:
        for fields in [
            {"pushed_at": "bad"},
            {"private": "false"},
            {"html_url": "javascript:evil"},
        ]:
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                generate.parse_repositories([repo("alpha", **fields)])
        with self.assertRaises(ValueError):
            generate.parse_posts(rss(item("post", "not a date")))
        with self.assertRaises(ValueError):
            generate.parse_posts(b"<html/>")


class HttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(hasattr(generate, "collect"), "HTTP content collection missing")
        self.requests: list[tuple[str, str | None]] = []
        self.responses: dict[str, tuple[int, bytes, dict[str, str]]] = {}
        test = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                test.requests.append((self.path, self.headers.get("Authorization")))
                status, body, headers = test.responses.get(
                    self.path, (404, b"missing", {})
                )
                self.send_response(status)
                for key, value in headers.items():
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: Any) -> None:
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.thread.join)
        self.addCleanup(self.server.shutdown)
        self.respond(
            "/orgs/2389-research/repos?type=public&per_page=100", [repo("alpha")]
        )
        self.respond(
            "/repos/2389-research/alpha/releases?per_page=100", [release("v1")]
        )
        self.responses["/feed"] = (
            200,
            rss(item("research", "01 Jan 2026 00:00:00 +0000")),
            {},
        )

    def respond(self, path: str, value: Any, **headers: str) -> None:
        self.responses[path] = (200, json.dumps(value).encode(), headers)

    def test_collect_follows_every_page_and_never_authenticates_rss(self) -> None:
        self.respond(
            "/orgs/2389-research/repos?type=public&per_page=100",
            [repo("alpha")],
            Link=f'<{self.base}/page2>; rel="next"',
        )
        self.respond("/page2", [repo("beta"), repo("secret", private=True)])
        self.respond("/repos/2389-research/beta/releases?per_page=100", [])
        self.respond(
            "/repos/2389-research/alpha/releases?per_page=100",
            [release("v1")],
            Link=f'<{self.base}/releases2>; rel="next"',
        )
        self.respond("/releases2", [release("v2")])
        repos, releases, posts = generate.collect(
            api_url=self.base, feed_url=f"{self.base}/feed", token="fixture-token"
        )
        self.assertEqual([r.name for r in repos], ["alpha", "beta"])
        self.assertEqual([r.tag for r in releases], ["v1", "v2"])
        self.assertEqual(posts[0].title, "research")
        self.assertIn(("/feed", None), self.requests)
        self.assertTrue(
            all(
                token == "Bearer fixture-token"
                for path, token in self.requests
                if path != "/feed"
            )
        )
        self.assertFalse(any("secret" in path for path, _ in self.requests))

    def test_bad_or_failed_sources_preserve_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "README.md"
            path.write_text("last good profile\n")
            for status, body in [
                (500, b"server error"),
                (200, b"bad json"),
                (200, b"{}"),
            ]:
                self.responses["/repos/2389-research/alpha/releases?per_page=100"] = (
                    status,
                    body,
                    {},
                )
                with (
                    self.subTest(status=status, body=body),
                    self.assertRaises(Exception),
                ):
                    generate.refresh(
                        path, api_url=self.base, feed_url=f"{self.base}/feed", token=""
                    )
                self.assertEqual(path.read_text(), "last good profile\n")
            self.respond("/repos/2389-research/alpha/releases?per_page=100", [])
            self.responses["/feed"] = (200, b"<broken", {})
            with self.assertRaises(Exception):
                generate.refresh(
                    path, api_url=self.base, feed_url=f"{self.base}/feed", token=""
                )
            self.assertEqual(path.read_text(), "last good profile\n")

    def test_refresh_renders_star_counts_from_every_repository_page(self) -> None:
        self.respond(
            "/orgs/2389-research/repos?type=public&per_page=100",
            [repo("alpha", stargazers_count=9)],
            Link=f'<{self.base}/page2>; rel="next"',
        )
        self.respond(
            "/page2",
            [
                repo("beta", stargazers_count=100, archived=True, fork=True),
                repo("secret", private=True, stargazers_count=999),
            ],
        )
        self.respond("/repos/2389-research/beta/releases?per_page=100", [])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "README.md"
            generate.refresh(path, api_url=self.base, feed_url=f"{self.base}/feed")
            output = path.read_text()
        self.assertIn("## Top starred repos", output)
        section = output.split("## Top starred repos")[1].split("## ")[0]
        self.assertLess(section.index("beta"), section.index("alpha"))
        self.assertIn("(archived, fork) — Useful code — 100 stars", section)
        self.assertIn("Useful code — 9 stars", section)
        self.assertNotIn("secret", output)
        self.assertEqual(len(self.requests), 5)

    def test_http_failure_reports_status_without_retaining_open_response(self) -> None:
        self.responses["/failure"] = (503, b"unavailable", {})
        with self.assertRaisesRegex(OSError, "HTTP 503 from") as failure:
            generate.fetch(f"{self.base}/failure")
        self.assertEqual(type(failure.exception), OSError)

    def test_pagination_cannot_leave_api_origin_or_repeat(self) -> None:
        path = "/orgs/2389-research/repos?type=public&per_page=100"
        for target in [f"{self.base}{path}", "https://example.com/steal"]:
            self.respond(path, [repo("alpha")], Link=f'<{target}>; rel="next"')
            with self.subTest(target=target), self.assertRaises(ValueError):
                generate.collect(
                    api_url=self.base,
                    feed_url=f"{self.base}/feed",
                    token="fixture-token",
                )


if __name__ == "__main__":
    unittest.main()
