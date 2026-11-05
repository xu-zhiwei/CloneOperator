"""Explicit DSFM dataset transformation with implementation IDs."""
from operate_sct import main as _main


def main(argv=None):
    return _main(argv, default_format="dsfm")


if __name__ == "__main__":
    main()
