import { ClientDetail } from "@/components/client-detail";

export default async function ClientRoute({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ClientDetail id={id} />;
}
