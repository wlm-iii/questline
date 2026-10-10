"""Scripted stand-in for `imsg rpc`: JSON-RPC 2.0, one object per line on stdio.

Env:
  FAKE_IMSG_MESSAGES  JSON list of message objects emitted after `watch.subscribe`
  FAKE_IMSG_LOG       file that receives one JSON line per request (for assertions)
"""

import json
import os
import sys


def write(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def main() -> None:
    print("fake imsg ready", file=sys.stderr, flush=True)
    messages = json.loads(os.environ.get("FAKE_IMSG_MESSAGES", "[]"))
    log_path = os.environ.get("FAKE_IMSG_LOG")
    for line in sys.stdin:
        request = json.loads(line)
        if log_path:
            with open(log_path, "a") as log:
                log.write(json.dumps(request) + "\n")
        method, request_id = request["method"], request.get("id")
        params = request.get("params", {})
        if method == "exit":
            return
        if method in {"initialize", "status"}:
            write({"jsonrpc": "2.0", "id": request_id, "result": {"protocol_version": 1}})
        elif method == "watch.subscribe":
            write({"jsonrpc": "2.0", "id": request_id, "result": {"subscription": "sub-1"}})
            since = params.get("since_rowid", 0)
            for message in messages:
                if message["id"] > since:
                    write(
                        {
                            "jsonrpc": "2.0",
                            "method": "message",
                            "params": {"subscription": "sub-1", "message": message},
                        }
                    )
        elif method == "send":
            write({"jsonrpc": "2.0", "id": request_id, "result": {"ok": True, "guid": "sent"}})
        elif method == "messages.history":
            history = [m for m in messages if m["chat_id"] == params["chat_id"]]
            result = {"messages": history[-params.get("limit", 50) :]}
            write({"jsonrpc": "2.0", "id": request_id, "result": result})
        else:
            error = {"code": -32601, "message": f"Method not found: {method}"}
            write({"jsonrpc": "2.0", "id": request_id, "error": error})


if __name__ == "__main__":
    main()
