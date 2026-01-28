// Re-export all generated types from Prisma
export type {
  Product,
  ChannelListing,
  Location,
  StockItem,
  StockMovement,
  Order,
  OrderLine,
  Vendor,
  PurchaseOrder,
  POLine,
} from "@prisma/client";

// Re-export enums
export {
  Channel,
  ListingStatus,
  LocationType,
  MovementType,
  OrderStatus,
  POStatus,
} from "@prisma/client";
