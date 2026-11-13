import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class VigiHttpsClient:
    def __init__(self, ip, port=443, timeout=10):
        self.base_url = f"https://{ip}:{port}"
        self.timeout = timeout
        self.session = requests.Session()
        self.session.trust_env = False

    def post(self, payload, path="/"):
        response = self.session.post(
            self.base_url + path,
            json=payload,
            headers={
                "Content-Type": "application/json;charset=UTF-8",
                "Accept": "application/json",
            },
            timeout=(5, self.timeout),
            verify=False,
            allow_redirects=False,
        )

        try:
            data = response.json()
        except ValueError:
            raise RuntimeError(
                f"Unexpected non-JSON response: HTTP {response.status_code}"
            )

        return {
            "http_status": response.status_code,
            "data": data,
        }
