import { ClientCompare } from "@/components/client-compare";

export default async function CompareRoute({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ClientCompare id={id} />;
}
