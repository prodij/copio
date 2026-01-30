import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { PageHeaderSkeleton, TableSkeleton } from "@/components/table-skeleton";
import { Skeleton } from "@/components/ui/skeleton";

export default function InventoryLoading() {
  return (
    <div className="space-y-6">
      <PageHeaderSkeleton />
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-32" />
          <Skeleton className="h-4 w-24" />
        </CardHeader>
        <CardContent>
          <TableSkeleton columns={5} rows={8} />
        </CardContent>
      </Card>
    </div>
  );
}
