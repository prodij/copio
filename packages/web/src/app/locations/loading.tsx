import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { PageHeaderSkeleton, TableSkeleton } from "@/components/table-skeleton";
import { Skeleton } from "@/components/ui/skeleton";

export default function LocationsLoading() {
  return (
    <div className="space-y-6">
      <PageHeaderSkeleton />
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-32" />
          <Skeleton className="h-4 w-24" />
        </CardHeader>
        <CardContent>
          <TableSkeleton columns={4} rows={6} />
        </CardContent>
      </Card>
    </div>
  );
}
