---
name: Playwright on NixOS
description: How to run Playwright Chromium on NixOS/Replit — system Chromium required
---

Playwright's downloaded chromium-headless-shell fails on NixOS with "libgbm.so.1 / libnspr4.so not found" because NixOS doesn't expose FHS-style library paths.

**Fix:** Install system Chromium via Nix (installSystemDependencies packages: ["chromium"]) and pass executable_path=shutil.which("chromium") to p.chromium.launch(). The env var PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH is NOT respected — must be in launch() directly.

**Why:** Nix-packaged Chromium is wrapped with correct library paths; Playwright's downloaded binary is not.

**How to apply:** Any Python script using Playwright in Replit:
```python
import shutil
CHROMIUM_EXECUTABLE = shutil.which("chromium") or None
launch_kwargs = {"headless": True}
if CHROMIUM_EXECUTABLE:
    launch_kwargs["executable_path"] = CHROMIUM_EXECUTABLE
browser = p.chromium.launch(**launch_kwargs)
```
