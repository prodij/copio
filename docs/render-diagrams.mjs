import { renderMermaid, THEMES } from 'beautiful-mermaid';
import { writeFileSync } from 'fs';
import { join } from 'path';

const theme = THEMES['tokyo-night'];
const outDir = './diagrams';

const diagrams = {
  '01-inventory-lifecycle': `flowchart TB
    subgraph PO["📋 PURCHASE ORDER"]
        ON_PO[ON_PO<br/>Ordered, not shipped]
    end

    ON_PO -->|vendor ships| SPLIT{Ship Destination?}
    
    SPLIT -->|to your warehouse| SELF_PATH
    SPLIT -->|direct to 3PL| FBA_PATH

    subgraph SELF_PATH["🏭 SELF-MANAGED PATH"]
        IN_TRANSIT_IN[IN_TRANSIT_INBOUND<br/>From vendor]
        IN_WAREHOUSE_RECV[IN_WAREHOUSE<br/>At dock/receiving]
        IN_WAREHOUSE_BIN[IN_WAREHOUSE<br/>@ Zone/Aisle/Bin<br/>lastVerifiedAt]
        ALLOCATED[ALLOCATED<br/>Reserved for order]
        IN_PREP[IN_PREP<br/>Pick/pack/label]
        IN_TRANSIT_OUT_SELF[IN_TRANSIT_OUTBOUND<br/>To customer]

        IN_TRANSIT_IN -->|arrive| IN_WAREHOUSE_RECV
        IN_WAREHOUSE_RECV -->|put away| IN_WAREHOUSE_BIN
        IN_WAREHOUSE_BIN -->|customer order| ALLOCATED
        ALLOCATED -->|picking| IN_PREP
        IN_PREP -->|ship| IN_TRANSIT_OUT_SELF
    end

    subgraph FBA_PATH["📦 3PL/FBA PATH"]
        FBA_INBOUND_SHIPPED[FBA_INBOUND_SHIPPED<br/>To Amazon FC]
        FBA_INBOUND_RECV[FBA_INBOUND_RECEIVING<br/>Being processed]
        FBA_FULFILLABLE[FBA_FULFILLABLE<br/>Sellable on AMZ<br/>lastSyncedAt]
        FBA_RESERVED[FBA_RESERVED<br/>Picking/packing or<br/>FC transfer]
        IN_TRANSIT_OUT_FBA[IN_TRANSIT_OUTBOUND<br/>AMZ shipping]

        FBA_INBOUND_SHIPPED -->|arrive at FC| FBA_INBOUND_RECV
        FBA_INBOUND_RECV -->|processed| FBA_FULFILLABLE
        FBA_FULFILLABLE -->|AMZ order| FBA_RESERVED
        FBA_RESERVED -->|shipped| IN_TRANSIT_OUT_FBA
    end

    IN_TRANSIT_OUT_SELF --> DELIVERED[✅ DELIVERED]
    IN_TRANSIT_OUT_FBA --> DELIVERED

    DELIVERED -->|return?| RETURNED[RETURNED]
    RETURNED -->|sellable| FBA_FULFILLABLE
    RETURNED -->|sellable| IN_WAREHOUSE_BIN

    IN_WAREHOUSE_BIN <-->|transfer to/from FBA| FBA_FULFILLABLE`,

  '02-transfer-locations': `flowchart LR
    subgraph SELF["Self-Managed"]
        WH[Your Warehouse<br/>@ Bin Location]
    end

    subgraph THIRDPARTY["Third-Party 3PL"]
        FBA[Amazon FBA]
        WFS[Walmart WFS]
        OTHER[Other 3PL]
    end

    WH -->|"FBA Inbound Shipment"| FBA
    FBA -->|"Removal Order"| WH
    
    WH -->|"WFS Inbound"| WFS
    WFS -->|"Return to Seller"| WH

    WH -->|"Ship to 3PL"| OTHER
    OTHER -->|"Return"| WH`,

  '03-exception-states': `flowchart TB
    FBA_FULFILLABLE[FBA_FULFILLABLE] --> EXCEPTION{Exception?}
    
    EXCEPTION -->|damaged| UNFULFILLABLE[FBA_UNFULFILLABLE<br/>• Damaged<br/>• Customer returns<br/>• Defective<br/>• Expired]
    EXCEPTION -->|discrepancy| RESEARCHING[FBA_RESEARCHING<br/>• Lost inventory<br/>• Damaged claims<br/>• Count discrepancies]
    
    UNFULFILLABLE --> DECISION{Decision}
    DECISION -->|removal order| WAREHOUSE[Back to Warehouse]
    DECISION -->|dispose| DISPOSED[Disposed]
    
    RESEARCHING -->|resolved - found| FBA_FULFILLABLE
    RESEARCHING -->|resolved - lost| REIMBURSEMENT[Reimbursement Claim]`,

  '04-warehouse-hierarchy': `flowchart TB
    subgraph WAREHOUSE["🏭 WAREHOUSE: Main Warehouse - LA"]
        subgraph ZONE_A["ZONE A: Receiving"]
            DOCK[Receiving Dock<br/>temporary holding]
        end
        
        subgraph ZONE_B["ZONE B: Bulk Storage"]
            subgraph AISLE_B1["AISLE B-1"]
                subgraph RACK_B1R1["RACK B-1-R1"]
                    SHELF_S1["SHELF S1"]
                    BIN_01["BIN 01<br/>SKU-001: 50 units"]
                    BIN_02["BIN 02<br/>SKU-002: 25 units"]
                    BIN_03["BIN 03<br/>empty"]
                    SHELF_S1 --- BIN_01
                    SHELF_S1 --- BIN_02
                    SHELF_S1 --- BIN_03
                end
            end
        end
        
        subgraph ZONE_C["ZONE C: Pick/Pack"]
            STAGING[Staging Area<br/>for orders]
        end
        
        subgraph ZONE_D["ZONE D: Shipping"]
            OUTBOUND[Outbound Dock]
        end
    end`,

  '05-location-class': `classDiagram
    class Location {
        +String id
        +String name
        +LocationType type
        +String parentId
        +String path
        +Boolean isStorable
        +Boolean isThirdParty
        +String fulfillmentProviderId
        +String externalId
        +JSON metadata
    }

    class LocationType {
        <<enumeration>>
        WAREHOUSE
        ZONE
        AISLE
        RACK
        SHELF
        BIN
        FULFILLMENT_CENTER
        TRANSIT
        VENDOR
    }

    class FulfillmentProvider {
        +String id
        +String name
        +String code
        +Boolean apiConfigured
        +JSON statusMappings
    }

    Location --> LocationType
    Location --> FulfillmentProvider
    Location --> Location : parentId`,

  '06-state-machine': `stateDiagram-v2
    [*] --> ON_PO : Create PO

    state "Self-Managed" as self {
        ON_PO --> IN_TRANSIT_INBOUND : Vendor ships
        IN_TRANSIT_INBOUND --> IN_WAREHOUSE : Received
        IN_WAREHOUSE --> ALLOCATED : Order placed
        ALLOCATED --> IN_PREP : Start picking
        IN_PREP --> IN_TRANSIT_OUTBOUND : Ship
        IN_TRANSIT_OUTBOUND --> DELIVERED : Delivered
    }

    state "3PL/FBA" as fba {
        ON_PO --> FBA_INBOUND_SHIPPED : Ship to FBA
        FBA_INBOUND_SHIPPED --> FBA_INBOUND_RECEIVING : Arrived at FC
        FBA_INBOUND_RECEIVING --> FBA_FULFILLABLE : Processed
        FBA_FULFILLABLE --> FBA_RESERVED : Order/Transfer
        FBA_RESERVED --> IN_TRANSIT_OUTBOUND : Shipped
        
        FBA_FULFILLABLE --> FBA_UNFULFILLABLE : Damaged/Return
        FBA_FULFILLABLE --> FBA_RESEARCHING : Discrepancy
        FBA_RESEARCHING --> FBA_FULFILLABLE : Resolved
        FBA_UNFULFILLABLE --> IN_WAREHOUSE : Removal order
    }

    DELIVERED --> [*]
    DELIVERED --> IN_WAREHOUSE : Return (sellable)
    DELIVERED --> FBA_UNFULFILLABLE : Return (FBA)

    IN_WAREHOUSE --> FBA_INBOUND_SHIPPED : Transfer to FBA
    FBA_FULFILLABLE --> IN_WAREHOUSE : Removal order`,

  '07-data-model': `erDiagram
    Product ||--o{ StockItem : "has inventory"
    Location ||--o{ StockItem : "stores"
    FulfillmentProvider ||--o{ Location : "manages"
    Location ||--o{ Location : "parent-child"
    StockItem ||--o{ StockMovement : "tracks"
    
    Product {
        string id PK
        string sku
        string name
    }

    Location {
        string id PK
        string name
        string type
        string parentId FK
        string path
        boolean isStorable
        boolean isThirdParty
        string fulfillmentProviderId FK
        string externalId
        json metadata
    }

    FulfillmentProvider {
        string id PK
        string name
        string code
        boolean apiConfigured
        json statusMappings
    }

    StockItem {
        string id PK
        string productId FK
        string locationId FK
        int quantityAvailable
        int quantityReserved
        int quantityInbound
        string status
        datetime lastVerifiedAt
        datetime lastSyncedAt
        string externalStatus
        json externalData
    }

    StockMovement {
        string id PK
        string productId FK
        string fromLocationId FK
        string toLocationId FK
        int quantity
        string type
        string status
        datetime timestamp
        string userId
        string reference
        string notes
    }`,

  '08-status-enum': `flowchart TB
    subgraph SELF_MANAGED["Self-Managed Statuses"]
        ON_PO["ON_PO"]
        IN_TRANSIT_INBOUND["IN_TRANSIT_INBOUND"]
        IN_WAREHOUSE["IN_WAREHOUSE"]
        ALLOCATED["ALLOCATED"]
        IN_PREP["IN_PREP"]
        IN_TRANSIT_OUTBOUND["IN_TRANSIT_OUTBOUND"]
        DELIVERED["DELIVERED"]
        RETURNED["RETURNED"]
    end

    subgraph FBA_STATUSES["Amazon FBA Statuses"]
        FBA_INBOUND_WORKING["FBA_INBOUND_WORKING"]
        FBA_INBOUND_SHIPPED["FBA_INBOUND_SHIPPED"]
        FBA_INBOUND_RECEIVING["FBA_INBOUND_RECEIVING"]
        FBA_FULFILLABLE["FBA_FULFILLABLE"]
        FBA_RESERVED["FBA_RESERVED"]
        FBA_UNFULFILLABLE["FBA_UNFULFILLABLE"]
        FBA_RESEARCHING["FBA_RESEARCHING"]
    end

    subgraph WFS_STATUSES["Walmart WFS Statuses"]
        WFS_INBOUND["WFS_INBOUND"]
        WFS_AVAILABLE["WFS_AVAILABLE"]
        WFS_RESERVED["WFS_RESERVED"]
        WFS_UNFULFILLABLE["WFS_UNFULFILLABLE"]
    end`
};

async function main() {
  console.log('Rendering diagrams with beautiful-mermaid (tokyo-night theme)...\n');
  
  for (const [name, code] of Object.entries(diagrams)) {
    try {
      const svg = await renderMermaid(code, theme);
      const outPath = join(outDir, `${name}.svg`);
      writeFileSync(outPath, svg);
      console.log(`✅ ${name}.svg`);
    } catch (e) {
      console.error(`❌ ${name}: ${e.message}`);
    }
  }
  
  console.log('\nDone! SVGs saved to ./diagrams/');
}

main();
