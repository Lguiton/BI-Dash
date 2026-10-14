# Computer control (personal edition)

Run a fixed list of maintenance, settings, network, account and security actions on **this** Windows computer from the dashboard, with a PIN, undo and an automatic fallback.

## Turning it on
It is **off** unless a file named `computer_control.enabled` exists in the project folder (next to `backend` and `frontend`):

    touch computer_control.enabled

Restart the app. **Manage > Computer control** appears. The personal bundle script skips this file, so your other computer stays off, and the plain installer never has it.

## Practice and Real
* **Practice workspace = simulation.** Every button shows the exact command and uses made-up example results. Nothing touches your computer.
* **Real workspace = live.** Actions run on this computer, but only after you arm it with your PIN.

## The guard rails
1. **PIN.** Set once (6 or more characters), stored as a salted scrypt hash. Five wrong tries lock it for five minutes.
2. **Arming.** The PIN gives a random token valid for 15 minutes, held only in that browser tab. Every action must send it. "Lock now" cancels it.
3. **Fixed catalogue.** Only the 51 actions in `backend/app/services/sysactions.py` can run. There is no free-form command box. Inputs are validated and passed to PowerShell as environment variables (`BI_P_...`), so a typed value can never become code.
4. **Preview.** Every action has "Preview command" showing the exact script, what is saved first, and what Undo runs.
5. **Protected things.** Critical Windows services (RPC, Defender, firewall service, event log and others) are refused, and you can't disable the account you are signed in with.
6. **High-risk actions** (firewall, adapters, new users, installs and removals, network reset) also need you to type CONFIRM.
7. **Origin check.** A request from a web page the app doesn't trust is refused.
8. **Activity log.** Every run, refusal, arm and lock is logged. Passwords are never stored or logged.

## Undo and the fallback
* Before a change, the app saves the prior state (service state and start type, firewall profiles, DNS servers, adapter state, the hosts file, a power plan, a startup entry, a user's enabled state). **Undo** puts that back.
* **Auto-revert.** Risky changes (firewall off, DNS change, adapter disabled) revert by themselves after 5, 3 and 2 minutes unless you press **Keep**. If the app is closed first, they revert the next time it runs.
* **Undo everything (last 24 hours)** replays every undoable change, newest first.
* **Restore points.** Firewall changes, a network reset, software removal and "update everything" try to create a Windows restore point first (System Protection must be on; Windows allows one per 24 hours).
* **Not undoable:** deleting temp files, emptying the Recycle Bin, resetting the network stack, uninstalling or updating software. These are labelled.

## Reset the app's own settings
**Reset app settings** returns AI access, blocked columns, backup options and alert and report options to the defaults. A snapshot is saved first and the last five are kept, so **Restore** brings them back. Your data, backups, progress and activity log are untouched.

## Security scans (leads, not verdicts)
Seven read-only scans plus a combined one: protection status (Defender, firewall, UAC, hosts file, proxy), accounts, remote-access tools and Remote Desktop, camera/microphone/location use (Windows' own privacy log), startup items, network connections, running programs. Items are checked for digital signatures and odd locations.

This is **not an antivirus**. Unsigned does not mean malicious; signed does not mean safe. The app can start a Microsoft Defender scan and update its signatures, and read its recent detections; use that for real detection.

## Things to know
* **Administrator.** Many actions need administrator rights. If the app runs inside WSL, start your Windows terminal "as Administrator" before launching it, or those actions will fail with an access-denied message (nothing is changed when they fail).
* **Needs PowerShell.** On Windows, or WSL on Windows (`powershell.exe`). Elsewhere the actions are unavailable.
* **Untested on real Windows.** The scripts were written and unit-tested with a fake PowerShell, not run on a Windows machine. Start with read-only actions and Preview, then low-risk ones, before anything marked high.
* **No login.** The PIN guards computer control, but the rest of the app still has no login; keep it on your own machine.
