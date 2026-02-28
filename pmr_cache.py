"""
pmr_cache.py — Local cache manager for PMR instance data.

Directory structure:
    <base_folder>/
    ├── .pmr-instance          # Plain text file containing the PMR instance URL
    ├── workspaces.json        # Workspace metadata, keyed by workspace ID
    └── repos/                 # Cloned git repositories
        └── <workspace-id>/
            └── <repo-name>/
"""

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ==============================================================================
# Module-level logger
# (each module in your project should do this — they all feed into the
#  root "pmr" logger that gets configured once in main())
# ==============================================================================

import logging
log = logging.getLogger("pmr.cache")

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class CacheError(Exception):
    """Base exception for cache-related errors."""


class InstanceMismatchError(CacheError):
    """Raised when the cache folder belongs to a different PMR instance."""

    def __init__(self, base_folder: Path, expected: str, found: str):
        self.base_folder = base_folder
        self.expected = expected
        self.found = found
        super().__init__(
            f"Cache at '{base_folder}' is for PMR instance '{found}', "
            f"but you requested '{expected}'. "
            f"Use a different base folder or pass the correct instance URL."
        )


class CacheNotInitialisedError(CacheError):
    """Raised when the cache folder exists but is missing required files."""


# ---------------------------------------------------------------------------
# Internal file/folder names
# ---------------------------------------------------------------------------

_INSTANCE_FILE = ".pmr-instance"
_WORKSPACES_FILE = "workspaces.json"
_REPOS_DIR = "repos"


# ---------------------------------------------------------------------------
# Workspace data model
# ---------------------------------------------------------------------------

@dataclass
class Workspace:
    """Metadata for a single PMR workspace."""
    href: str
    id: str
    title: str
    owner: str
    description: str = ""
    latest_exposure: dict[str, Any] = field(default_factory=dict)
    cached_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "href": self.href,
            "id": self.id,
            "title": self.title,
            "owner": self.owner,
            "description": self.description,
            "latest_exposure": self.latest_exposure,
            "cached_at": self.cached_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Workspace":
        return cls(
            href=data["href"],
            id=data["id"],
            title=data["title"],
            owner=data["owner"],
            description=data.get("description", ""),
            latest_exposure=data.get("latest_exposure", {}),
            cached_at=data.get("cached_at", ""),
        )


# ---------------------------------------------------------------------------
# PMRCache
# ---------------------------------------------------------------------------

class PMRCache:
    """
    Manages a local cache of data from a PMR instance.

    Usage
    -----
    Creating a new cache (folder must not yet exist, or be empty):
        cache = PMRCache("/path/to/cache", "https://models.physiomeproject.org")

    Opening an existing cache (validates that the instance URL matches):
        cache = PMRCache("/path/to/cache", "https://models.physiomeproject.org")

    Parameters
    ----------
    base_folder : str | Path
        Root directory for this cache. Created if it does not exist.
    pmr_instance : str
        URL of the PMR instance this cache belongs to (e.g. "https://...").
        Trailing slashes are stripped for consistency.

    Raises
    ------
    InstanceMismatchError
        If the folder exists and is already initialised for a *different* PMR instance.
    CacheNotInitialisedError
        If the folder exists but is missing the instance file (looks corrupted or not a cache folder).
    """

    def __init__(self, base_folder: str | Path, pmr_instance: str):
        self._base = Path(base_folder).resolve()
        self._instance = pmr_instance.rstrip("/")

        if self._base.exists():
            self._open_existing()
        else:
            self._initialise_new()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def base_folder(self) -> Path:
        """Absolute path to the cache root directory."""
        return self._base

    @property
    def pmr_instance(self) -> str:
        """URL of the PMR instance this cache is bound to."""
        return self._instance

    @property
    def repos_dir(self) -> Path:
        """Directory containing cloned git repositories."""
        return self._base / _REPOS_DIR

    # ------------------------------------------------------------------
    # Workspace API
    # ------------------------------------------------------------------

    def get_workspace(self, workspace_id: str) -> Workspace | None:
        """Return a cached Workspace by ID, or None if not found."""
        data = self._load_workspaces()
        entry = data.get(workspace_id)
        return Workspace.from_dict(entry) if entry else None

    def list_workspaces(self) -> list[Workspace]:
        """Return all cached workspaces, sorted by name."""
        data = self._load_workspaces()
        workspaces = [Workspace.from_dict(v) for v in data.values()]
        return sorted(workspaces, key=lambda w: w.name.lower())

    def upsert_workspace(self, workspace: Workspace) -> None:
        """Add or update a workspace entry in the cache."""
        data = self._load_workspaces()
        data[workspace.href] = workspace.to_dict()
        self._save_workspaces(data)

    def delete_workspace(self, workspace_id: str, delete_repo: bool = False) -> bool:
        """
        Remove a workspace from the cache.

        Parameters
        ----------
        workspace_id : str
        delete_repo : bool
            If True, also delete any cloned repo for this workspace.

        Returns
        -------
        bool
            True if the workspace was found and removed, False if it was not cached.
        """
        data = self._load_workspaces()
        if workspace_id not in data:
            return False

        del data[workspace_id]
        self._save_workspaces(data)

        if delete_repo:
            repo_path = self.repos_dir / workspace_id
            if repo_path.exists():
                shutil.rmtree(repo_path)

        return True

    # ------------------------------------------------------------------
    # Repository path helpers
    # ------------------------------------------------------------------

    def repo_path(self, workspace_id: str, repo_name: str = "") -> Path:
        """
        Return the expected local path for a cloned repo.

        Parameters
        ----------
        workspace_id : str
        repo_name : str
            Optional sub-folder within the workspace repo directory.
            If omitted, returns the workspace-level repos folder.
        """
        path = self.repos_dir / workspace_id
        if repo_name:
            path = path / repo_name
        return path

    def is_repo_cloned(self, workspace_id: str, repo_name: str = "") -> bool:
        """Return True if the repo directory exists and looks like a git repo."""
        path = self.repo_path(workspace_id, repo_name)
        return (path / ".git").exists()

    # ------------------------------------------------------------------
    # Representation
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        n_workspaces = len(self._load_workspaces())
        return (
            f"PMRCache(\n"
            f"\tbase_folder='{self._base}',\n"
            f"\tpmr_instance='{self._instance}',\n"
            f"\tworkspaces={n_workspaces}\n)"
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _initialise_new(self) -> None:
        """Create and populate a fresh cache directory."""
        self._base.mkdir(parents=True, exist_ok=True)
        (self._base / _REPOS_DIR).mkdir()

        # Write the instance file
        self._instance_file.write_text(self._instance + "\n", encoding="utf-8")

        # Write an empty workspaces store
        self._save_workspaces({})

    def _open_existing(self) -> None:
        """Validate an existing cache directory."""
        instance_file = self._instance_file

        if not instance_file.exists():
            # Folder exists but has no instance file — could be empty or corrupted
            if any(self._base.iterdir()):
                raise CacheNotInitialisedError(
                    f"Cache folder '{self._base}' exists and is non-empty but has no "
                    f"'{_INSTANCE_FILE}' file. It may be corrupted or not a PMR cache."
                )
            # Folder is empty — treat as uninitialised and set it up
            self._initialise_new()
            return

        stored = instance_file.read_text(encoding="utf-8").strip()
        if stored != self._instance:
            raise InstanceMismatchError(self._base, self._instance, stored)

        # Ensure repos dir exists even if someone deleted it by hand
        self.repos_dir.mkdir(exist_ok=True)

        # Ensure workspaces file exists
        if not self._workspaces_file.exists():
            self._save_workspaces({})

    @property
    def _instance_file(self) -> Path:
        return self._base / _INSTANCE_FILE

    @property
    def _workspaces_file(self) -> Path:
        return self._base / _WORKSPACES_FILE

    def _load_workspaces(self) -> dict[str, Any]:
        try:
            return json.loads(self._workspaces_file.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_workspaces(self, data: dict[str, Any]) -> None:
        self._workspaces_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )