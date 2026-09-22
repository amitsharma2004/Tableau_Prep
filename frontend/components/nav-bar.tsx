"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useActor } from "@/lib/actor-context";

const LINKS = [
  { href: "/flows", label: "Flows" },
  { href: "/connections", label: "Connections" },
  { href: "/runs", label: "Run History" },
];

export function NavBar() {
  const pathname = usePathname();
  const { actorEmail, setActorEmail } = useActor();

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="w-full px-4 sm:px-6 py-2.5 flex items-center justify-between gap-4">
        <div className="flex items-center gap-6">
          <Link href="/flows" className="font-semibold text-slate-900">
            Tableau AI Prep
          </Link>
          <nav className="flex items-center gap-4 text-sm">
            {LINKS.map((link) => {
              const active = pathname === link.href || pathname.startsWith(link.href + "/");
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={active ? "text-blue-600 font-medium" : "text-slate-600 hover:text-slate-900"}
                >
                  {link.label}
                </Link>
              );
            })}
          </nav>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <label htmlFor="actor-email" className="text-slate-500">
            Acting as
          </label>
          <input
            id="actor-email"
            type="email"
            value={actorEmail}
            onChange={(e) => setActorEmail(e.target.value)}
            className="border border-slate-300 rounded px-2 py-1 text-sm w-56"
          />
        </div>
      </div>
    </header>
  );
}
