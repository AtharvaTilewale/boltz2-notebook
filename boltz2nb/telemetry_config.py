"""Where usage reports go and the key that seals them. Both are public values; the matching private key is never in this repository.

Fill these in once (see docs/TELEMETRY.md): ``ENDPOINT`` is the URL of the collecting web app, ``PUBLIC_KEY`` the base64 public key printed by
``python tools/telemetry_keygen.py``. While either is empty nothing is ever sent, whatever the user ticked.
Forks and tests can override both with the environment variables BOLTZ2NB_TELEMETRY_URL and BOLTZ2NB_TELEMETRY_KEY.
"""
ENDPOINT = "https://script.google.com/macros/s/AKfycbw5rLHOqA1frA_7BKQWI8W3FSZvHFZ23XTLRh1EqJW6tzFH5fWFjGVkLBSGJgcLtNwFow/exec"
PUBLIC_KEY = "/oYKKLFUqgUAV5pBhKM8+Vte+fudNBqh+pNh+H3QBWo="
