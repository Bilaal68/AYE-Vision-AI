'use client';

import { useMemo } from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import {
  Camera,
  Bell,
  Users,
  ShieldCheck,
  Plus,
  UserPlus,
  AlertTriangle,
  ArrowUpRight,
  Loader2,
  Activity,
  CheckCircle2,
  XCircle,
  AlertCircle,
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { apiClient } from '@/lib/api-client';

interface DashboardStats {
  cameras: { total: number; online: number; offline: number; degraded: number };
  alerts: { today: number; critical: number; warning: number; info: number };
  persons: { enrolled: number };
  rules: { active: number };
}

interface AlertTrend {
  date: string;
  critical: number;
  warning: number;
  info: number;
}

interface AlertTypeDistribution {
  type: string;
  count: number;
}

interface CameraHealth {
  id: string;
  name: string;
  status: 'online' | 'offline' | 'degraded';
}

interface RecentEvent {
  id: string;
  type?: string;
  event_type?: string;
  camera?: string;
  camera_name?: string;
  camera_id?: string;
  message?: string;
  severity?: 'critical' | 'warning' | 'info';
  timestamp?: string;
}

export default function DashboardPage() {
  const { data: stats, isLoading: statsLoading } = useQuery<DashboardStats>({
    queryKey: ['dashboard', 'stats'],
    queryFn: async () => {
      const res = await apiClient.get('/api/v1/dashboard/stats');
      return res.data;
    },
    refetchInterval: 30000,
  });

  const { data: alertTrends, isLoading: trendsLoading } = useQuery<AlertTrend[]>({
    queryKey: ['dashboard', 'alert-trends'],
    queryFn: async () => {
      const res = await apiClient.get('/api/v1/dashboard/alert-trends');
      return res.data;
    },
  });

  const { data: alertDistribution } = useQuery<AlertTypeDistribution[]>({
    queryKey: ['dashboard', 'alert-distribution'],
    queryFn: async () => {
      const res = await apiClient.get('/api/v1/dashboard/alert-distribution');
      return res.data;
    },
  });

  const { data: cameraHealthList } = useQuery<CameraHealth[]>({
    queryKey: ['dashboard', 'camera-health'],
    queryFn: async () => {
      const res = await apiClient.get('/api/v1/cameras/health');
      return res.data;
    },
    refetchInterval: 15000,
  });

  const { data: recentEvents } = useQuery<RecentEvent[]>({
    queryKey: ['dashboard', 'recent-events'],
    queryFn: async () => {
      const res = await apiClient.get('/api/v1/events/recent', {
        params: { limit: 20 },
      });
      return res.data;
    },
    refetchInterval: 10000,
  });

  const statCards = useMemo(
    () => [
      {
        title: 'Total Cameras',
        value: stats?.cameras?.total ?? 0,
        subtitle: `${stats?.cameras?.online ?? 0} online / ${stats?.cameras?.offline ?? 0} offline`,
        icon: Camera,
        color: 'blue',
        href: '/dashboard/cameras',
      },
      {
        title: 'Alerts Today',
        value: stats?.alerts?.today ?? 0,
        subtitle: `${stats?.alerts?.critical ?? 0} critical / ${stats?.alerts?.warning ?? 0} warning`,
        icon: Bell,
        color: 'red',
        href: '/dashboard/alerts',
      },
      {
        title: 'Persons Enrolled',
        value: stats?.persons?.enrolled ?? 0,
        subtitle: 'Face recognition database',
        icon: Users,
        color: 'green',
        href: '/dashboard/faces',
      },
      {
        title: 'Active Rules',
        value: stats?.rules?.active ?? 0,
        subtitle: 'Detection rules configured',
        icon: ShieldCheck,
        color: 'purple',
        href: '/dashboard/admin/settings',
      },
    ],
    [stats]
  );

  const colorMap: Record<string, string> = {
    blue: 'bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400',
    red: 'bg-red-50 text-red-600 dark:bg-red-900/30 dark:text-red-400',
    green: 'bg-green-50 text-green-600 dark:bg-green-900/30 dark:text-green-400',
    purple: 'bg-purple-50 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400',
  };

  const severityBadge = (severity: string) => {
    switch (severity) {
      case 'critical':
        return <Badge variant="destructive">Critical</Badge>;
      case 'warning':
        return <Badge className="bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">Warning</Badge>;
      default:
        return <Badge variant="secondary">Info</Badge>;
    }
  };

  const statusDot = (status: string) => {
    switch (status) {
      case 'online':
        return 'bg-green-500';
      case 'offline':
        return 'bg-red-500';
      case 'degraded':
        return 'bg-yellow-500';
      default:
        return 'bg-slate-400';
    }
  };

  if (statsLoading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
          <p className="text-sm text-slate-500">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Dashboard</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Real-time overview of your surveillance system
          </p>
        </div>
        <div className="flex gap-2">
          <Link href="/dashboard/cameras">
            <Button variant="outline" size="sm">
              <Plus className="mr-1 h-4 w-4" />
              Add Camera
            </Button>
          </Link>
          <Link href="/dashboard/faces/enroll">
            <Button variant="outline" size="sm">
              <UserPlus className="mr-1 h-4 w-4" />
              Enroll Face
            </Button>
          </Link>
          <Link href="/dashboard/alerts">
            <Button size="sm">
              <AlertTriangle className="mr-1 h-4 w-4" />
              View Alerts
            </Button>
          </Link>
        </div>
      </div>

      {/* Stat Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {statCards.map((stat, idx) => {
          const Icon = stat.icon;
          const isHighlighted = idx === 2; // Matching reference card 3 highlighting
          return (
            <Link key={stat.title} href={stat.href}>
              <Card className={`transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg border-[#020b1b] ${
                isHighlighted
                  ? 'bg-gradient-to-br from-[#122845] to-[#1c3a64] border-[#2d9ce4]/40 shadow-md shadow-[#2d9ce4]/10'
                  : 'bg-[#0a1c31] hover:border-[#152e4f]'
              }`}>
                <CardContent className="p-5">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className={`text-xs font-semibold uppercase tracking-wider ${isHighlighted ? 'text-blue-200' : 'text-[#829dbe]'}`}>
                        {stat.title}
                      </p>
                      <p className="mt-1 text-2xl font-bold tracking-tight text-white">
                        {stat.value.toLocaleString()}
                      </p>
                      <p className={`mt-1 text-xs ${isHighlighted ? 'text-blue-200/80' : 'text-[#829dbe]/80'}`}>
                        {stat.subtitle}
                      </p>
                    </div>
                    <div className={`rounded-lg p-3 ${
                      isHighlighted
                        ? 'bg-[#2d9ce4] text-white shadow-sm shadow-[#2d9ce4]/40'
                        : `${colorMap[stat.color]} bg-[#08162a] border border-[#020b1b]`
                    }`}>
                      <Icon className="h-5 w-5" />
                    </div>
                  </div>
                </CardContent>
              </Card>
            </Link>
          );
        })}
      </div>

      {/* Charts Row */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Alert Trend Chart */}
        <Card className="border-[#020b1b] bg-[#0a1c31]">
          <CardHeader>
            <CardTitle className="text-base text-white">Alert Trends</CardTitle>
            <CardDescription className="text-[#829dbe]">Alerts over the last 7 days</CardDescription>
          </CardHeader>
          <CardContent>
            {trendsLoading ? (
              <div className="flex h-64 items-center justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-[#829dbe]" />
              </div>
            ) : alertTrends && alertTrends.length > 0 ? (
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={alertTrends}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#0d233e" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 12, fill: '#829dbe' }}
                    stroke="#1a3558"
                  />
                  <YAxis tick={{ fontSize: 12, fill: '#829dbe' }} stroke="#1a3558" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0a1c31',
                      border: '1px solid #1a3558',
                      borderRadius: '8px',
                      fontSize: '12px',
                      color: '#fff',
                    }}
                  />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="critical"
                    stroke="#ef4444"
                    strokeWidth={2}
                    dot={false}
                    name="Critical"
                  />
                  <Line
                    type="monotone"
                    dataKey="warning"
                    stroke="#f59e0b"
                    strokeWidth={2}
                    dot={false}
                    name="Warning"
                  />
                  <Line
                    type="monotone"
                    dataKey="info"
                    stroke="#2d9ce4"
                    strokeWidth={2}
                    dot={false}
                    name="Info"
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-64 flex-col items-center justify-center text-[#829dbe]">
                <Activity className="mb-2 h-8 w-8" />
                <p className="text-sm">No alert data available yet</p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Alert Type Distribution */}
        <Card className="border-[#020b1b] bg-[#0a1c31]">
          <CardHeader>
            <CardTitle className="text-base text-white">Alert Distribution</CardTitle>
            <CardDescription className="text-[#829dbe]">Alerts by type</CardDescription>
          </CardHeader>
          <CardContent>
            {alertDistribution && alertDistribution.length > 0 ? (
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={alertDistribution}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#0d233e" />
                  <XAxis
                    dataKey="type"
                    tick={{ fontSize: 12, fill: '#829dbe' }}
                    stroke="#1a3558"
                  />
                  <YAxis tick={{ fontSize: 12, fill: '#829dbe' }} stroke="#1a3558" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0a1c31',
                      border: '1px solid #1a3558',
                      borderRadius: '8px',
                      fontSize: '12px',
                      color: '#fff',
                    }}
                  />
                  <Bar dataKey="count" fill="#2d9ce4" radius={[4, 4, 0, 0]} name="Count" />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-64 flex-col items-center justify-center text-[#829dbe]">
                <Activity className="mb-2 h-8 w-8" />
                <p className="text-sm">No distribution data available yet</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Camera Health + Recent Events */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Camera Health Grid */}
        <Card className="border-[#020b1b] bg-[#0a1c31]">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-base text-white">Camera Health</CardTitle>
              <CardDescription className="text-[#829dbe]">Real-time camera status</CardDescription>
            </div>
            <Link href="/dashboard/cameras">
              <Button variant="ghost" size="sm" className="text-[#2d9ce4] hover:bg-[#08162a]">
                View all
                <ArrowUpRight className="ml-1 h-3 w-3" />
              </Button>
            </Link>
          </CardHeader>
          <CardContent>
            {cameraHealthList && cameraHealthList.length > 0 ? (
              <div className="grid grid-cols-4 gap-3 sm:grid-cols-6 md:grid-cols-8">
                {cameraHealthList.map((cam) => (
                  <Link
                    key={cam.id}
                    href={`/dashboard/cameras/${cam.id}`}
                    className="group flex flex-col items-center gap-1 rounded-lg p-2 hover:bg-[#08162a]"
                    title={`${cam.name} - ${cam.status}`}
                  >
                    <div
                      className={`h-4 w-4 rounded-full ${statusDot(cam.status)} ring-2 ring-offset-1 ring-offset-[#0a1c31] ${
                        cam.status === 'online'
                          ? 'ring-green-500/30'
                          : cam.status === 'offline'
                          ? 'ring-red-500/30'
                          : 'ring-yellow-500/30'
                      }`}
                    />
                    <span className="max-w-full truncate text-[10px] text-[#829dbe] group-hover:text-white">
                      {cam.name}
                    </span>
                  </Link>
                ))}
              </div>
            ) : (
              <div className="flex h-40 flex-col items-center justify-center text-[#829dbe]">
                <Camera className="mb-2 h-8 w-8" />
                <p className="text-sm">No cameras configured</p>
                <Link href="/dashboard/cameras">
                  <Button variant="link" size="sm" className="mt-1 text-[#2d9ce4]">
                    Add a camera
                  </Button>
                </Link>
              </div>
            )}

            {/* Legend */}
            {cameraHealthList && cameraHealthList.length > 0 && (
              <div className="mt-4 flex items-center gap-4 border-t border-[#020b1b] pt-3">
                <div className="flex items-center gap-1.5 text-xs text-[#829dbe]">
                  <div className="h-2.5 w-2.5 rounded-full bg-green-500" />
                  Online ({cameraHealthList.filter((c) => c.status === 'online').length})
                </div>
                <div className="flex items-center gap-1.5 text-xs text-[#829dbe]">
                  <div className="h-2.5 w-2.5 rounded-full bg-red-500" />
                  Offline ({cameraHealthList.filter((c) => c.status === 'offline').length})
                </div>
                <div className="flex items-center gap-1.5 text-xs text-[#829dbe]">
                  <div className="h-2.5 w-2.5 rounded-full bg-yellow-500" />
                  Degraded ({cameraHealthList.filter((c) => c.status === 'degraded').length})
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Recent Events */}
        <Card className="border-[#020b1b] bg-[#0a1c31]">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-base text-white">Recent Events</CardTitle>
              <CardDescription className="text-[#829dbe]">Live surveillance activity</CardDescription>
            </div>
            <Link href="/dashboard/alerts">
              <Button variant="ghost" size="sm" className="text-[#2d9ce4] hover:bg-[#08162a]">
                View all
                <ArrowUpRight className="ml-1 h-3 w-3" />
              </Button>
            </Link>
          </CardHeader>
          <CardContent>
            {recentEvents && recentEvents.length > 0 ? (
              <div className="space-y-3">
                {recentEvents.slice(0, 5).map((evt) => (
                  <div
                    key={evt.id}
                    className="flex items-center justify-between rounded-lg border border-[#020b1b] bg-[#08162a] p-3 transition-colors hover:border-[#1a3558]"
                  >
                    <div className="flex items-center gap-3">
                      <div className="rounded-lg bg-[#0d2f55] p-2 text-[#2d9ce4]">
                        <Activity className="h-4 w-4" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-white">
                          {(evt.type || evt.event_type || 'Event').replace(/_/g, ' ')}
                        </p>
                        <p className="text-xs text-[#829dbe]">
                          Camera: {evt.camera || evt.camera_name || evt.camera_id || 'Unknown'}
                        </p>
                      </div>
                    </div>
                    <span className="text-xs text-[#829dbe]/70">
                      {evt.timestamp ? new Date(evt.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex h-40 flex-col items-center justify-center text-[#829dbe]">
                <Activity className="mb-2 h-8 w-8" />
                <p className="text-sm">No recent activity</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
