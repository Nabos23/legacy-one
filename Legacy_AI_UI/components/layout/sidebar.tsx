"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  LayoutDashboard,
  Bot,
  Wrench,
  Database,
  Terminal,
  Settings,
  HelpCircle,
  Building2,
  Users,
  Users2,
  LogOut,
  ChevronLeft,
  Download,
  X,
  Activity,
  Package,
  Plug,
  PlugZap,
  Monitor,
  GitBranch,
  MessageCircle,
  ShieldCheck,
  CalendarClock,
  FolderKanban,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { LogoMark } from "@/components/landing/logo";
import { cn } from "@/lib/utils";
import { useSidebar } from "@/hooks/use-sidebar";
import { useAuth } from "@/contexts/auth-context";

interface NavItem {
  label: string;
  href: string;
  icon: React.ReactNode;
  permission?: string | string[];
}

function hasNavPermission(item: NavItem, permissions: Record<string, boolean>): boolean {
  if (!item.permission) return true;
  if (permissions.is_super_admin || permissions.is_org_admin) return true;
  const required = Array.isArray(item.permission) ? item.permission : [item.permission];
  return required.some((flag) => permissions[flag]);
}

interface NavSection {
  title: string;
  items: NavItem[];
}

interface SidebarProps {
  variant: "admin" | "client";
}

export function Sidebar({ variant }: SidebarProps) {
  const pathname = usePathname();
  const { isCollapsed, isMobileOpen, toggleCollapse, toggleMobile } =
    useSidebar();
  const { logout, permissions } = useAuth();

  const [isDesktopApp, setIsDesktopApp] = useState(true);
  const [isWindows, setIsWindows] = useState(true);
  useEffect(() => {
    setIsDesktopApp(Boolean((window as any).desktop?.isElectron));
    setIsWindows(/Win/i.test(navigator.userAgent));
  }, []);

  const clientSections: NavSection[] = [
    {
      title: "Workspace",
      items: [
        {
          label: "Dashboard",
          href: "/client/dashboard",
          icon: <LayoutDashboard size={17} />,
        },
        {
          label: "Users",
          href: "/client/users",
          icon: <Users size={17} />,
          permission: "view_user",
        },
        {
          label: "Teams",
          href: "/client/teams",
          icon: <Users2 size={17} />,
          permission: "view_team",
        },
        {
          label: "Permissions",
          href: "/client/permissions",
          icon: <ShieldCheck size={17} />,
          permission: "edit_role_permissions",
        },
        {
          label: "Agents",
          href: "/client/agents",
          icon: <Bot size={17} />,
          permission: "view_agent",
        },
        {
          label: "Projects",
          href: "/client/projects",
          icon: <FolderKanban size={17} />,
        },
        {
          label: "Tools",
          href: "/client/tools",
          icon: <Wrench size={17} />,
          permission: "view_tool",
        },
        {
          label: "MCP Servers",
          href: "/client/mcp-servers",
          icon: <Plug size={17} />,
          permission: "view_tool",
        },
        {
          label: "DB Connections",
          href: "/client/db-connections",
          icon: <Database size={17} />,
          permission: "view_db_connection",
        },
        {
          label: "Connectors",
          href: "/client/connectors",
          icon: <PlugZap size={17} />,
        },
        {
          label: "Orchestrations",
          href: "/client/orchestrations",
          icon: <GitBranch size={17} />,
          permission: "view_agent",
        },
        {
          label: "Schedules",
          href: "/client/schedules",
          icon: <CalendarClock size={17} />,
          permission: "view_schedule",
        },
        {
          label: "Chatbot Widgets",
          href: "/client/widgets",
          icon: <MessageCircle size={17} />,
          permission: "view_widget",
        },
        {
          label: "Playground",
          href: "/client/playground",
          icon: <Terminal size={17} />,
          permission: "create_chat_session",
        },
        {
          label: "Observability",
          href: "/client/tracing",
          icon: <Activity size={17} />,
          permission: "view_trace",
        },
      ],
    },
    {
      title: "Account",
      items: [
        {
          label: "Settings",
          href: "/client/settings",
          icon: <Settings size={17} />,
        },
        { label: "Help", href: "/client/help", icon: <HelpCircle size={17} /> },
      ],
    },
  ];

  const adminItems: NavItem[] = [
    {
      label: "Dashboard",
      href: "/admin/dashboard",
      icon: <LayoutDashboard size={17} />,
    },
    {
      label: "Organizations",
      href: "/admin/organizations",
      icon: <Building2 size={17} />,
      permission: "create_org",
    },
    {
      label: "Users",
      href: "/admin/users",
      icon: <Users size={17} />,
      permission: ["view_user", "create_user", "edit_user", "delete_user"],
    },
    {
      label: "Agents",
      href: "/admin/agents",
      icon: <Bot size={17} />,
      permission: "create_agent",
    },
    {
      label: "Projects",
      href: "/client/projects",
      icon: <FolderKanban size={17} />,
    },
    {
      label: "Tool Registry",
      href: "/admin/tool-registry",
      icon: <Package size={17} />,
      permission: "create_tool",
    },
    {
      label: "MCP Servers",
      href: "/admin/mcp-servers",
      icon: <Plug size={17} />,
      permission: "create_tool",
    },
    {
      label: "Connectors",
      href: "/admin/connectors",
      icon: <PlugZap size={17} />,
      permission: "create_tool",
    },
    {
      label: "Chatbot Widgets",
      href: "/admin/widgets",
      icon: <MessageCircle size={17} />,
      permission: "view_widget",
    },
    {
      label: "Playground",
      href: "/admin/playground",
      icon: <Terminal size={17} />,
      permission: "create_chat_session",
    },
    {
      label: "Observability",
      href: "/admin/tracing",
      icon: <Activity size={17} />,
      permission: "view_trace",
    },
    {
      label: "Settings",
      href: "/admin/settings",
      icon: <Settings size={17} />,
    },
    { label: "Help", href: "/admin/help", icon: <HelpCircle size={17} /> },
  ];

  const isActive = (href: string) => pathname?.startsWith(href) ?? false;

  const NavLink = ({ item }: { item: NavItem }) => {
    const active = isActive(item.href);
    return (
      <Link
        href={item.href}
        title={isCollapsed ? item.label : undefined}
        onClick={() => toggleMobile()}
        className={cn(
          "group relative flex items-center gap-3 mx-2 px-3 py-2.5 rounded-xl text-[13px] font-medium",
          "transition-[background-color,color] duration-200 active:scale-[0.98] active:duration-100",
          active
            ? "bg-gradient-to-r from-violet-500/15 to-violet-500/5 dark:from-violet-500/20 dark:to-violet-500/5 text-violet-700 dark:text-violet-300"
            : "text-[var(--text-2)] hover:bg-black/[0.045] dark:hover:bg-white/[0.05] hover:text-[var(--text-1)]",
        )}
      >
        {/* Active indicator line */}
        {active && (
          <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full bg-violet-500 dark:bg-violet-400 animate-scaleIn" />
        )}

        <span
          className={cn(
            "shrink-0 transition-colors duration-200",
            active
              ? "text-violet-600 dark:text-violet-400"
              : "text-[var(--text-3)] group-hover:text-[var(--text-2)]",
          )}
        >
          {item.icon}
        </span>

        <span
          className={cn(
            "truncate transition-[opacity,width] duration-[220ms]",
            isCollapsed ? "opacity-0 w-0 overflow-hidden" : "opacity-100",
          )}
        >
          {item.label}
        </span>

        {/* Active glow dot */}
        {active && !isCollapsed && (
          <span
            className="ml-auto w-[6px] h-[6px] rounded-full bg-violet-500 dark:bg-violet-400 shrink-0 animate-scaleIn
            shadow-[0_0_6px_2px_rgba(124,58,237,0.5)] dark:shadow-[0_0_6px_2px_rgba(167,139,250,0.5)]"
          />
        )}
      </Link>
    );
  };

  return (
    <>
      {/* Mobile overlay */}
      {isMobileOpen && (
        <div
          className="fixed inset-0 bg-black/50 backdrop-blur-sm z-30 lg:hidden animate-fadeIn"
          onClick={toggleMobile}
        />
      )}

      {/* Sidebar panel */}
      <aside
        className={cn(
          "fixed left-0 top-0 h-screen z-40 flex flex-col",
          /* Glass background — unified with top-nav header */
          "bg-white/[0.88] dark:bg-[#0b0b18]/90",
          "backdrop-blur-2xl",
          "border-r",
          "border-black/[0.07] dark:border-white/[0.07]",
          /* Width transition */
          "transition-[width,transform] duration-[220ms] ease-[cubic-bezier(0.16,1,0.3,1)]",
          isCollapsed ? "w-[68px]" : "w-[252px]",
          "max-lg:transition-transform",
          isMobileOpen ? "max-lg:translate-x-0" : "max-lg:-translate-x-full",
        )}
      >
        {/* ── Logo / header ── same height & glass as top-nav ── */}
        <div
          className="relative h-[56px] flex items-center px-4 shrink-0
          border-b border-black/[0.06] dark:border-white/[0.06]"
        >
          <Link
            href={variant === "admin" ? "/admin/dashboard" : "/client/dashboard"}
            className="flex items-center gap-2.5 min-w-0 flex-1 hover:opacity-85 active:scale-[0.98] transition-[opacity,transform] duration-150 cursor-pointer"
            title="Go to Dashboard"
          >
            {/* Logo mark — shared brand glyph (flat violet, matches landing/login) */}
            <span className="flex size-8 items-center justify-center rounded-[10px] bg-violet-600 glow-violet-sm shrink-0">
              <LogoMark className="text-white" size={18} />
            </span>

            <span
              className={cn(
                "font-extrabold text-[15px] tracking-tight text-[var(--text-1)]",
                "whitespace-nowrap transition-[opacity,width] duration-[220ms]",
                isCollapsed ? "opacity-0 w-0 overflow-hidden" : "opacity-100",
              )}
            >
              ONE
              <span className="text-violet-600 dark:text-violet-400">-AI</span>
            </span>
          </Link>

          <Button
            variant="ghost"
            size="icon-xs"
            onClick={toggleCollapse}
            className={cn(
              "hidden lg:flex shrink-0 text-[var(--text-3)] hover:text-[var(--text-1)] hover:bg-black/[0.05] dark:hover:bg-white/[0.06]",
              isCollapsed &&
                "absolute -right-3 top-1/2 -translate-y-1/2 bg-white dark:bg-[#0b0b18] border border-[var(--border)] shadow-sm z-50 rounded-full w-6 h-6 flex items-center justify-center",
            )}
            aria-label="Toggle sidebar"
          >
            <ChevronLeft className={cn("w-4 h-4 transition-transform duration-[220ms]", isCollapsed && "rotate-180")} />
          </Button>
          <Button
            variant="ghost"
            size="icon-xs"
            onClick={toggleMobile}
            className="lg:hidden shrink-0"
          >
            <X className="w-4 h-4" />
          </Button>
        </div>

        {/* ── Navigation ── */}
        <nav className="flex-1 overflow-y-auto py-2 scrollbar-none">
          {variant === "client"
            ? clientSections
                .map((section) => ({
                  ...section,
                  items: section.items.filter((item) => hasNavPermission(item, permissions)),
                }))
                .filter((section) => section.items.length > 0)
                .map((section, si) => (
                  <div key={section.title} className={cn(si > 0 && "mt-1")}>
                    {!isCollapsed ? (
                      <p
                        className="text-[10px] font-bold tracking-[0.1em] text-[var(--text-3)] uppercase
                      px-5 pt-4 pb-1.5"
                      >
                        {section.title}
                      </p>
                    ) : (
                      si > 0 && (
                        <div className="my-2 mx-4 border-t border-[var(--border)]" />
                      )
                    )}
                    {section.items.map((item) => (
                      <NavLink key={item.href} item={item} />
                    ))}
                  </div>
                ))
            : adminItems
                .filter((item) => hasNavPermission(item, permissions))
                .map((item) => <NavLink key={item.href} item={item} />)}
        </nav>

        {/* ── Footer ── */}
        <div className="pb-2 border-t border-black/[0.06] dark:border-white/[0.06]">
          {/* CLI promo card */}
          {!isCollapsed && (
            <div className="mx-3 my-3 rounded-xl overflow-hidden relative">
              <div
                className="absolute inset-0
                bg-gradient-to-br from-violet-500/10 via-transparent to-indigo-500/10
                dark:from-violet-600/20 dark:to-indigo-600/10"
              />
              <div className="absolute inset-0 border border-violet-400/15 dark:border-violet-500/20 rounded-xl" />
              <div className="relative p-3">
                <p className="text-[12px] font-semibold text-[var(--text-1)]">
                  ONE-AI CLI
                </p>
                <p className="text-[11px] text-[var(--text-3)] mt-0.5">
                  Run agents from your terminal
                </p>
                <Button
                  variant="outline"
                  size="xs"
                  className="mt-2 h-6 text-[11px]
                    border-violet-300/60 dark:border-violet-700/60
                    text-violet-700 dark:text-violet-300
                    hover:bg-violet-50 dark:hover:bg-violet-900/20"
                >
                  <Download className="w-3 h-3 mr-1" />
                  Download
                </Button>
              </div>
            </div>
          )}

          {/* Desktop app promo card */}
          {!isCollapsed && !isDesktopApp && (
            <div className="mx-3 my-3 rounded-xl overflow-hidden relative">
              <div
                className="absolute inset-0
                bg-gradient-to-br from-violet-500/10 via-transparent to-indigo-500/10
                dark:from-violet-600/20 dark:to-indigo-600/10"
              />
              <div className="absolute inset-0 border border-violet-400/15 dark:border-violet-500/20 rounded-xl" />
              <div className="relative p-3">
                <p className="text-[12px] font-semibold text-[var(--text-1)] flex items-center gap-1.5">
                  <Monitor className="w-3.5 h-3.5" />
                  ONE-AI Desktop
                </p>
                <p className="text-[11px] text-[var(--text-3)] mt-0.5">
                  {isWindows
                    ? "Get the native app for Windows"
                    : "Windows app available now — Mac & Linux coming soon"}
                </p>
                <Button
                  nativeButton={false}
                  render={<a href="/downloads/One-AI-Setup.exe" download />}
                  variant="outline"
                  size="xs"
                  className="mt-2 h-6 text-[11px]
                    border-violet-300/60 dark:border-violet-700/60
                    text-violet-700 dark:text-violet-300
                    hover:bg-violet-50 dark:hover:bg-violet-900/20"
                >
                  <Download className="w-3 h-3 mr-1" />
                  Download for Windows
                </Button>
              </div>
            </div>
          )}

          {/* Logout */}
          <button
            type="button"
            onClick={logout}
            className={cn(
              "flex items-center gap-3 mx-2 px-3 py-2.5 rounded-xl w-[calc(100%-1rem)]",
              "text-[13px] font-medium text-[var(--text-3)]",
              "hover:bg-red-50 dark:hover:bg-red-500/10",
              "hover:text-red-600 dark:hover:text-red-400",
              "transition-[background-color,color] duration-150",
            )}
          >
            <LogOut size={17} className="shrink-0" />
            {!isCollapsed && <span>Logout</span>}
          </button>
        </div>
      </aside>
    </>
  );
}
