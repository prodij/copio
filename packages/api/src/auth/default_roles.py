"""Default roles for new tenants."""

from typing import TypedDict


class RoleDefinition(TypedDict):
    name: str
    description: str
    permissions: list[str]
    is_system: bool


# Default roles created for every new tenant
# Order matters - Owner should be first (assigned to tenant creator)
DEFAULT_ROLES: list[RoleDefinition] = [
    {
        "name": "Owner",
        "description": "Full system access including billing and company management",
        "permissions": ["*:*"],
        "is_system": True,
    },
    {
        "name": "Admin",
        "description": "Full operational access, user and role management",
        "permissions": [
            "products:*",
            "inventory:*",
            "vendors:*",
            "purchase_orders:*",
            "locations:*",
            "categories:*",
            "channels:*",
            "users:*",
            "roles:view",  # Can view roles but not edit (only Owner can)
            "settings:*",
            "audit_log:*",
            "company:view",  # Can view but not edit company settings
        ],
        "is_system": True,
    },
    {
        "name": "Manager",
        "description": "Manage operations, approve POs, supervise inventory",
        "permissions": [
            "products:view", "products:create", "products:edit",
            "inventory:*",
            "vendors:view", "vendors:create", "vendors:edit",
            "purchase_orders:*",
            "locations:view", "locations:create", "locations:edit",
            "categories:view", "categories:create", "categories:edit",
            "channels:view", "channels:sync",
            "users:view",
            "audit_log:view",
            "company:view",
        ],
        "is_system": True,
    },
    {
        "name": "Ordering",
        "description": "Procurement focused - manage purchase orders and vendors",
        "permissions": [
            # Dashboard - view only
            "products:view",
            # Purchase Orders - full access
            "purchase_orders:view", "purchase_orders:create", "purchase_orders:edit", "purchase_orders:delete", "purchase_orders:approve",
            # Vendors - full access for procurement
            "vendors:view", "vendors:create", "vendors:edit",
            # Supporting views
            "inventory:view",  # See stock levels to know what to order
            "locations:view",
            "categories:view",
            "channels:view",
            "company:view",
        ],
        "is_system": True,
    },
    {
        "name": "Warehouse",
        "description": "Fulfillment focused - manage inventory and receiving",
        "permissions": [
            # Dashboard - view only
            "products:view",
            # Inventory - full access
            "inventory:view", "inventory:adjust", "inventory:transfer",
            # Locations - full access
            "locations:view", "locations:create", "locations:edit",
            # Purchase Orders - view and receive only
            "purchase_orders:view", "purchase_orders:receive",
            # Supporting views
            "vendors:view",
            "categories:view",
            "channels:view",
            "company:view",
        ],
        "is_system": True,
    },
    {
        "name": "Viewer",
        "description": "Read-only access to all operational data",
        "permissions": [
            "products:view",
            "inventory:view",
            "vendors:view",
            "purchase_orders:view",
            "locations:view",
            "categories:view",
            "channels:view",
            "audit_log:view",
            "company:view",
        ],
        "is_system": True,
    },
]


def get_owner_role() -> RoleDefinition:
    """Get the Owner role definition (first role, assigned to tenant creator)."""
    return DEFAULT_ROLES[0]


def get_default_role_names() -> list[str]:
    """Get list of default role names."""
    return [r["name"] for r in DEFAULT_ROLES]
