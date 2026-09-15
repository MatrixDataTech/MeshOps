## Python

- Replace entire methods instead of patching snippets.
- Run compileall before testing.
- Black is your friend.

## Meshtastic

- Don't hold SerialInterface open.
- USB reconnects are normal.
- Device numbers change after reconnects.
- /dev/ttyACM0 is what matters.

## Git

- One architectural change per commit.
- Recover lost code with git diff before rewriting.