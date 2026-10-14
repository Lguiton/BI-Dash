BI Dashboard: install on any computer
=====================================
1. Install Python 3.11+ and Node 20+ (once per computer).
2. Unzip this folder anywhere.
3. Run the installer for your system (once):
     Windows:      double-click installer\install.bat
     Mac/Linux/WSL: bash installer/install.sh
4. Start it any time:
     Windows:      double-click installer\start.bat
     Mac/Linux/WSL: bash installer/start.sh
5. Open http://localhost:3012

Each computer has its own databases and backups. Nothing syncs between computers.
To move your data: Settings > Export everything on the old one, then import the CSVs
(My data > Import) on the new one, or copy the backend/data folder while the app is stopped.
AI keys go in backend/.env (never shared by the zip; every computer needs its own).
The dashboard listens on this computer only (127.0.0.1). Don't expose it to a network: there is no login.

The install step needs internet once (packages and the Geist font are downloaded). After that it runs offline.

Two editions
------------
* Someone else: give them bi_install.zip as it is. No data, no keys.
* Your own computers: on your main computer, stop the app, then run
    Windows: installer\make_personal_bundle.bat     Mac/Linux: python3 installer/make_personal_bundle.py
  That writes bi_personal_bundle_<date>.zip next to the app folder, containing the app AND your databases,
  backups, models and backend/.env. Unzip it on your other computer and run the installer there.
  Keep that zip private. Re-make it whenever you want the other computer to catch up.
Both computers then have a COPY. Changes on one don't appear on the other unless you carry a fresh bundle over.
Never run two copies on the same database files at once (for example through a synced folder); the database can be damaged.
