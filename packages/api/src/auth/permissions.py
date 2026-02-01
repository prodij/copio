"""Permission definitions for Copio RBAC."""

from enum import Enum
from typing import List

RESOURCES = [
    "products", "inventory", "vendors", "purchase_orders",
    "locations", "categories", "channels", "users", "roles",
    "settings", "audit_log",
]

ACTIONS = [
    "view", "create", "edit", "delete",
    "adjust", "transfer",  # inventory
    "receive", "approve",  # purchase_orders
    "sync",  # channels
    "invite",  # users
    "export",  # audit_log
]

CRUD_ACTIONS = ["view", "create", "edit", "delete"]

RESOURCE_ACTIONS = {
    "products": CRUD_ACTIONS,
    "inventory": ["view", "adjust", "transfer"],
    "vendors": CRUD_ACTIONS,
    "purchase_orders": CRUD_ACTIONS + ["receive", "approve"],
    "locations": CRUD_ACTIONS,
    "categories": CRUD_ACTIONS,
    "channels": CRUD_ACTIONS + ["sync"],
    "users": ["view", "edit", "delete", "invite"],
    "roles": CRUD_ACTIONS,
    "settings": ["view", "edit"],
    "audit_log": ["view", "export"],
}


def _generate_permissions() -> List[str]:
    perms = []
    for resource, actions in RESOURCE_ACTIONS.items():
        for action in actions:
            perms.append(f"{resource}:{action}")
    return perms


ALL_PERMISSIONS = _generate_permissions()


class Permission(str, Enum):
    """All available permissions."""
    PRODUCTS_VIEW = "products:view"
    PRODUCTS_CREATE = "products:create"
    PRODUCTS_EDIT = "products:edit"
    PRODUCTS_DELETE = "products:delete"
    INVENTORY_VIEW = "inventory:view"
    INVENTORY_ADJUST = "inventory:adjust"
    INVENTORY_TRANSFER = "inventory:transfer"
    VENDORS_VIEW = "vendors:view"
    VENDORS_CREATE = "vendors:create"
    VENDORS_EDIT = "vendors:edit"
    VENDORS_DELETE = "vendors:delete"
    PURCHASE_ORDERS_VIEW = "purchase_orders:view"
    PURCHASE_ORDERS_CREATE = "purchase_orders:create"
    PURCHASE_ORDERS_EDIT = "purchase_orders:edit"
    PURCHASE_ORDERS_DELETE = "purchase_orders:delete"
    PURCHASE_ORDERS_RECEIVE = "purchase_orders:receive"
    PURCHASE_ORDERS_APPROVE = "purchase_orders:approve"
    LOCATIONS_VIEW = "locations:view"
    LOCATIONS_CREATE = "locations:create"
    LOCATIONS_EDIT = "locations:edit"
    LOCATIONS_DELETE = "locations:delete"
    CATEGORIES_VIEW = "categories:view"
    CATEGORIES_CREATE = "categories:create"
    CATEGORIES_EDIT = "categories:edit"
    CATEGORIES_DELETE = "categories:delete"
    CHANNELS_VIEW = "channels:view"
    CHANNELS_CREATE = "channels:create"
    CHANNELS_EDIT = "channels:edit"
    CHANNELS_DELETE = "channels:delete"
    CHANNELS_SYNC = "channels:sync"
    USERS_VIEW = "users:view"
    USERS_EDIT = "users:edit"
    USERS_DELETE = "users:delete"
    USERS_INVITE = "users:invite"
    ROLES_VIEW = "roles:view"
    ROLES_CREATE = "roles:create"
    ROLES_EDIT = "roles:edit"
    ROLES_DELETE = "roles:delete"
    SETTINGS_VIEW = "settings:view"
    SETTINGS_EDIT = "settings:edit"
    AUDIT_LOG_VIEW = "audit_log:view"
    AUDIT_LOG_EXPORT = "audit_log:export"
    ALL = "*:*"


def get_permissions_for_resource(resource: str) -> List[str]:
    """Get all permissions for a given resource."""
    actions = RESOURCE_ACTIONS.get(resource, [])
    return [f"{resource}:{action}" for action in actions]


def permission_matches(granted: str, required: str) -> bool:
    """Check if a granted permission satisfies a required permission."""
    if granted == "*:*":
        return True
    granted_resource, granted_action = granted.split(":", 1)
    required_resource, required_action = required.split(":", 1)
    resource_match = granted_resource == "*" or granted_resource == required_resource
    action_match = granted_action == "*" or granted_action == required_action
    return resource_match and action_match
