"""Private test launcher; production CLI has no test token or fixture reset API."""

import argparse
import json
import signal
import threading
from pathlib import Path
from tempfile import TemporaryDirectory

from prguard.demo import _demo_proposals, prepare_demo_task
from prguard.harness.artifacts import canonical_json
from prguard.implementer.errors import ProviderError
from prguard.studio import StudioConfig, StudioService, create_server


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--review-unavailable", action="store_true")
    args = parser.parse_args()
    with TemporaryDirectory(prefix="prguard-browser-") as directory:
        root = Path(directory)
        options = {}
        if args.local:
            fixture = root / "fixture"
            fixture.mkdir()
            task = prepare_demo_task(fixture)
            proposals = root / "proposals.json"
            proposals.write_bytes(canonical_json([
                value.model_dump(mode="json") for value in _demo_proposals()
            ]))
            options = {
                "repository": task.repository, "trust_host": True,
                "provider": "scripted", "proposal_sequence": proposals,
            }
        service = StudioService(StudioConfig(
            workspace=root / "runs", enable_independent_review=not args.local, **options,
        ))
        if args.review_unavailable:
            def unavailable(_spec):
                raise ProviderError("Scripted Reviewer service outage for browser test")

            service._reviewer = unavailable
        server = create_server(service, port=0)

        def shutdown(_signum, _frame):
            # shutdown() must be called outside serve_forever's thread.
            threading.Thread(target=server.shutdown, daemon=True).start()

        signal.signal(signal.SIGTERM, shutdown)
        signal.signal(signal.SIGINT, shutdown)
        print(json.dumps({"url": (
            f"http://127.0.0.1:{server.server_port}/#token={service.token}"
        )}), flush=True)
        try:
            server.serve_forever(poll_interval=0.1)
        finally:
            server.server_close()
            service.close()


if __name__ == "__main__":
    main()
