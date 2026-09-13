import { redirect } from "next/navigation";

/**
 * Home route. Process discovery (Module A) is the only screen built so far, and every later module
 * starts from its outputs, so the app opens there instead of on an empty landing page.
 */
export default function Home() {
  redirect("/discovery");
}
