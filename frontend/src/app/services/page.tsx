import { redirect } from "next/navigation";

/** The service catalog, quote builder and price list now live in Settings. Old links and bookmarks land there. */
export default function ServicesPage() {
  redirect("/settings?tab=quotes");
}
