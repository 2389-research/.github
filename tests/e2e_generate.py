# ABOUTME: Runs the actual generator CLI against live GitHub and research RSS sources.
# ABOUTME: Checks the complete public repository directory in a temporary output file.
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


class LiveProfileTests(unittest.TestCase):
    def test_public_sources_generate_complete_profile(self) -> None:
        headers = {"User-Agent": "2389-profile-e2e"}
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        url = "https://api.github.com/orgs/2389-research/repos?type=public&per_page=100"
        names: set[str] = set()
        topic_members: dict[str, set[str]] = {}
        while url:
            with urlopen(Request(url, headers=headers), timeout=30) as response:
                for repository in json.load(response):
                    if repository["private"]:
                        continue
                    names.add(repository["name"])
                    for topic in set(repository["topics"]):
                        topic_members.setdefault(topic, set()).add(repository["name"])
                next_page = re.search(
                    r'<([^>]+)>;\s*rel="next"', response.headers.get("Link", "")
                )
                url = next_page[1] if next_page else ""
        self.assertGreater(len(names), 0)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "README.md"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "profile/generate.py"),
                    "--output",
                    str(output),
                ],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=600,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, "")
            content = output.read_text()
            directory_section = content.split("<details>")[1]
            self.assertIn("| Name | Description | Topics |", directory_section)
            self.assertEqual(directory_section.count("| ["), len(names))
            for name in names:
                self.assertIn(
                    f"](https://github.com/2389-research/{name})", directory_section
                )
            self.assertIn("## Top starred repos", content)
            top_starred = content.split("## Top starred repos")[1].split("## ")[0]
            ranked = re.findall(
                r"^- \[.*\]\(https://github.com/2389-research/([^)]*)\)"
                r".* — (\d+) stars$",
                top_starred,
                re.MULTILINE,
            )
            ranking = [(name, int(count)) for name, count in ranked]
            self.assertEqual(len(ranking), min(10, len(names)))
            self.assertEqual(len({name for name, _ in ranking}), len(ranking))
            for name, count in ranking:
                self.assertIn(name, names)
                self.assertGreaterEqual(count, 0)
            self.assertEqual(
                ranking,
                sorted(ranking, key=lambda row: (-row[1], row[0].casefold(), row[0])),
            )
            cloud = content.split("## Topics")[1].split("## ")[0]
            targets = re.findall(r"blob/HEAD/profile/topics/([^)]*)", cloud)
            expected_topics = sorted(
                topic_members,
                key=lambda topic: (-len(topic_members[topic]), topic.casefold(), topic),
            )[:30]
            self.assertEqual(
                [unquote(unquote(target)[:-3]) for target in targets], expected_topics
            )
            topic_directory = output.parent / "topics"
            self.assertEqual(
                {page.name for page in topic_directory.iterdir()},
                {unquote(target) for target in targets},
            )
            for target in targets:
                filename = unquote(target)
                topic = unquote(filename[:-3])
                page = (topic_directory / filename).read_text()
                self.assertIn("| Name | Description | Stars |", page)
                self.assertIn(f"{len(topic_members[topic])} public repositories", page)
                members = re.findall(
                    r"^\| \[.*?\]\(https://github.com/2389-research/([^)]*)\)"
                    r".* \| (\d+) \|$",
                    page,
                    re.MULTILINE,
                )
                self.assertEqual({name for name, _ in members}, topic_members[topic])
                self.assertEqual(len(members), len(topic_members[topic]))
                ranking = [(name, int(count)) for name, count in members]
                self.assertEqual(
                    ranking,
                    sorted(
                        ranking, key=lambda row: (-row[1], row[0].casefold(), row[0])
                    ),
                )
            releases = content.split("## Latest releases")[1].split("## ")[0]
            self.assertIn("/releases/tag/", releases)
            self.assertGreater(releases.count("- ["), 0)
            self.assertLessEqual(releases.count("- ["), 10)
            release_projects = re.findall(
                r"\]\(https://github.com/2389-research/([^/]+)/releases/tag/", releases
            )
            self.assertEqual(len(release_projects), releases.count("- ["))
            self.assertEqual(len(set(release_projects)), len(release_projects))
            self.assertTrue(set(release_projects).issubset(names))
            research = content.split("## Latest research")[1].split("## ")[0]
            self.assertIn("https://2389.ai/research/", research)
            self.assertGreater(research.count("- ["), 0)
            self.assertLessEqual(research.count("- ["), 5)


if __name__ == "__main__":
    unittest.main()
