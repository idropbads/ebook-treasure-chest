# Free bulk translation

The workflow is manual only: GitHub repository > Actions > Free English Catalog Translation > Run workflow > main. Forks may require enabling Actions first. If permission settings block commits, allow GitHub Actions read/write repository contents. Do not add an API key.

Only public repositories run this job. It uses the standard ubuntu-latest runner, a locally loaded Helsinki-NLP/opus-mt-zh-en model, and no paid translation API, larger runner, uploaded artifact, or Actions cache. Dependencies and model weights download on each run. Model: https://huggingface.co/Helsinki-NLP/opus-mt-zh-en (Helsinki-NLP / OPUS-MT, CC-BY-4.0).

Each run translates for up to about one hour after model loading. Re-run until the status report shows all categories translated and no unresolved issues. There is no schedule and no background process started by adding these files. Runtime and completion are not guaranteed; failed or unsupported text requires review. Check the workflow log when a run fails.

Outputs appear under catalog/en/bulk: README.md is the alphabetical index; status.json reports progress and errors; translations.json is the reusable translation dictionary. Long inputs that cannot safely be translated are flagged instead of truncated. The script translates source table columns and non-heading prose, including descriptions when actually present. It does not invent descriptions. Mixed URL/text fields needing review prevent that category from being marked complete.

Original md files, website, main README, authors, links, and the three existing manually translated pages are not overwritten. The bulk index links to those three pages. English translations of author names are machine renderings, not verified identities; originals are retained. Preserve attribution and the source rights notice; that notice does not establish download authorization. Ebook contents are not translated.
