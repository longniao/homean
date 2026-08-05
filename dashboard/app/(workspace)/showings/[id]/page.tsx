import { ShowingWorkspace } from "@/components/showing-workspace";

export default async function ShowingPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ShowingWorkspace id={id} />;
}
