import logging
from collections.abc import Mapping

import httpx

from app.errors import DependencyRejected, DependencyUnavailable

# Zitadel answers 409 (AlreadyExists) when a create already happened. Workspace creation
# retries after a lost response, so each call below treats its own 409 as "already done".
ALREADY_EXISTS = 409

log = logging.getLogger(__name__)


class ZitadelClient:
    def __init__(self, api_url: str, token: str, instance_org_id: str, project_id: str,
                 http: httpx.Client | None = None) -> None:
        self.instance_org_id = instance_org_id
        self.project_id = project_id
        self.http = http or httpx.Client(
            base_url=api_url, headers={"Authorization": f"Bearer {token}"}, timeout=10.0
        )

    def _post(self, path: str, body: Mapping[str, object], org_id: str | None = None) -> httpx.Response:
        headers = {"x-zitadel-orgid": org_id} if org_id else {}
        try:
            response = self.http.post(path, json=body, headers=headers)
        except httpx.HTTPError as exc:
            raise DependencyUnavailable("Zitadel") from exc
        if response.status_code >= 500:
            raise DependencyUnavailable("Zitadel")
        return response

    @staticmethod
    def _check(response: httpx.Response) -> None:
        """Any other non-2xx is a request Zitadel refused. The client hears only the status; Zitadel's
        message goes to the log."""
        if response.is_success:
            return
        log.warning("Zitadel rejected %s %s: HTTP %s %s", response.request.method, response.request.url.path,
                    response.status_code, response.text[:200])
        raise DependencyRejected("Zitadel", f"HTTP {response.status_code}")

    @classmethod
    def _json(cls, response: httpx.Response) -> dict[str, object]:
        cls._check(response)
        result: dict[str, object] = response.json()
        return result

    def create_org(self, name: str, org_id: str) -> str:
        """Create the organization with a caller-chosen ID, so a retry cannot make a second one."""
        response = self._post("/v2/organizations", {"name": name, "organizationId": org_id})
        if response.status_code == ALREADY_EXISTS:
            return org_id
        return str(self._json(response)["organizationId"])

    def grant_project(self, org_id: str) -> str:
        body = {"grantedOrgId": org_id, "roleKeys": ["owner", "member"]}
        path = f"/management/v1/projects/{self.project_id}/grants"
        response = self._post(path, body, org_id=self.instance_org_id)
        if response.status_code == ALREADY_EXISTS:
            return self._existing_grant_id(org_id)
        return str(self._json(response)["grantId"])

    def _existing_grant_id(self, org_id: str) -> str:
        body = {"queries": [
            {"projectIdQuery": {"projectId": self.project_id}},
            {"grantedOrgIdQuery": {"grantedOrgId": org_id}},
        ]}
        response = self._post("/management/v1/projectgrants/_search", body, org_id=self.instance_org_id)
        result = self._json(response).get("result")
        if not isinstance(result, list) or not result:
            # The grant exists but Zitadel's search projection lags behind; a retry will find it.
            raise DependencyUnavailable("Zitadel")
        return str(result[0]["grantId"])

    def add_user_role(self, user_id: str, org_id: str, grant_id: str, role: str) -> None:
        body = {"projectId": self.project_id, "projectGrantId": grant_id, "roleKeys": [role]}
        response = self._post(f"/management/v1/users/{user_id}/grants", body, org_id=org_id)
        if response.status_code != ALREADY_EXISTS:
            self._check(response)

    def user_email(self, user_id: str) -> str | None:
        """The user's email address (Zitadel access tokens carry no `email` claim).

        Best effort: None when Zitadel cannot say, since a Lago customer works without an email.
        """
        try:
            response = self.http.get(f"/v2/users/{user_id}")
            email = response.json()["user"]["human"]["email"]["email"] if response.status_code == 200 else None
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            log.warning("Zitadel email lookup for %s failed: %s", user_id, type(exc).__name__)
            return None
        if response.status_code != 200:
            log.warning("Zitadel email lookup for %s failed: HTTP %s", user_id, response.status_code)
        return email if isinstance(email, str) and email else None
