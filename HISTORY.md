# Project History & Critical Decisions

## 2026-01-21: System Recovery & Rebranding
- **Git History Cleanup**: Removed sensitive `.env` file and large `ffmpeg` folder from git history using `git filter-branch`.
- **Data Loss Incident**: The cleanup process inadvertently removed untracked backend files (`settings_api`, `models`) and the frontend `components` directory.
- **Recovery**:
  - **Backend**: Manually reconstructed `ldap_model.py`, `settings_model.py`, `ldap.py`, and `settings_routes.py`.
  - **Frontend**: Re-initialized `shadcn` UI library and restored custom components (`AdminModal`, `SystemSettings`, `ThemeContext`).
- **Rebranding**: Renamed project content from "Sovia" to "**aidox**".
- **Theme Reset**: `shadcn` re-installation reset the theme to default Teal. Restored "**Project Red**" branding in `index.css`.

## 2026-01-21: Feature Implementations
- **LDAP**: Integrated LDAP authentication and settings management.
- **System Status**: Added health check endpoint and UI indicator.
- **UI Refinement**: Changed Theme Toggle from dropdown to side-by-side buttons.
