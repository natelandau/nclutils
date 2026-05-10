"""Git utilities built on top of nclutils.sh."""

from .runner import NotARepoError, run_git

__all__ = [
    "NotARepoError",
    "run_git",
]
