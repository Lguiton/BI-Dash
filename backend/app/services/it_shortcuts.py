"""Windows keyboard shortcut cheat sheet for the IT dashboard. Keys are the documented Windows 10/11 shortcuts; (11) marks Windows 11 only."""
from __future__ import annotations

GROUPS: dict[str, list[tuple[str, str]]] = {
    "Everyday editing": [
        ("Ctrl+C", "Copy"), ("Ctrl+X", "Cut"), ("Ctrl+V", "Paste"), ("Ctrl+Z", "Undo"), ("Ctrl+Y", "Redo"), ("Ctrl+A", "Select all"), ("Ctrl+S", "Save"),
        ("Ctrl+F", "Find"), ("Ctrl+P", "Print"), ("Ctrl+N", "New window or document"), ("Ctrl+B / Ctrl+I / Ctrl+U", "Bold, italic, underline"),
        ("Ctrl+Shift+V", "Paste as plain text (most apps)"), ("Win+V", "Clipboard history (turn it on first)"), ("Ctrl+Backspace", "Delete the previous word"),
    ],
    "Windows and desktop": [
        ("Win", "Open Start"), ("Win+D", "Show or hide the desktop"), ("Win+E", "File Explorer"), ("Win+I", "Settings"), ("Win+L", "Lock the PC"),
        ("Win+R", "Run box"), ("Win+X", "Quick-link (power user) menu"), ("Win+Tab", "Task view and virtual desktops"), ("Win+Ctrl+D", "New virtual desktop"),
        ("Win+Ctrl+Left / Right", "Switch virtual desktop"), ("Win+Ctrl+F4", "Close the current virtual desktop"), ("Win+M", "Minimize all windows"),
        ("Win+Shift+M", "Restore minimized windows"), ("Win+Home", "Minimize everything except the active window"), ("Win+P", "Project to a second screen"),
        ("Win+A", "Quick settings (11) / Action center (10)"), ("Win+N", "Notification center (11)"), ("Win+W", "Widgets (11)"), ("Win+K", "Cast to a wireless display"),
        ("Win+,", "Peek at the desktop while held"), ("Win+Pause", "System properties"), ("Win+U", "Accessibility settings"), ("Win+.  or  Win+;", "Emoji and symbols panel"),
    ],
    "Window snapping": [
        ("Win+Left / Right", "Snap window to the left or right half"), ("Win+Up", "Maximize"), ("Win+Down", "Restore, then minimize"), ("Win+Shift+Left / Right", "Move a window to the other monitor"),
        ("Win+Z", "Snap layouts (11)"), ("Alt+Space", "Window menu (move, size, close)"),
    ],
    "Switching and closing": [
        ("Alt+Tab", "Switch between open apps"), ("Ctrl+Alt+Tab", "Switch apps and keep the switcher open"), ("Alt+Esc", "Cycle windows in the order opened"),
        ("Alt+F4", "Close the active window (on the desktop: Shut down dialog)"), ("Ctrl+W  or  Ctrl+F4", "Close the current tab or document"), ("Ctrl+Shift+Esc", "Task Manager"),
        ("Ctrl+Alt+Del", "Security screen: lock, switch user, sign out, Task Manager"), ("Win+1 to 9", "Open or switch to the taskbar app in that position"),
        ("Win+T", "Cycle through taskbar icons"), ("Win+B", "Focus the notification area"),
    ],
    "File Explorer": [
        ("F2", "Rename"), ("F5", "Refresh"), ("F3  or  Ctrl+E", "Search"), ("Alt+Left / Right", "Back or forward"), ("Alt+Up", "Up one folder"), ("Alt+Enter", "Properties"),
        ("Ctrl+Shift+N", "New folder"), ("Ctrl+L  or  Alt+D", "Select the address bar"), ("Shift+Delete", "Delete permanently, skipping the Recycle Bin"), ("Delete", "Send to the Recycle Bin"),
        ("Ctrl+Mouse wheel", "Change icon size"), ("Alt+P", "Preview pane"), ("Ctrl+Shift+E", "Show all folders above the current one"), ("Backspace", "Back"),
        ("Hold Ctrl and drag", "Copy a file instead of moving it"),
    ],
    "Screenshots and recording": [
        ("PrtScn", "Copy the whole screen (opens Snipping Tool if enabled)"), ("Win+Shift+S", "Snipping Tool: region, window or full-screen capture to the clipboard"),
        ("Win+PrtScn", "Save a full-screen screenshot to Pictures > Screenshots"), ("Alt+PrtScn", "Copy only the active window"), ("Win+G", "Xbox Game Bar (also records a window)"),
        ("Win+Alt+R", "Start or stop a Game Bar recording"), ("Win+Alt+PrtScn", "Save a Game Bar screenshot"),
    ],
    "Text navigation and selection": [
        ("Ctrl+Left / Right", "Move one word"), ("Ctrl+Up / Down", "Move one paragraph"), ("Home / End", "Start or end of the line"), ("Ctrl+Home / End", "Start or end of the document"),
        ("Shift+Arrow", "Extend the selection"), ("Ctrl+Shift+Left / Right", "Select a word at a time"), ("Shift+Home / End", "Select to the line start or end"), ("Ctrl+Shift+Home / End", "Select to the document start or end"),
        ("Page Up / Down", "Scroll one screen"),
    ],
    "Browser (Edge, Chrome, Firefox)": [
        ("Ctrl+T", "New tab"), ("Ctrl+Shift+T", "Reopen the last closed tab"), ("Ctrl+Tab / Ctrl+Shift+Tab", "Next or previous tab"), ("Ctrl+1 to 8", "Jump to that tab"), ("Ctrl+9", "Jump to the last tab"),
        ("Ctrl+L  or  F6", "Select the address bar"), ("Ctrl+D", "Bookmark the page"), ("Ctrl+H", "History"), ("Ctrl+J", "Downloads"), ("Ctrl+Shift+N", "Private window (InPrivate in Edge, Incognito in Chrome)"),
        ("Ctrl+Shift+Delete", "Clear browsing data"), ("F5  or  Ctrl+R", "Reload"), ("Ctrl+F5  or  Ctrl+Shift+R", "Reload ignoring the cache"), ("F12  or  Ctrl+Shift+I", "Developer tools"),
        ("Ctrl+Plus / Minus / 0", "Zoom in, out, reset"), ("Alt+Home", "Home page"),
    ],
    "Command Prompt and PowerShell": [
        ("Up / Down", "Previous or next command"), ("F7", "Command history list (Command Prompt)"), ("Tab", "Complete a file or folder name"), ("Ctrl+C", "Stop the running command (copy when text is selected, in Windows Terminal)"),
        ("Ctrl+Shift+C / V", "Copy or paste (Windows Terminal)"), ("Ctrl+L", "Clear the screen (PowerShell, Windows Terminal)"), ("Ctrl+Shift+T", "New tab (Windows Terminal)"), ("Ctrl+R", "Search command history (PowerShell)"),
        ("Win+X then I", "Open Terminal (11) from the quick-link menu"), ("Shift+Right-click in a folder", "Open a command window or terminal here"),
    ],
    "Troubleshooting and IT tools": [
        ("Win+R then  msconfig", "System Configuration (startup and boot options)"), ("Win+R then  services.msc", "Services"), ("Win+R then  devmgmt.msc", "Device Manager"),
        ("Win+R then  diskmgmt.msc", "Disk Management"), ("Win+R then  eventvwr.msc", "Event Viewer"), ("Win+R then  compmgmt.msc", "Computer Management"), ("Win+R then  appwiz.cpl", "Programs and Features (uninstall)"),
        ("Win+R then  ncpa.cpl", "Network adapters"), ("Win+R then  control", "Control Panel"), ("Win+R then  taskmgr", "Task Manager"), ("Win+R then  regedit", "Registry Editor (careful: back up first)"),
        ("Win+R then  gpedit.msc", "Group Policy Editor (Pro and above)"), ("Win+R then  lusrmgr.msc", "Local users and groups (Pro and above)"), ("Win+R then  perfmon", "Performance Monitor"),
        ("Win+R then  resmon", "Resource Monitor"), ("Win+R then  mstsc", "Remote Desktop connection"), ("Win+R then  cmd  /  powershell", "Command Prompt / PowerShell"),
        ("Win+Ctrl+Shift+B", "Restart the graphics driver (fixes a black or frozen screen)"), ("Win+Ctrl+O", "On-screen keyboard"), ("Hold Shift while clicking Restart", "Boot to the recovery options"),
        ("F8  or  Shift+F8", "Older recovery key; on modern PCs use Shift+Restart or Settings > Recovery"), ("Ctrl+Shift+Click an app", "Run it as administrator"),
    ],
    "Accessibility": [
        ("Win+Plus / Minus", "Magnifier on, zoom in or out"), ("Win+Esc", "Close Magnifier"), ("Win+Ctrl+Enter", "Narrator on or off"), ("Win+Ctrl+C", "Color filters (if enabled)"),
        ("Shift x5", "Sticky Keys prompt"), ("Hold right Shift 8 s", "Filter Keys prompt"), ("Win+H", "Voice typing"),
    ],
}
NOTE = "Shortcuts follow Microsoft's documented Windows 10 and 11 keys. Items marked (11) are Windows 11 only. App-specific keys can differ by version, so test a shortcut before you teach it."


def sheet() -> dict:
    groups = {g: [{"keys": k, "what": w} for k, w in rows] for g, rows in GROUPS.items()}
    return {"groups": groups, "count": sum(len(v) for v in groups.values()), "note": NOTE}
