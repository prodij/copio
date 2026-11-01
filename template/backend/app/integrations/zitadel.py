from collections.abc import Mapping

import httpx

from app.errors import DependencyUnavailable

# Zitadel answers 409 (AlreadyExists) when a create already happened. Workspace creation
# retries after a lost response, so each call below treats its own 409 as "already done".
ALREADY_EXISTS = 409


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
    def _json(response: httpx.Response) -> dict[str, object]:
        response.raise_for_status()
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
            raise RuntimeError(f"Zitadel reported a project grant for org {org_id} but lists none")
        return str(result[0]["grantId"])

    def add_user_role(self, user_id: str, org_id: str, grant_id: str, role: str) -> None:
        body = {"projectId": self.project_id, "projectGrantId": grant_id, "roleKeys": [role]}
        response = self._post(f"/management/v1/users/{user_id}/grants", body, org_id=org_id)
        if response.status_code != ALREADY_EXISTS:
            response.raise_for_status()
