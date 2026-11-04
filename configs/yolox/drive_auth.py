"""Drive read-only OAuth token for reading the GlareMOT2 zip through the Drive API (configs/yolox/push_token.sh).

rclone's built-in OAuth client shares one requests-per-minute quota with every rclone user (2026-11-03: HTTP 403
"Quota exceeded for quota metric 'Queries'"), and Google blocks the Cloud SDK client for Drive scopes ("This app is
blocked"). So this uses the user's own Desktop OAuth client (~/.config/peg_drive/client.json, never in git; redirect
http://localhost:8085/, the user pastes the redirect URL back) with scope drive.readonly. Without client.json it falls
back to the Cloud SDK client that the Colab CLI ships (colab_cli/oauth_config.json).
  url   -> prints the consent URL; the PKCE verifier is kept in a private state file
  code  -> reads the code shown on Google's page from stdin, saves the credentials (with refresh token)
  token -> prints a fresh access token (refreshing it when < 10 min is left); used by push_token.sh, never logged
Run with the gemma4ever venv (google-auth-oauthlib): ~/Projects/gemma4ever/.venv/bin/python configs/yolox/drive_auth.py url
"""
import datetime as dt
import json
import os
import sys
from importlib import resources

D = os.path.expanduser("~/.config/peg_drive")
CREDS = os.path.join(D, "credentials.json")
# drive.readonly by default; `url full` asks for the drive scope that `gcloud auth login --enable-gdrive-access` uses
SCOPE_SETS = {"readonly": ["https://www.googleapis.com/auth/drive.readonly"], "full": ["https://www.googleapis.com/auth/drive"]}


def state_path(state):
    return os.path.join(D, f"flow_{state}.json")
REDIRECT = "https://sdk.cloud.google.com/applicationdefaultauthcode.html"


OWN_CLIENT = os.path.join(D, "client.json")      # our own Desktop OAuth client (project of the user), if present
LOCAL_REDIRECT = "http://localhost:8085/"         # Desktop clients accept any localhost port; the user pastes the URL back


def client_config():
    if os.path.isfile(OWN_CLIENT):
        return json.load(open(OWN_CLIENT))
    return json.loads(resources.files("colab_cli").joinpath("oauth_config.json").read_text())


def redirect():
    return LOCAL_REDIRECT if os.path.isfile(OWN_CLIENT) else REDIRECT


def private_write(path, obj):
    os.makedirs(D, mode=0o700, exist_ok=True)
    fd = os.open(path + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(obj, f)
    os.replace(path + ".tmp", path)


def main():
    from google_auth_oauthlib.flow import InstalledAppFlow
    cmd = sys.argv[1]
    if cmd == "url":
        scopes = SCOPE_SETS[sys.argv[2] if len(sys.argv) > 2 else "readonly"]
        flow = InstalledAppFlow.from_client_config(client_config(), scopes, autogenerate_code_verifier=True)
        flow.redirect_uri = redirect()
        extra = {} if os.path.isfile(OWN_CLIENT) else {"token_usage": "remote"}
        url, state = flow.authorization_url(prompt="consent", access_type="offline", **extra)
        private_write(state_path(state), {"state": state, "code_verifier": flow.code_verifier, "scopes": scopes})
        print(url)
    elif cmd == "code":
        # the code does not say which consent URL it came from: try every pending flow until one exchanges
        import glob
        code, err = sys.stdin.readline().strip(), None
        if "code=" in code:                             # the whole localhost redirect URL was pasted
            from urllib.parse import parse_qs, urlparse
            code = parse_qs(urlparse(code).query)["code"][0]
        for p in sorted(glob.glob(os.path.join(D, "flow_*.json")), key=os.path.getmtime, reverse=True):
            st = json.load(open(p))
            flow = InstalledAppFlow.from_client_config(client_config(), st["scopes"], state=st["state"],
                                                       code_verifier=st["code_verifier"])
            flow.redirect_uri = redirect()
            try:
                flow.fetch_token(code=code)
            except Exception as e:                    # noqa: BLE001 - wrong verifier for this code: try the next flow
                err = e
                continue
            private_write(CREDS, json.loads(flow.credentials.to_json()))
            for q in glob.glob(os.path.join(D, "flow_*.json")):
                os.remove(q)
            print("saved", CREDS, "scopes", flow.credentials.scopes)
            return
        sys.exit(f"no pending flow accepted the code: {type(err).__name__}: {str(err)[:200]}")
    elif cmd == "token":
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_info(json.load(open(CREDS)))
        left = (creds.expiry - dt.datetime.utcnow()).total_seconds() if creds.expiry else -1
        if not creds.valid or left < 600:
            creds.refresh(Request())
            private_write(CREDS, json.loads(creds.to_json()))
        print(creds.token)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
