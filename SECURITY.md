# Security

## Which versions are supported

Only the latest release gets fixes. If you are on an older one, upgrade first (see [docs/UPGRADE.md](docs/UPGRADE.md)).

## Reporting a problem privately

Please do not open a public issue for a security problem. Use GitHub's private reporting instead: open the **Security** tab of this repository and choose **Report a vulnerability**. If you cannot use GitHub, write to security@aigrceler.com instead. Describe what you did, what you expected and what happened, and the release number (it is in the file `VERSION`).

This is a one-person project, so there is no promised response time. Reports are read and answered as soon as the maintainer can, and a fix goes out as a new release with a note in the changelog.

## What counts

Examples of what to report:

- the engine accepts a change it should refuse (a decision without the decision-maker's own words, a control verified by its own owner, a stage started by someone outside AI Governance);
- the decision journal or an evidence fingerprint can be changed without the engine noticing;
- a command writes or reads outside the company folder;
- any file in a release that runs code you would not expect, or contains a secret, a private name or a local path.

## What to know about how it works

- AIGRCeler keeps its records as plain files on the computer where it runs. Protect that folder the way you protect any sensitive company record, and back it up.
- A person is identified by the name typed with `--by`, not by a login. The journal says so (`unsigned`). If your auditors need signed identities, add them outside the framework.
- The engine uses only Python's standard library and makes no network calls of its own. Claude Code, which runs the agents, has its own settings and terms; what you put in a conversation is handled by the AI service you use with it.
