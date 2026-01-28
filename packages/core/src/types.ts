// Re-export all generated types from Prisma
export type {
  Product,
  ProductImage,
  ProductAttribute,
  Category,
  ProductCategory,
  ChannelListing,
  Location,
  StockItem,
  StockMovement,
  Order,
  OrderLine,
  Vendor,
  VendorProduct,
  PurchaseOrder,
  POLine,
} from "@prisma/client";

// Re-export enums
export {
  ProductType,
  ProductStatus,
  Channel,
  ListingStatus,
  FulfillmentChannel,
  LocationType,
  MovementType,
  OrderStatus,
  POStatus,
} from "@prisma/client";
