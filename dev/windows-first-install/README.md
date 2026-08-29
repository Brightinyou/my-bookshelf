# Windows host first-install test

`reset-host.cmd` prepares this PC for a real public-download installation test.
It uses registered uninstallers for Python, Node.js, Obsidian, and My Bookshelf.
CLI files and settings are moved to a timestamped backup instead of deleted.

Preserved without modification:

- `%USERPROFILE%\Documents\My Bookshelf`
- Obsidian vault contents
- `%USERPROFILE%\my-bookshelf`
- Claude Desktop

Close Codex before running the reset because the script removes the Codex CLI
and stops `codex-code-mode-host`. Type `RESET` at its confirmation prompt. When
the reset finishes, the latest public release page opens for downloading
`Setup.exe`.

The timestamped backup also contains the pre-test PATH and installed-package
inventory. Close Codex again after the test, then run `restore-settings.cmd` to
restore My Bookshelf preferences,
Claude/Codex authentication, Obsidian settings, CLI files, and the original user
PATH. Reinstalled application versions are left in place.
