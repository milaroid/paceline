---
description: Install the paceline statusline into Claude Code settings
---

Install the paceline statusline for the user.

1. Run the installer with the first Python that exists:

   ```sh
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/install.py" setup || python "${CLAUDE_PLUGIN_ROOT}/scripts/install.py" setup
   ```

2. Show the installer output to the user word for word.
3. If the command fails, show the exact error and stop. Do not edit `settings.json` by hand.
4. On success, tell the user to restart Claude Code or start a new session.
