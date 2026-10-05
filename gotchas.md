# Profile maintenance

- GitHub organization is `2389-research`; the company is **2389 Research**, not 2398. The company website is `https://2389.ai`.
- Research posts come from `https://2389.ai/research/writing/index.xml`. The parent research feed was empty when checked on 2026-10-04.
- “Tagged releases” means published GitHub Releases, confirmed by Doctor Biz. Draft releases and private repositories must never appear.
- Doctor Biz wants only the latest published release per project, then the ten newest projects by release date. Deduplicate before applying the ten-entry limit so one busy project cannot crowd out the others.
- The org already exceeds GitHub's 100-repo page size. Fetch every page before generating the directory.
- The top-starred section uses `stargazers_count` from the same repository responses. Star counts can change between live API reads; exact ranking expectations belong in stable fixture tests.
