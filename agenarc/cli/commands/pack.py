"""
Command: pack — Pack a directory into a .agrc ZIP bundle.
"""

from pathlib import Path
from typing import Optional

from . import pack_bundle


def command_pack(
    source: Path,
    output: Optional[Path] = None,
    verbose: bool = False
) -> int:
    """
    Pack a directory into a .agrc ZIP bundle.

    Args:
        source: Source directory to pack
        output: Output .agrc file path (default: <source>.agrc)
        verbose: Verbose output flag

    Returns:
        Exit code
    """
    output_path = output or Path(str(source) + ".agrc")
    pack_bundle(source, output_path, verbose)
    return 0
