"""After `make bootstrap`: check the backend's Zitadel token can do what workspace creation does.

With the backend PAT it creates a throwaway organization, grants it the project, creates a throwaway
user in the instance org and gives that user the `member` role inside the new organization (the
cross-org role grant the backend makes for every workspace owner), then deletes both. Prints `OK`
or the call that failed.
"""

import secrets
import sys

import httpx

import bootstrap


def run(http: httpx.Client, project_id: str, instance_org: str) -> None:
    def call(method: str, path: str, what: str, org: str | None = None, **body: object) -> dict[str, object]:
        headers = {"x-zitadel-orgid": org} if org else {}
        reply = http.request(method, path, json=body or None, headers=headers)
        return bootstrap.check(reply, what)

    tag = secrets.token_hex(4)
    org_id = str(call("POST", "/v2/organizations", "create org", name=f"smoke-{tag}")["organizationId"])
    user_id = ""
    try:
        grant = call("POST", f"/management/v1/projects/{project_id}/grants", "grant project", org=instance_org,
                     grantedOrgId=org_id, roleKeys=["owner", "member"])
        user = call("POST", "/v2/users/human", "create user",
                    username=f"smoke-{tag}", organization={"orgId": instance_org},
                    profile={"givenName": "Smoke", "familyName": "Test"},
                    email={"email": f"smoke-{tag}@example.com", "isVerified": True})
        user_id = str(user["userId"])
        call("POST", f"/management/v1/users/{user_id}/grants", "add member role in the new org", org=org_id,
             projectId=project_id, projectGrantId=str(grant["grantId"]), roleKeys=["member"])
    finally:
        if user_id:
            call("DELETE", f"/v2/users/{user_id}", "delete user")
        call("DELETE", f"/v2/organizations/{org_id}", "delete org")


def main() -> None:
    ids = bootstrap.read_ids()
    if not bootstrap.BACKEND_PAT.is_file() or "ZITADEL_PROJECT_ID" not in ids:
        sys.exit("smoke: run `make bootstrap` first")
    token = bootstrap.BACKEND_PAT.read_text().strip()
    with bootstrap.client(bootstrap.zitadel_url(), {"Authorization": f"Bearer {token}"}) as http:
        try:
            run(http, ids["ZITADEL_PROJECT_ID"], ids["ZITADEL_INSTANCE_ORG_ID"])
        except httpx.HTTPError as exc:
            sys.exit(f"smoke: request failed ({type(exc).__name__}): {exc}")
    print("OK")


if __name__ == "__main__":
    main()
