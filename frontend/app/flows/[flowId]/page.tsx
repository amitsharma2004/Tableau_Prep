import { FlowDetailClient } from "@/components/flow-detail-client";

export default async function FlowDetailPage({ params }: { params: Promise<{ flowId: string }> }) {
  const { flowId } = await params;
  return <FlowDetailClient flowId={flowId} />;
}
