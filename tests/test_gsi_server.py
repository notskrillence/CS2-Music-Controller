import json
import threading
import urllib.error
import urllib.request

from cs2mc.gsi_server import GSIServer


def post(port: int, token: str):
    body = json.dumps({"auth": {"token": token}, "provider": {"appid": 730}}).encode()
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/gsi",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return urllib.request.urlopen(request, timeout=2)


def test_local_server_accepts_correct_token_and_rejects_wrong_one():
    received = []
    delivered = threading.Event()

    def receive(payload):
        received.append(payload)
        delivered.set()

    server = GSIServer(0, "secret", receive)
    server.start()
    try:
        with post(server.port, "secret") as response:
            assert response.status == 200
        assert delivered.wait(1.0)
        assert received[0]["provider"]["appid"] == 730
        try:
            post(server.port, "wrong")
            assert False, "wrong token should be rejected"
        except urllib.error.HTTPError as exc:
            assert exc.code == 403
    finally:
        server.stop()
