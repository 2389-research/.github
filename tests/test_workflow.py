# ABOUTME: Exercises the update workflow's commit step with real local Git repositories.
# ABOUTME: Checks topic-only commits and leaves unrelated files untouched.
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class WorkflowCommitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / "checkout"
        self.repo.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Profile test")
        self.git("config", "user.email", "profile-test@example.com")
        self.git("init", "--bare", str(self.root / "remote.git"))
        self.git("remote", "add", "origin", str(self.root / "remote.git"))
        self.profile = self.repo / "profile"
        self.profile.mkdir()
        (self.profile / "README.md").write_text("Profile\n")
        self.topics = self.profile / "topics"
        self.topics.mkdir()
        self.git("add", "profile/README.md")
        self.git("commit", "-m", "test: seed profile")
        self.git("push", "-u", "origin", "main")
        workflow = (ROOT / ".github/workflows/update-profile.yml").read_text()
        self.script = textwrap.dedent(
            workflow.split("      - name: Commit changed content\n        run: |\n")[1]
        )

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=self.repo, check=True, capture_output=True, text=True
        ).stdout.strip()

    def publish(self) -> None:
        result = subprocess.run(
            ["bash", "-eo", "pipefail", "-c", self.script],
            cwd=self.repo,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_topic_only_additions_edits_and_removals_are_committed_and_pushed(
        self,
    ) -> None:
        page = self.topics / "agents.md"
        for content in ["First topic page\n", "Updated topic page\n", None]:
            with self.subTest(content=content):
                before = self.git("rev-parse", "HEAD")
                if content is None:
                    page.unlink()
                else:
                    page.write_text(content)
                self.publish()
                after = self.git("rev-parse", "HEAD")
                self.assertNotEqual(before, after)
                self.assertEqual(self.git("rev-parse", "origin/main"), after)
                self.assertEqual(self.git("status", "--porcelain"), "")
                self.assertEqual(self.git("show", "HEAD:profile/README.md"), "Profile")

    def test_unchanged_outputs_and_unrelated_files_do_not_create_a_commit(self) -> None:
        (self.repo / "notes.md").write_text("Local notes\n")
        before = self.git("rev-parse", "HEAD")
        self.publish()
        self.assertEqual(self.git("rev-parse", "HEAD"), before)
        self.assertEqual(self.git("status", "--porcelain"), "?? notes.md")

    def test_profile_changes_do_not_stage_unrelated_files(self) -> None:
        (self.repo / "notes.md").write_text("Local notes\n")
        (self.profile / "README.md").write_text("Updated profile\n")
        before = self.git("rev-parse", "HEAD")
        self.publish()
        self.assertNotEqual(self.git("rev-parse", "HEAD"), before)
        self.assertEqual(self.git("status", "--porcelain"), "?? notes.md")


if __name__ == "__main__":
    unittest.main()
