"""One isolated collection batch. Internal worker; no Streamlit dependencies."""

import json
import sys

from engine import process_live
from network import discover_network
from settings import Endpoint, Settings


def main() -> None:
    data = json.load(sys.stdin)
    data["endpoints"] = tuple(Endpoint(**e) for e in data["endpoints"])
    settings = Settings(**data)
    network = discover_network().as_dict()
    df = process_live(settings)
    print(json.dumps({"records": json.loads(df.to_json(orient="records")), "network": network}))


if __name__ == "__main__":
    main()
