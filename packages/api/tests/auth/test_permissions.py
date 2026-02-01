# packages/api/tests/auth/test_permissions.py
import pytest
from src.auth.permissions import Permission, RESOURCES, ACTIONS, ALL_PERMISSIONS


def test_permission_structure():
    """All permissions follow resource:action format."""
    for perm in ALL_PERMISSIONS:
        assert ":" in perm
        resource, action = perm.split(":", 1)
        assert resource in RESOURCES
        assert action in ACTIONS or action == "*"


def test_permission_enum_values():
    """Permission enum has expected values."""
    assert Permission.PRODUCTS_VIEW == "products:view"
    assert Permission.PURCHASE_ORDERS_RECEIVE == "purchase_orders:receive"
    assert Permission.ALL == "*:*"


def test_get_permissions_for_resource():
    """Can get all actions for a resource."""
    from src.auth.permissions import get_permissions_for_resource
    
    product_perms = get_permissions_for_resource("products")
    assert "products:view" in product_perms
    assert "products:create" in product_perms
    assert "products:edit" in product_perms
    assert "products:delete" in product_perms


def test_wildcard_matching():
    """Wildcard permissions match correctly."""
    from src.auth.permissions import permission_matches
    
    assert permission_matches("products:view", "products:view")  # Exact
    assert permission_matches("*:view", "products:view")  # Wildcard resource
    assert permission_matches("products:*", "products:view")  # Wildcard action
    assert permission_matches("*:*", "anything:here")  # Full wildcard
    assert not permission_matches("products:view", "vendors:view")  # No match
    assert not permission_matches("products:edit", "products:view")  # Wrong action
