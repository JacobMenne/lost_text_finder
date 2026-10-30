import sys
sys.path.insert(0, "src")

from catalog import interactive_select_target
from ingest import ingest_target_book
from scanner import scan_and_attribute
from codex_server import launch_codex_app


def run_cli_mode():
    targets = interactive_select_target()
    for target in targets:
        try:
            aligned_csv = ingest_target_book(target)
            scan_and_attribute(aligned_csv, headless=False)
        except Exception as exc:
            print(f"[!] Error processing {target['sector_id']}: {exc}")


if __name__ == "__main__":
    if "--cli" in sys.argv:
        run_cli_mode()
    else:
        launch_codex_app()