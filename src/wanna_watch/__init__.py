"""Run the personal German streaming discovery app."""

import argparse

import uvicorn


def main() -> None:
    """Start the web server using the requested host and port."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run("wanna_watch.app:create_app", factory=True, host=args.host, port=args.port)
