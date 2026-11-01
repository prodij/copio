import { UserManager, WebStorageStateStore } from "oidc-client-ts";

const projectId = import.meta.env.ZITADEL_PROJECT_ID;

export const userManager = new UserManager({
  authority: import.meta.env.ZITADEL_ISSUER,
  client_id: import.meta.env.ZITADEL_CLIENT_ID,
  redirect_uri: `${window.location.origin}/callback`,
  post_logout_redirect_uri: `${window.location.origin}/`,
  response_type: "code",
  scope: `openid profile email offline_access urn:zitadel:iam:org:project:id:${projectId}:aud urn:zitadel:iam:org:projects:roles`,
  userStore: new WebStorageStateStore({ store: window.localStorage }),
  automaticSilentRenew: true,
});

export async function accessToken(): Promise<string | null> {
  const user = await userManager.getUser();
  return user && !user.expired ? user.access_token : null;
}
