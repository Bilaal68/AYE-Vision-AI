'use client';

import { useEffect, useState, useMemo, useCallback } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import Link from 'next/link';
import { useAuthStore } from '@/stores/useAuthStore';
import { useAlertStore } from '@/stores/useAlertStore';
import { getAccessToken, isAuthenticated as checkTokenValid } from '@/lib/auth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { useTheme } from 'next-themes';
import {
  Eye,
  LayoutDashboard,
  Video,
  Bell,
  Camera,
  ShieldCheck,
  Users,
  Car,
  Footprints,
  Flame,
  CalendarCheck,
  HardHat,
  TrendingUp,
  Film,
  FileBarChart,
  Settings,
  UserCog,
  BellRing,
  ClipboardList,
  ChevronLeft,
  ChevronRight,
  Search,
  Sun,
  Moon,
  LogOut,
  User,
  ChevronDown,
  Menu,
  X,
  Loader2,
  Bot,
} from 'lucide-react';

interface NavItem {
  label: string;
  href: string;
  icon: React.ElementType;
}

interface NavGroup {
  title: string;
  items: NavItem[];
}

const navigationGroups: NavGroup[] = [
  {
    title: 'Overview',
    items: [
      { label: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
    ],
  },
  {
    title: 'Monitoring',
    items: [
      { label: 'Live View', href: '/dashboard/live', icon: Video },
      { label: 'Alerts', href: '/dashboard/alerts', icon: Bell },
    ],
  },
  {
    title: 'Management',
    items: [
      { label: 'Cameras', href: '/dashboard/cameras', icon: Camera },
    ],
  },
  {
    title: 'Recognition',
    items: [
      { label: 'Faces', href: '/dashboard/faces', icon: Users },
      { label: 'Vehicles', href: '/dashboard/vehicles', icon: Car },
    ],
  },
  {
    title: 'Analytics',
    items: [
      { label: 'Footfall', href: '/dashboard/analytics/footfall', icon: Footprints },
      { label: 'Heatmaps', href: '/dashboard/analytics/heatmap', icon: Flame },
      { label: 'Attendance', href: '/dashboard/analytics/attendance', icon: CalendarCheck },
      { label: 'PPE', href: '/dashboard/analytics/ppe', icon: HardHat },
      { label: 'Patterns', href: '/dashboard/analytics/patterns', icon: TrendingUp },
    ],
  },
  {
    title: 'AI Assistant',
    items: [
      { label: 'AYE AI', href: '/dashboard/copilot', icon: Bot },
    ],
  },
  {
    title: 'System',
    items: [
      { label: 'Recordings', href: '/dashboard/recordings', icon: Film },
      { label: 'Reports', href: '/dashboard/reports', icon: FileBarChart },
      { label: 'Admin', href: '/dashboard/admin/users', icon: Settings },
    ],
  },
];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, isAuthenticated, logout } = useAuthStore();
  const { unreadCount } = useAlertStore();
  const { theme, setTheme } = useTheme();

  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);

  useEffect(() => {
    // Primary check: does a valid JWT exist in localStorage?
    // This is synchronous and doesn't depend on Zustand hydration.
    const token = getAccessToken();
    const tokenValid = token && checkTokenValid();

    if (!tokenValid) {
      // No valid token at all — definitely not authenticated
      router.replace('/login');
    } else {
      // Valid token exists — allow dashboard access.
      // Zustand's isAuthenticated may still be false due to async hydration,
      // but the token proves the user logged in successfully.
      setIsCheckingAuth(false);
    }
  }, [router]);

  useEffect(() => {
    setMobileSidebarOpen(false);
  }, [pathname]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (userMenuOpen) {
        setUserMenuOpen(false);
      }
    };
    document.addEventListener('click', handleClickOutside);
    return () => document.removeEventListener('click', handleClickOutside);
  }, [userMenuOpen]);

  const breadcrumbs = useMemo(() => {
    const segments = pathname.split('/').filter(Boolean);
    return segments.map((segment, index) => ({
      label: segment.charAt(0).toUpperCase() + segment.slice(1).replace(/-/g, ' '),
      href: '/' + segments.slice(0, index + 1).join('/'),
      isLast: index === segments.length - 1,
    }));
  }, [pathname]);

  const isActiveRoute = useCallback(
    (href: string) => {
      if (href === '/dashboard') {
        return pathname === '/dashboard';
      }
      return pathname.startsWith(href);
    },
    [pathname]
  );

  const handleLogout = () => {
    logout();
    router.replace('/login');
  };

  if (isCheckingAuth) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 dark:bg-slate-900">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
          <p className="text-sm text-slate-500">Loading...</p>
        </div>
      </div>
    );
  }

  const SidebarContent = () => (
    <div className="flex h-full flex-col">
      {/* Logo */}
      <div className="flex h-16 items-center gap-3 border-b border-[#020b1b] px-4">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#2d9ce4] shadow-md shadow-[#2d9ce4]/30">
          <Eye className="h-5 w-5 text-white" />
        </div>
        {!sidebarCollapsed && (
          <div className="flex flex-col">
            <span className="text-base font-bold tracking-tight text-white flex items-center gap-1.5">
              AYE Vision
              <span className="rounded bg-[#2d9ce4]/20 px-1 py-0.2 text-[9px] font-semibold text-[#2d9ce4] border border-[#2d9ce4]/30">PRO</span>
            </span>
            <span className="text-[10px] text-[#829dbe] font-medium">Zero Trace INSA</span>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-2 py-4">
        <div className="space-y-5">
          {navigationGroups.map((group) => (
            <div key={group.title}>
              {!sidebarCollapsed && (
                <p className="mb-1.5 px-3 text-[11px] font-bold uppercase tracking-wider text-[#829dbe]/70">
                  {group.title}
                </p>
              )}
              <div className="space-y-0.5">
                {group.items.map((item) => {
                  const Icon = item.icon;
                  const active = isActiveRoute(item.href);
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      prefetch={false}
                      className={`relative flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-all duration-150 ${
                        active
                          ? 'bg-[#0d2f55] text-white shadow-inner font-semibold'
                          : 'text-[#829dbe] hover:bg-[#0a1c31] hover:text-slate-100'
                      }`}
                      title={sidebarCollapsed ? item.label : undefined}
                    >
                      {active && (
                        <span className="absolute left-0 top-1/2 h-5 w-1 -translate-y-1/2 rounded-r bg-[#2d9ce4]" />
                      )}
                      <Icon className={`h-4 w-4 shrink-0 ${active ? 'text-[#2d9ce4]' : 'text-[#829dbe]'}`} />
                      {!sidebarCollapsed && <span className="tracking-tight">{item.label}</span>}
                      {item.href === '/dashboard/alerts' && unreadCount > 0 && (
                        <Badge
                          variant="destructive"
                          className={`ml-auto text-xs ${sidebarCollapsed ? 'absolute -right-1 -top-1' : ''}`}
                        >
                          {unreadCount > 99 ? '99+' : unreadCount}
                        </Badge>
                      )}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </nav>

      {/* Collapse Toggle */}
      <div className="hidden border-t border-slate-200 p-3 dark:border-slate-700 lg:block">
        <button
          onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
          className="flex w-full items-center justify-center rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-300"
        >
          {sidebarCollapsed ? (
            <ChevronRight className="h-5 w-5" />
          ) : (
            <ChevronLeft className="h-5 w-5" />
          )}
        </button>
      </div>
    </div>
  );

  return (
    <div className="flex h-screen bg-[#08162a] text-slate-100">
      {/* Desktop Sidebar */}
      <aside
        className={`hidden border-r border-[#020b1b] bg-[#09172a] transition-all duration-300 lg:block ${
          sidebarCollapsed ? 'w-[72px]' : 'w-64'
        }`}
      >
        <SidebarContent />
      </aside>

      {/* Mobile Sidebar Overlay */}
      {mobileSidebarOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => setMobileSidebarOpen(false)}
          />
          <aside className="relative z-10 h-full w-64 bg-white shadow-xl dark:bg-slate-800">
            <div className="absolute right-2 top-4 z-20">
              <button
                onClick={() => setMobileSidebarOpen(false)}
                className="rounded-lg p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <SidebarContent />
          </aside>
        </div>
      )}

      {/* Main Content */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top Header Bar */}
        <header className="flex h-16 items-center justify-between border-b border-[#020b1b] bg-[#09172a] px-4 lg:px-6">
          <div className="flex items-center gap-4">
            {/* Mobile menu button */}
            <button
              onClick={() => setMobileSidebarOpen(true)}
              className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-700 dark:hover:text-slate-300 lg:hidden"
            >
              <Menu className="h-5 w-5" />
            </button>

            {/* Breadcrumbs */}
            <nav className="hidden items-center gap-1 text-sm sm:flex">
              {breadcrumbs.map((crumb, index) => (
                <div key={crumb.href} className="flex items-center gap-1">
                  {index > 0 && (
                    <span className="text-slate-300 dark:text-slate-600">/</span>
                  )}
                  {crumb.isLast ? (
                    <span className="font-medium text-slate-900 dark:text-white">
                      {crumb.label}
                    </span>
                  ) : (
                    <Link
                      href={crumb.href}
                      className="text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
                    >
                      {crumb.label}
                    </Link>
                  )}
                </div>
              ))}
            </nav>
          </div>

          <div className="flex items-center gap-2">
            {/* Search */}
            <div className="relative hidden md:block">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#829dbe]" />
              <Input
                type="text"
                placeholder="Search..."
                className="h-9 w-64 border-[#020b1b] bg-[#0a1c31] pl-9 text-sm text-slate-100 placeholder:text-[#829dbe]/60 focus:border-[#2d9ce4]"
              />
            </div>

            {/* Theme Toggle */}
            <button
              onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
              className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-700 dark:hover:text-slate-300"
              title="Toggle theme"
            >
              {theme === 'dark' ? (
                <Sun className="h-5 w-5" />
              ) : (
                <Moon className="h-5 w-5" />
              )}
            </button>

            {/* Notification Bell */}
            <Link
              href="/dashboard/alerts"
              className="relative rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-700 dark:hover:text-slate-300"
            >
              <Bell className="h-5 w-5" />
              {unreadCount > 0 && (
                <span className="absolute -right-0.5 -top-0.5 flex h-5 min-w-[20px] items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
                  {unreadCount > 99 ? '99+' : unreadCount}
                </span>
              )}
            </Link>

            {/* User Avatar Dropdown */}
            <div className="relative">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setUserMenuOpen(!userMenuOpen);
                }}
                className="flex items-center gap-2 rounded-lg p-1.5 hover:bg-slate-100 dark:hover:bg-slate-700"
              >
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-100 text-sm font-semibold text-blue-700 dark:bg-blue-900 dark:text-blue-300">
                  {user?.full_name?.charAt(0)?.toUpperCase() || 'U'}
                </div>
                <span className="hidden text-sm font-medium text-slate-700 dark:text-slate-200 lg:block">
                  {user?.full_name || 'User'}
                </span>
                <ChevronDown className="hidden h-4 w-4 text-slate-400 lg:block" />
              </button>

              {userMenuOpen && (
                <div className="absolute right-0 top-full z-50 mt-1 w-56 rounded-xl border border-[#1f2d48] bg-[#0f1a30] py-1 shadow-2xl">
                  <div className="border-b border-[#1f2d48] px-4 py-3">
                    <p className="text-sm font-semibold text-white">
                      {user?.full_name || 'User'}
                    </p>
                    <p className="text-xs text-slate-400">
                      {user?.email || 'user@example.com'}
                    </p>
                  </div>
                  <Link
                    href="/dashboard/admin/settings"
                    className="flex items-center gap-2 px-4 py-2 text-sm text-slate-300 hover:bg-[#15233c] hover:text-white"
                  >
                    <User className="h-4 w-4" />
                    Profile
                  </Link>
                  <Link
                    href="/dashboard/admin/settings"
                    className="flex items-center gap-2 px-4 py-2 text-sm text-slate-300 hover:bg-[#15233c] hover:text-white"
                  >
                    <Settings className="h-4 w-4" />
                    Settings
                  </Link>
                  <div className="border-t border-[#1f2d48]">
                    <button
                      onClick={handleLogout}
                      className="flex w-full items-center gap-2 px-4 py-2 text-sm text-red-400 hover:bg-red-500/10"
                    >
                      <LogOut className="h-4 w-4" />
                      Logout
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto p-4 lg:p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
