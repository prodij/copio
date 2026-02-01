#!/usr/bin/env python
"""
Seed script to populate the database with realistic mock data.

Usage:
    docker compose exec api python scripts/seed_data.py
    
    # Or with options:
    docker compose exec api python scripts/seed_data.py --products 100 --vendors 20
"""

import asyncio
import argparse
import random
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Import session management
from src.db.session import async_session_maker

# Import factories
from src.factories.base import set_session
from src.factories.tenant import TenantFactory
from src.factories.product import ProductFactory, ProductImageFactory, ProductAttributeFactory
from src.factories.category import CategoryFactory
from src.factories.vendor import VendorFactory, VendorContactFactory, VendorAddressFactory, VendorProductFactory
from src.factories.inventory import LocationFactory, StockItemFactory, StockMovementFactory
from src.factories.purchase_order import PurchaseOrderFactory, POLineFactory

# Import models for queries
from src.db.models.tenant import Tenant
from src.db.models.user import User
from src.db.models.category import Category
from src.db.models.inventory import Location
from src.db.models.vendor import Vendor
from src.db.models.product import Product


async def get_or_create_tenant(session: AsyncSession) -> Tenant:
    """Get existing tenant or create demo tenant."""
    result = await session.execute(select(Tenant).limit(1))
    tenant = result.scalar_one_or_none()
    
    if tenant:
        print(f"Using existing tenant: {tenant.name} ({tenant.slug})")
        return tenant
    
    # Create new tenant
    set_session(session)
    tenant = TenantFactory.create(
        name="Demo Company",
        slug="demo",
    )
    await session.flush()
    print(f"Created tenant: {tenant.name}")
    return tenant


async def seed_categories(session: AsyncSession, tenant_id: UUID, count: int = 20) -> list[Category]:
    """Create a realistic category hierarchy."""
    print(f"\n📁 Creating {count} categories...")
    
    set_session(session)
    categories = []
    
    # Define category hierarchy
    hierarchy = {
        "Electronics": ["Audio", "Computers", "Mobile Accessories", "Gaming", "Smart Home"],
        "Home & Garden": ["Furniture", "Kitchen", "Bedding", "Outdoor", "Storage"],
        "Sports & Fitness": ["Exercise Equipment", "Outdoor Recreation", "Yoga", "Team Sports"],
        "Office Supplies": ["Desk Accessories", "Organization", "Tech Accessories"],
        "Pet Supplies": ["Dog", "Cat", "Fish", "Small Animals"],
    }
    
    for parent_name, children in hierarchy.items():
        if len(categories) >= count:
            break
            
        # Create parent category
        parent = CategoryFactory.create(
            tenant_id=tenant_id,
            name=parent_name,
            slug=parent_name.lower().replace(" ", "-").replace("&", "and"),
            parent_id=None,
        )
        categories.append(parent)
        await session.flush()
        
        # Create child categories
        for child_name in children:
            if len(categories) >= count:
                break
            child = CategoryFactory.create(
                tenant_id=tenant_id,
                name=child_name,
                slug=f"{parent.slug}-{child_name.lower().replace(' ', '-')}",
                parent_id=parent.id,
            )
            categories.append(child)
            await session.flush()
    
    print(f"   ✓ Created {len(categories)} categories")
    return categories


async def seed_locations(session: AsyncSession, tenant_id: UUID, count: int = 5) -> list[Location]:
    """Create warehouse and FBA locations."""
    print(f"\n📍 Creating {count} locations...")
    
    set_session(session)
    locations = []
    
    # Create main warehouse
    main_warehouse = LocationFactory.create(
        tenant_id=tenant_id,
        name="Main Warehouse",
    )
    locations.append(main_warehouse)
    await session.flush()
    
    # Create FBA locations
    for i in range(min(2, count - 1)):
        fba = LocationFactory.create(
            tenant_id=tenant_id,
            fba=True,
        )
        locations.append(fba)
        await session.flush()
    
    # Create additional warehouses if needed
    warehouse_names = ["West Coast DC", "East Coast DC", "Central Hub", "Returns Center"]
    for i, name in enumerate(warehouse_names):
        if len(locations) >= count:
            break
        loc = LocationFactory.create(
            tenant_id=tenant_id,
            name=name,
        )
        locations.append(loc)
        await session.flush()
    
    print(f"   ✓ Created {len(locations)} locations")
    return locations


async def seed_vendors(session: AsyncSession, tenant_id: UUID, count: int = 15) -> list[Vendor]:
    """Create vendors with contacts and addresses."""
    print(f"\n🏭 Creating {count} vendors...")
    
    set_session(session)
    vendors = []
    
    for i in range(count):
        vendor = VendorFactory.create(tenant_id=tenant_id)
        await session.flush()
        
        # Add 1-3 contacts per vendor
        for j in range(random.randint(1, 3)):
            VendorContactFactory.create(
                vendor_id=vendor.id,
                is_primary=(j == 0),
            )
        
        # Add 1-2 addresses per vendor
        for j in range(random.randint(1, 2)):
            VendorAddressFactory.create(
                vendor_id=vendor.id,
                is_primary=(j == 0),
            )
        
        vendors.append(vendor)
        await session.flush()
        
        if (i + 1) % 5 == 0:
            print(f"   ... {i + 1}/{count} vendors created")
    
    print(f"   ✓ Created {len(vendors)} vendors with contacts and addresses")
    return vendors


async def seed_products(
    session: AsyncSession,
    tenant_id: UUID,
    categories: list[Category],
    vendors: list[Vendor],
    locations: list[Location],
    count: int = 50,
) -> list[Product]:
    """Create products with images, attributes, and stock."""
    print(f"\n📦 Creating {count} products...")
    
    set_session(session)
    products = []
    
    leaf_categories = [c for c in categories if c.parent_id is not None]
    if not leaf_categories:
        leaf_categories = categories
    
    for i in range(count):
        product = ProductFactory.create(tenant_id=tenant_id)
        await session.flush()
        
        # Add 2-5 images per product
        for pos in range(random.randint(2, 5)):
            ProductImageFactory.create(
                product_id=product.id,
                position=pos,
            )
        
        # Add 3-6 attributes per product
        attr_names = random.sample(
            ["Material", "Color", "Warranty", "Connectivity", "Battery Life", "Capacity", "Rating"],
            k=random.randint(3, 6)
        )
        for name in attr_names:
            ProductAttributeFactory.create(
                product_id=product.id,
                name=name,
            )
        
        # Create stock items at 1-3 locations
        selected_locations = random.sample(locations, k=min(random.randint(1, 3), len(locations)))
        for loc in selected_locations:
            stock = StockItemFactory.create(
                tenant_id=tenant_id,
                product_id=product.id,
                location_id=loc.id,
            )
            await session.flush()
            
            # Add 1-5 stock movements
            for _ in range(random.randint(1, 5)):
                StockMovementFactory.create(
                    tenant_id=tenant_id,
                    stock_item_id=stock.id,
                )
        
        # Link to 1-2 vendors
        selected_vendors = random.sample(vendors, k=min(random.randint(1, 2), len(vendors)))
        for j, vendor in enumerate(selected_vendors):
            VendorProductFactory.create(
                vendor_id=vendor.id,
                product_id=product.id,
                is_preferred=(j == 0),
            )
        
        products.append(product)
        await session.flush()
        
        if (i + 1) % 10 == 0:
            print(f"   ... {i + 1}/{count} products created")
    
    print(f"   ✓ Created {len(products)} products with images, attributes, stock, and vendor links")
    return products


async def seed_purchase_orders(
    session: AsyncSession,
    tenant_id: UUID,
    vendors: list[Vendor],
    locations: list[Location],
    products: list[Product],
    count: int = 20,
) -> None:
    """Create purchase orders with lines."""
    print(f"\n📋 Creating {count} purchase orders...")
    
    set_session(session)
    
    warehouse_locations = [loc for loc in locations if loc.type.value == "WAREHOUSE"]
    if not warehouse_locations:
        warehouse_locations = locations
    
    for i in range(count):
        vendor = random.choice(vendors)
        destination = random.choice(warehouse_locations)
        
        po = PurchaseOrderFactory.create(
            tenant_id=tenant_id,
            vendor_id=vendor.id,
            destination_id=destination.id,
        )
        await session.flush()
        
        # Add 2-8 lines per PO
        selected_products = random.sample(products, k=min(random.randint(2, 8), len(products)))
        for product in selected_products:
            POLineFactory.create(
                po_id=po.id,
                product_id=product.id,
            )
        
        await session.flush()
        
        if (i + 1) % 5 == 0:
            print(f"   ... {i + 1}/{count} purchase orders created")
    
    print(f"   ✓ Created {count} purchase orders with lines")


async def main(
    products: int = 50,
    vendors: int = 15,
    categories: int = 20,
    locations: int = 5,
    purchase_orders: int = 20,
):
    """Main seed function."""
    print("=" * 60)
    print("🌱 Seeding Copio database with mock data")
    print("=" * 60)
    
    async with async_session_maker() as session:
        try:
            # Get or create tenant
            tenant = await get_or_create_tenant(session)
            
            # Seed in dependency order
            cats = await seed_categories(session, tenant.id, categories)
            locs = await seed_locations(session, tenant.id, locations)
            vends = await seed_vendors(session, tenant.id, vendors)
            prods = await seed_products(session, tenant.id, cats, vends, locs, products)
            await seed_purchase_orders(session, tenant.id, vends, locs, prods, purchase_orders)
            
            # Commit all changes
            await session.commit()
            
            print("\n" + "=" * 60)
            print("✅ Database seeded successfully!")
            print("=" * 60)
            print(f"\nSummary:")
            print(f"  • {len(cats)} categories")
            print(f"  • {len(locs)} locations")
            print(f"  • {len(vends)} vendors")
            print(f"  • {len(prods)} products")
            print(f"  • {purchase_orders} purchase orders")
            
        except Exception as e:
            await session.rollback()
            print(f"\n❌ Error seeding database: {e}")
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the database with mock data")
    parser.add_argument("--products", type=int, default=50, help="Number of products to create")
    parser.add_argument("--vendors", type=int, default=15, help="Number of vendors to create")
    parser.add_argument("--categories", type=int, default=20, help="Number of categories to create")
    parser.add_argument("--locations", type=int, default=5, help="Number of locations to create")
    parser.add_argument("--purchase-orders", type=int, default=20, help="Number of POs to create")
    
    args = parser.parse_args()
    
    asyncio.run(main(
        products=args.products,
        vendors=args.vendors,
        categories=args.categories,
        locations=args.locations,
        purchase_orders=args.purchase_orders,
    ))
