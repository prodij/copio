#!/bin/sh
# Entrypoint of the stripe-cli service: forward Stripe TEST webhooks to Lago's Stripe route.
# Idles (exit 0) until .env has the key and `make bootstrap` wrote LAGO_ORGANIZATION_ID; refuses
# anything that is not a test key.
case "$STRIPE_API_KEY" in
  "") echo "stripe-cli: idle until STRIPE_SECRET_KEY is in .env and make bootstrap has run"; exit 0 ;;
  sk_test_*|rk_test_*) ;;
  *) echo "stripe-cli: refusing STRIPE_SECRET_KEY: only Stripe test keys (sk_test_/rk_test_) are allowed" >&2; exit 1 ;;
esac
if [ -z "$LAGO_ORGANIZATION_ID" ]; then
  echo "stripe-cli: idle until make bootstrap has run"
  exit 0
fi
exec stripe listen --forward-to "http://lago-api:3000/webhooks/stripe/$LAGO_ORGANIZATION_ID?code=stripe"
