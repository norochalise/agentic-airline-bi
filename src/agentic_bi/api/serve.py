"""`abi-serve`: run the API and web UI with uvicorn."""

import argparse
import logging

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Agentic BI web app.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="Restart on code edits.")
    args = parser.parse_args()

    # Show the app's own messages (model warm-up, retries) next to uvicorn's.
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(message)s")

    uvicorn.run(
        "agentic_bi.api.app:app", host=args.host, port=args.port, reload=args.reload
    )


if __name__ == "__main__":
    main()
