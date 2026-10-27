# Upgrading AIGRCeler

Your company's records are kept outside the framework items, so upgrading means replacing the framework and leaving the records alone.

## Every upgrade

1. **Back up** the company root. Copy the whole folder somewhere else.
2. **Find your release.** It is written in `.claude\shared\VERSION`, and `py -3 .claude\shared\engine\aigrceler.py ws release` prints it (`ws status` shows it too).
3. **Read the changelog** (`CHANGELOG.md`) for every release between yours and the one you are moving to. Lines marked *Breaking* say what needs doing to existing records. A release whose first number goes up (for example 2.x to 3.0) can change records, commands or control IDs; read its section below before you start.
4. **Replace the framework.** In the company root, replace `.claude\`, `CLAUDE.md` and `aigrceler.ps1` with the ones from the new release. Do not touch `data\`, `catalog\`, `decisions\`, `00-status\` or `projects\`.
5. **Check.** Run the menu and the status command again, and run the self-test if you like: `py -3 .claude\shared\testing\selftest.py`.

The company's control catalog is the company's own. A new release can bring a new starter catalog as a file; it is never forced on you. AI Governance chooses what to adopt, through proposals.

## By release

### 2.0.0

The first public release. There is no earlier public version, so there is nothing to upgrade from. Start with [INSTALL.md](INSTALL.md).
