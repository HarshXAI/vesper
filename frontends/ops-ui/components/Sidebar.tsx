"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession, signIn, signOut } from "next-auth/react";
import {
  LayoutDashboard,
  LineChart,
  Wrench,
  Settings,
  LogOut,
  User,
  FileText,
} from "lucide-react";

const navigation = [
  { name: "Dashboard", href: "/", icon: LayoutDashboard },
  { name: "Evaluations", href: "/evals", icon: LineChart },
  { name: "Actions", href: "/actions", icon: Wrench },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { data: session, status } = useSession();

  return (
    <aside className="w-64 bg-slate-900 text-white flex flex-col">
      {/* Logo */}
      <div className="p-6 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-vesper-600 rounded-lg flex items-center justify-center">
            <FileText className="w-6 h-6" />
          </div>
          <div>
            <h1 className="font-semibold text-lg">VESPER</h1>
            <p className="text-xs text-slate-400">Operations</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-1">
        {navigation.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={`flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium
                transition-colors ${
                  isActive
                    ? "bg-vesper-600 text-white"
                    : "text-slate-300 hover:bg-slate-800 hover:text-white"
                }`}
            >
              <item.icon className="w-5 h-5" />
              {item.name}
            </Link>
          );
        })}
      </nav>

      {/* User section */}
      <div className="p-4 border-t border-slate-800">
        {status === "loading" ? (
          <div className="animate-pulse h-10 bg-slate-800 rounded-lg" />
        ) : session ? (
          <div className="space-y-3">
            <div className="flex items-center gap-3 px-2">
              <div className="w-8 h-8 bg-slate-700 rounded-full flex items-center justify-center">
                <User className="w-4 h-4 text-slate-400" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">
                  {session.user?.name || session.user?.email}
                </p>
                <p className="text-xs text-slate-400 truncate">
                  {session.user?.email}
                </p>
              </div>
            </div>

            <button
              onClick={() => signOut()}
              className="flex items-center gap-2 w-full px-4 py-2 text-sm text-slate-400 
                       hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
            >
              <LogOut className="w-4 h-4" />
              Sign out
            </button>
          </div>
        ) : (
          <button
            onClick={() => signIn("cognito")}
            className="flex items-center gap-2 w-full px-4 py-2.5 bg-vesper-600 
                     text-white rounded-lg hover:bg-vesper-700 text-sm font-medium"
          >
            <User className="w-4 h-4" />
            Sign in
          </button>
        )}
      </div>
    </aside>
  );
}
