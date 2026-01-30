import { Card, CardContent, CardHeader } from "@/components/ui/card";
import {
  PageHeaderSkeleton,
  FiltersSkeleton,
  TableSkeleton,
} from "@/components/table-skeleton";
import { Skeleton } from "@/components/ui/skeleton";

export default function PurchaseOrdersLoading() {
  return (
    <div className="space-y-6">
      <PageHeaderSkeleton />
      <FiltersSkeleton />
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-40" />
          <Skeleton className="h-4 w-24" />
        </CardHeader>
        <CardContent>
          <TableSkeleton columns={6} rows={8} />
        </CardContent>
      </Card>
    </div>
  );
}
