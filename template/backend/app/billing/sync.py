"""`python -m app.billing.sync`: create or update every plan in plans.yaml in Lago.

Reads only LAGO_API_URL and LAGO_API_KEY, so it runs before Stripe or Zitadel are configured.
"""
from app.billing.plans import load_plans
from app.config import LagoSettings
from app.integrations.lago import LagoClient


def main() -> None:
    settings = LagoSettings()
    lago = LagoClient(settings.lago_api_url, settings.lago_api_key)
    for plan in load_plans().values():
        lago.upsert_plan(plan.to_lago())
        print(f"synced plan {plan.code}")


if __name__ == "__main__":
    main()
