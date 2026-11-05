"""Explicit ASTNN dataset transformation with implementation IDs."""
from operate_sct import main as _main


def main(argv=None):
    return _main(argv, default_format="astnn")


if __name__ == "__main__":
    main()
