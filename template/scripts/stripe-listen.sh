#!/bin/sh
# Entrypoint of the stripe-cli service: forward Stripe TEST webhooks to Lago's Stripe route.
# Idles (exit 0) until .env has the key and `make bootstrap` wrote LAGO_ORGANIZATION_ID; refuses
# anything that is not a test key.
case "$STRIPE_API_KEY" in
  "") echo "stripe-cli: idle until STRIPE_SECRET_KEY is in .env and make bootstrap has run"; exit 0 ;;
  sk_test_*) ;;
  *) echo "stripe-cli: refusing STRIPE_SECRET_KEY: only Stripe test secret keys (sk_test_) are allowed" >&2; exit 1 ;;
esac
if [ -z "$LAGO_ORGANIZATION_ID" ]; then
  echo "stripe-cli: idle until make bootstrap has run"
  exit 0
fi
# stripe-cli refuses to listen without an event list. This is what Lago v1.55.0 handles
# (PaymentProviders::StripeProvider::WEBHOOKS_EVENTS); check it when bumping the Lago image.
EVENTS=setup_intent.succeeded,payment_intent.payment_failed,payment_intent.succeeded,payment_intent.canceled
EVENTS=$EVENTS,payment_method.detached,charge.refund.updated,customer.updated,charge.dispute.closed
EVENTS=$EVENTS,customer_cash_balance_transaction.created
exec stripe listen --events "$EVENTS" --forward-to "http://lago-api:3000/webhooks/stripe/$LAGO_ORGANIZATION_ID?code=stripe"
