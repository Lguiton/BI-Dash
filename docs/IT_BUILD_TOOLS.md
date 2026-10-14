# Backup lab, inventory agent, Gantt chart and diagram canvas

**Backup lab** (IT tools > Backup lab). An incremental backup engine in the standard library: files are stored once by SHA-256, a snapshot is a list of names and fingerprints, `verify` re-reads every stored file, `restore` checks every fingerprint and refuses unsafe paths or non-empty folders, `drill` restores to a temporary folder and compares with the live folder (recovery time and data at risk), `prune` removes old snapshots and unused files. The practice area uses a private sample folder. The same engine runs on real folders with `python scripts/backup_tool.py` (backup, list, verify, restore, drill, prune). Not built: encryption, compression, scheduling, cloud or network targets, open-file snapshots, database-aware backup. Use restic, Borg or Veeam for important data.

**Inventory agent** (IT tools > Inventory). `scripts/inventory_agent.py` prints a JSON report about one computer: name, kind guess, OS, CPU, cores, RAM, disks, IP addresses, serial, uptime. It reads only, collects no files, apps, users or history, and sends nothing. The app imports reports (one, a list, or one per line), matching by serial then by name; owner, purchase date and warranty are never changed. The script is tested on Linux; the Windows and macOS paths are best-effort and not tested here.

**Gantt chart** (Project and product > Schedule). Bars from the critical-path schedule; drag the end of a bar, or focus it and press the arrow keys, to change the duration. The schedule is recalculated from the dependencies. Red = critical; pale tail = float.

**Free-form diagram canvas** (Diagram studio > Free-form canvas). Add boxes, rounded boxes, decisions, circles and notes; drag, connect, label; export SVG, a file, or Mermaid text. The drawing is kept in the browser. No swimlanes, shape libraries or shared editing.

Files: `services/backup_lab.py`, `services/inventory_agent.py`, `routers/backuplab.py`, `routers/itagent.py`, `scripts/backup_tool.py`, `scripts/inventory_agent.py`, `panels/ItBuild.tsx`, `panels/DiagramCanvas.tsx`, `tests/test_it_build.py`.
