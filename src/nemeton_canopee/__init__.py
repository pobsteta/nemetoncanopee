"""nemetoncanopee : hauteur, volume et biomasse forestière par millésime."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("nemeton-canopee")
except PackageNotFoundError:  # paquet non installé (exécution depuis les sources)
    __version__ = "0.0.0"

__all__ = ["__version__"]
