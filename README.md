# 2389 Research GitHub profile

The organization's public profile is [profile/README.md](profile/README.md).
`profile/generate.py` builds it from live public data; edit the generator to
change its layout or introduction.

The profile starts with the supplied 2389 block-character wordmark in a monospace
code block. Its source lives in the generator so refreshes preserve the header.

## What appears

- Eight recently pushed, active public repos, ordered by `pushed_at`. The profile
  repository is excluded from this section to avoid promoting its own refreshes.
- The latest published GitHub Release from each of the ten most recently released
  projects. Drafts are excluded; prereleases are labeled. Git tags without a release
  do not appear.
- Five latest posts from [the writing RSS feed](https://2389.ai/research/writing/index.xml).
- Ten public repos with the most stars, with counts, descriptions, and fork/archive
  labels. Ties sort alphabetically, ignoring case first. All public repos qualify;
  star counts come from the existing repository requests.
- A topic cloud linking the 30 most-used topics to generated pages with all matching
  public repos, sorted by stars. Counts include forks and archived projects and
  count each repo once per topic. Ties sort by topic name; topics with at least half
  the largest count appear bold. The cloud and pages reuse the repository snapshot.
- An alphabetical, expandable table of **every public repo**, with names,
  descriptions, and alphabetized topics. Forks and archived projects keep their
  labels. Empty descriptions and topic lists display an em dash. Topics come from
  the existing repository responses. Repository and release requests fetch all pages.

Dates use UTC. Descriptions come from GitHub; update a repository's description
there to change its listing. The company links and introduction live in the
generator. There is no hand-maintained second repository list.

## Local use

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and
[actionlint](https://github.com/rhysd/actionlint/blob/main/docs/install.md).
The project uses Python 3.12 or newer, no runtime packages, and locked Ruff/mypy
development tools.

```sh
uv sync --locked
scripts/check
```

Generate the profile using a GitHub token. The public org exceeds the
unauthenticated API's hourly request allowance when releases are included.
The token needs only read access to public data. If using GitHub CLI:

```sh
GH_TOKEN="$(gh auth token)" uv run --locked python profile/generate.py
```

`GITHUB_TOKEN` also works. The token is sent only to GitHub, never to the RSS
server. `--output PATH` writes a preview elsewhere, with topic pages in a sibling
`topics` directory; `--help` shows usage. Topic links use GitHub's `blob/HEAD` URLs
and become live after the pages reach the default branch. Files in `profile/topics`
are generated; edit repository topics on GitHub to change membership. Refreshes
remove stale marked pages, preserve unrelated files, and reject unmarked filename
collisions before writing.

Run the live end-to-end test against GitHub and the RSS feed:

```sh
GH_TOKEN="$(gh auth token)" uv run --locked python -m unittest discover -s tests -p 'e2e_*.py'
```

Offline unit/integration tests use local data and a local HTTP server. Live
tests use real APIs and a temporary output directory.

## Daily updates

[Update profile](.github/workflows/update-profile.yml) runs daily at **11:23 UTC**
and supports **Run workflow** in GitHub Actions. It uses the built-in
`GITHUB_TOKEN`; no personal token or extra repository secret is needed.
It runs generator tests, fetches the sources, and commits changed `profile/README.md`
and generated `profile/topics` pages, including additions and removals. Identical
data leaves every file untouched and produces no commit. Fetch or parsing failures
fail the job and leave the previous profile and topic pages intact. All content is
rendered before writes; each changed file is replaced atomically.

The schedule becomes active after the workflow merges into the default branch.
The job writes to that branch; branch rules must permit the bot's commit.
Concurrent refreshes are serialized, and a conflicting branch update fails the
push safely without a force push. Rerun the workflow after resolving a failure.

GitHub schedules are best effort and can be delayed. GitHub also disables
scheduled workflows in public repos after 60 days without repository activity;
if that happens, re-enable this workflow from Actions. These are
[GitHub platform limits](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

[Check](.github/workflows/check.yml) runs offline verification on pushes and
pull requests. The [implementation plan](docs/superpowers/plans/2026-10-04-profile.md)
records scope and validation; [gotchas.md](gotchas.md) records source decisions.
