import type { Metadata } from "next";
import "./globals.css";
import { ActorProvider } from "@/lib/actor-context";
import { NavBar } from "@/components/nav-bar";

export const metadata: Metadata = {
  title: "Tableau AI Prep",
  description: "NL -> Claude plan -> human approval -> Hyper extract -> Tableau publish",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col bg-slate-50 text-slate-900">
        <ActorProvider>
          <NavBar />
          <main className="flex-1 w-full">{children}</main>
        </ActorProvider>
      </body>
    </html>
  );
}
