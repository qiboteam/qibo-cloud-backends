"""Authentication and project-context helpers for qnexus."""

from __future__ import annotations

from typing import Any

from .nexus_errors import NexusAuthError


def authenticate(*, credential_login: bool | None) -> None:
    """Authenticate with Nexus using credential or interactive login."""

    try:
        import qnexus as qnx
    except Exception as exc:  # pragma: no cover - import environment specific
        raise NexusAuthError("qnexus is not installed. Cannot authenticate to Nexus.") from exc

    try:
        if credential_login:
            qnx.login_with_credentials()
            return

        # Headless default: rely on pre-configured token/session managed by qnexus.
        # Avoid forcing interactive login in automated environments.
        print("Using pre-configured Nexus session/token. If this fails later, run 'python -c \"import qnexus as qnx; qnx.login()\"' to log in interactively or set 'credential_login=True' for credential-based login.")
        return
    except Exception as exc:
        raise NexusAuthError(f"Failed Nexus authentication: {exc}") from exc


def ensure_project(project_name: str | None) -> Any:
    """Return a Nexus ProjectRef, creating it if needed."""

    if project_name is None:
        return None

    try:
        import qnexus as qnx
    except Exception as exc:  # pragma: no cover - import environment specific
        raise NexusAuthError("qnexus is not installed. Cannot create/get project.") from exc

    try:
        get_or_create = qnx.projects.get_or_create
        try:
            return get_or_create(name=project_name)
        except TypeError:
            return get_or_create(project_name)
    except Exception as exc:
        raise NexusAuthError(f"Failed to initialize Nexus project '{project_name}': {exc}") from exc
