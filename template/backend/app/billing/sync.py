"""`python -m app.billing.sync`: create or update every plan in plans.yaml in Lago."""
from app.billing.plans import load_plans
from app.config import get_settings
from app.integrations import get_lago


def main() -> None:
    lago = get_lago(get_settings())
    for plan in load_plans().values():
        lago.upsert_plan(plan.to_lago())
        print(f"synced plan {plan.code}")


if __name__ == "__main__":
    main()
