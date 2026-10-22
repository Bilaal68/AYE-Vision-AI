'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import {
  Camera,
  Plus,
  Search,
  LayoutGrid,
  List,
  MapPin,
  Wifi,
  WifiOff,
  Loader2,
  X,
  Video,
  Settings,
  Trash2,
  AlertCircle,
  Play,
  ExternalLink,
  Eye,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { StreamPlayer } from '@/components/camera/stream-player';
import { getAccessToken } from '@/lib/auth';
import { apiClient } from '@/lib/api-client';

function getMjpegUrl(cameraId: string, token: string | null): string {
  if (typeof window === 'undefined') return '';
  const base = window.location.origin;
  const params = new URLSearchParams({ fps: '15', quality: '75' });
  if (token) params.set('token', token);
  return `${base}/api/v1/cameras/${cameraId}/stream/mjpeg?${params.toString()}`;
}

interface CameraItem {
  id: string;
  name: string;
  location?: string;
  location_description?: string;
  stream_url: string;
  status?: 'online' | 'offline' | 'degraded';
  is_online?: boolean;
  protocol: string;
  thumbnail_url: string | null;
  created_at: string;
}

const addCameraSchema = z.object({
  name: z.string().min(1, 'Camera name is required'),
  location: z.string().min(1, 'Location is required'),
  stream_url: z.string().url('Must be a valid URL'),
  protocol: z.enum(['rtsp', 'rtmp', 'hls', 'webrtc']),
  username: z.string().optional(),
  password: z.string().optional(),
});

type AddCameraFormData = z.infer<typeof addCameraSchema>;

export default function CamerasPage() {
  const queryClient = useQueryClient();
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [searchQuery, setSearchQuery] = useState('');
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [quickViewCamera, setQuickViewCamera] = useState<CameraItem | null>(null);
  const accessToken = getAccessToken();

  const { data: camerasData, isLoading } = useQuery({
    queryKey: ['cameras', 'all'],
    queryFn: async () => {
      const res = await apiClient.get('/api/v1/cameras', { params: { limit: 200 } });
      const raw = res.data;
      return (Array.isArray(raw) ? raw : (raw?.items || raw?.data || [])) as CameraItem[];
    },
  });

  const startAllMutation = useMutation({
    mutationFn: async () => {
      await apiClient.post('/api/v1/cameras/start-all');
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cameras'] });
    },
  });

  const cameras = camerasData || [];
  const filteredCameras = cameras.filter((cam) => {
    const loc = cam.location || cam.location_description || '';
    return (
      cam.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      loc.toLowerCase().includes(searchQuery.toLowerCase())
    );
  });

  const addCameraMutation = useMutation({
    mutationFn: async (data: AddCameraFormData) => {
      const res = await apiClient.post('/api/v1/cameras', data);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cameras'] });
      setShowAddDialog(false);
      reset();
    },
  });

  const deleteCameraMutation = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/api/v1/cameras/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cameras'] });
    },
  });

  const handleDeleteCamera = (id: string, name: string) => {
    if (confirm(`Are you sure you want to delete camera "${name}"? This action cannot be undone.`)) {
      deleteCameraMutation.mutate(id);
    }
  };

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<AddCameraFormData>({
    resolver: zodResolver(addCameraSchema),
    defaultValues: {
      protocol: 'rtsp',
    },
  });

  const statusBadge = (status: string) => {
    switch (status) {
      case 'online':
        return (
          <Badge className="bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">
            <Wifi className="mr-1 h-3 w-3" />
            Online
          </Badge>
        );
      case 'offline':
        return (
          <Badge className="bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">
            <WifiOff className="mr-1 h-3 w-3" />
            Offline
          </Badge>
        );
      default:
        return (
          <Badge className="bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
            <AlertCircle className="mr-1 h-3 w-3" />
            Degraded
          </Badge>
        );
    }
  };

  const protocolBadge = (protocol: string) => (
    <Badge variant="outline" className="text-xs">
      {protocol.toUpperCase()}
    </Badge>
  );

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Cameras</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {cameras.length} camera{cameras.length !== 1 ? 's' : ''} configured
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={() => startAllMutation.mutate()}
            disabled={startAllMutation.isPending}
            className="border-blue-600/30 text-blue-400 hover:bg-blue-600/10"
          >
            {startAllMutation.isPending ? (
              <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
            ) : (
              <Play className="mr-1.5 h-4 w-4" />
            )}
            Start All Streams
          </Button>
          <Button onClick={() => setShowAddDialog(true)}>
            <Plus className="mr-1 h-4 w-4" />
            Add Camera
          </Button>
        </div>
      </div>

      {/* Search + View Toggle */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input
            placeholder="Search cameras by name or location..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>
        <div className="flex rounded-lg border border-slate-200 dark:border-slate-700">
          <button
            onClick={() => setViewMode('grid')}
            className={`p-2 ${
              viewMode === 'grid'
                ? 'bg-blue-600 text-white'
                : 'bg-white text-slate-500 dark:bg-slate-800 dark:text-slate-400'
            } rounded-l-lg`}
          >
            <LayoutGrid className="h-4 w-4" />
          </button>
          <button
            onClick={() => setViewMode('list')}
            className={`p-2 ${
              viewMode === 'list'
                ? 'bg-blue-600 text-white'
                : 'bg-white text-slate-500 dark:bg-slate-800 dark:text-slate-400'
            } rounded-r-lg`}
          >
            <List className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="flex h-64 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
        </div>
      ) : filteredCameras.length === 0 ? (
        <div className="flex h-64 flex-col items-center justify-center text-slate-400">
          <Camera className="mb-3 h-10 w-10" />
          <p className="text-sm font-medium">
            {searchQuery ? 'No cameras match your search' : 'No cameras configured'}
          </p>
          {!searchQuery && (
            <Button variant="link" className="mt-1" onClick={() => setShowAddDialog(true)}>
              Add your first camera
            </Button>
          )}
        </div>
      ) : viewMode === 'grid' ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {filteredCameras.map((cam) => {
            const loc = cam.location || cam.location_description || 'Unassigned';
            const status = cam.status || (cam.is_online ? 'online' : 'offline');
            return (
              <div key={cam.id} className="relative group">
                <Card className="overflow-hidden transition-all duration-200 hover:shadow-lg border-border hover:border-primary/50 bg-[#0a1c31]">
                  {/* Thumbnail & Quick Live Open */}
                  <div
                    onClick={() => setQuickViewCamera(cam)}
                    className="relative aspect-video bg-[#08162a] overflow-hidden cursor-pointer"
                    title={`Click to open live video stream for ${cam.name}`}
                  >
                    <img
                      src={cam.thumbnail_url || `/api/v1/cameras/${cam.id}/thumbnail`}
                      alt={cam.name}
                      loading="lazy"
                      className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
                      onError={(e) => {
                        const target = e.currentTarget;
                        target.onerror = null;
                        target.src = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 640 360' fill='%2308162a'%3E%3Crect width='640' height='360'/%3E%3Ctext x='50%25' y='50%25' dominant-baseline='middle' text-anchor='middle' fill='%23829dbe' font-family='sans-serif' font-size='16'%3EStandby / Feed Ready%3C/text%3E%3C/svg%3E";
                      }}
                    />
                    {/* Play Hover Overlay */}
                    <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                      <div className="rounded-full bg-blue-600/90 p-3 text-white shadow-lg backdrop-blur-sm transform transition-transform group-hover:scale-110 flex items-center gap-1.5">
                        <Play className="h-5 w-5 fill-current" />
                        <span className="text-xs font-semibold pr-1">Watch Live</span>
                      </div>
                    </div>
                    <div className="absolute left-2 top-2">
                      {statusBadge(status)}
                    </div>
                    <div className="absolute right-2 top-2 flex items-center gap-1.5">
                      {protocolBadge(cam.protocol)}
                      <button
                        type="button"
                        title="Delete Camera"
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          handleDeleteCamera(cam.id, cam.name);
                        }}
                        className="rounded p-1 bg-black/60 text-slate-300 hover:text-red-400 hover:bg-black/90 transition-colors"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                  <CardContent className="p-3.5 flex items-center justify-between">
                    <div className="min-w-0 flex-1">
                      <button
                        type="button"
                        onClick={() => setQuickViewCamera(cam)}
                        className="font-semibold text-white truncate block text-left hover:text-blue-400 transition-colors max-w-full"
                        title={`Click to open live feed for ${cam.name}`}
                      >
                        {cam.name}
                      </button>
                      <div className="mt-1 flex items-center gap-1 text-xs text-[#829dbe]">
                        <MapPin className="h-3 w-3 shrink-0" />
                        <span className="truncate">{loc}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5 ml-2 shrink-0">
                      <button
                        type="button"
                        onClick={() => setQuickViewCamera(cam)}
                        className="rounded-md bg-blue-600/20 px-2 py-1 text-xs font-medium text-blue-400 hover:bg-blue-600 hover:text-white transition-colors flex items-center gap-1"
                        title="Open live stream immediately"
                      >
                        <Video className="h-3 w-3" />
                        <span className="hidden sm:inline">Live</span>
                      </button>
                      <Link
                        href={`/dashboard/cameras/${cam.id}`}
                        className="rounded-md p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white transition-colors"
                        title="Configure Camera & AI Rules"
                      >
                        <Settings className="h-3.5 w-3.5" />
                      </Link>
                    </div>
                  </CardContent>
                </Card>
              </div>
            );
          })}
        </div>
      ) : (
        <Card>
          <CardContent className="p-0">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50/50 dark:border-slate-700 dark:bg-slate-800/50">
                  <th className="px-4 py-3 text-left font-medium text-slate-600 dark:text-slate-300">
                    Name
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-slate-600 dark:text-slate-300">
                    Location
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-slate-600 dark:text-slate-300">
                    Status
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-slate-600 dark:text-slate-300">
                    Protocol
                  </th>
                  <th className="px-4 py-3 text-right font-medium text-slate-600 dark:text-slate-300">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {filteredCameras.map((cam) => {
                  const loc = cam.location || cam.location_description || 'Unassigned';
                  const status = cam.status || (cam.is_online ? 'online' : 'offline');
                  return (
                    <tr
                      key={cam.id}
                      className="border-b border-slate-100 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800/50"
                    >
                      <td className="px-4 py-3">
                        <button
                          type="button"
                          onClick={() => setQuickViewCamera(cam)}
                          className="font-medium text-blue-600 hover:underline dark:text-blue-400 text-left flex items-center gap-1.5"
                          title="Open live stream immediately"
                        >
                          <Video className="h-3.5 w-3.5 shrink-0" />
                          {cam.name}
                        </button>
                      </td>
                      <td className="px-4 py-3 text-slate-600 dark:text-slate-400">
                        <div className="flex items-center gap-1">
                          <MapPin className="h-3 w-3" />
                          {loc}
                        </div>
                      </td>
                      <td className="px-4 py-3">{statusBadge(status)}</td>
                      <td className="px-4 py-3">{protocolBadge(cam.protocol)}</td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <Button
                            variant="outline"
                            size="sm"
                            className="h-8 gap-1 text-xs font-semibold text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-950/40"
                            title="Open Live Stream Immediately"
                            onClick={() => setQuickViewCamera(cam)}
                          >
                            <Play className="h-3 w-3 fill-current" />
                            Live Feed
                          </Button>
                          <Link href={`/dashboard/cameras/${cam.id}`}>
                            <Button variant="ghost" size="sm" title="Configure Camera">
                              <Settings className="h-4 w-4" />
                            </Button>
                          </Link>
                          <Button
                            variant="ghost"
                            size="sm"
                            title="Delete Camera"
                            onClick={() => handleDeleteCamera(cam.id, cam.name)}
                            className="text-red-400 hover:text-red-300 hover:bg-red-500/10"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {/* Add Camera Dialog */}
      {showAddDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <Card className="w-full max-w-lg mx-4">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>Add Camera</CardTitle>
              <button
                onClick={() => {
                  setShowAddDialog(false);
                  reset();
                }}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="h-5 w-5" />
              </button>
            </CardHeader>
            <form onSubmit={handleSubmit((data) => addCameraMutation.mutate(data))}>
              <CardContent className="space-y-4">
                {addCameraMutation.isError && (
                  <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/30 dark:text-red-400">
                    {(addCameraMutation.error as any)?.response?.data?.detail || 'Failed to add camera'}
                  </div>
                )}

                <div className="space-y-2">
                  <Label htmlFor="cam-name">Camera Name</Label>
                  <Input id="cam-name" placeholder="Front Entrance" {...register('name')} />
                  {errors.name && <p className="text-xs text-red-500">{errors.name.message}</p>}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="cam-location">Location</Label>
                  <Input id="cam-location" placeholder="Building A, Floor 1" {...register('location')} />
                  {errors.location && <p className="text-xs text-red-500">{errors.location.message}</p>}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="cam-url">Stream URL</Label>
                  <Input id="cam-url" placeholder="rtsp://192.168.1.100:554/stream" {...register('stream_url')} />
                  {errors.stream_url && <p className="text-xs text-red-500">{errors.stream_url.message}</p>}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="cam-protocol">Protocol</Label>
                  <select
                    id="cam-protocol"
                    {...register('protocol')}
                    className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                  >
                    <option value="rtsp">RTSP</option>
                    <option value="rtmp">RTMP</option>
                    <option value="hls">HLS</option>
                    <option value="webrtc">WebRTC</option>
                  </select>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="cam-user">Username (optional)</Label>
                    <Input id="cam-user" placeholder="admin" {...register('username')} />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="cam-pass">Password (optional)</Label>
                    <Input id="cam-pass" type="password" placeholder="********" {...register('password')} />
                  </div>
                </div>

                <div className="flex justify-end gap-2 pt-2">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => {
                      setShowAddDialog(false);
                      reset();
                    }}
                  >
                    Cancel
                  </Button>
                  <Button type="submit" disabled={addCameraMutation.isPending}>
                    {addCameraMutation.isPending ? (
                      <>
                        <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                        Adding...
                      </>
                    ) : (
                      <>
                        <Plus className="mr-1 h-4 w-4" />
                        Add Camera
                      </>
                    )}
                  </Button>
                </div>
              </CardContent>
            </form>
          </Card>
        </div>
      )}
      {/* Instant Camera Live Feed Modal */}
      <Dialog open={!!quickViewCamera} onOpenChange={(open) => !open && setQuickViewCamera(null)}>
        <DialogContent className="max-w-4xl p-0 overflow-hidden bg-slate-950 border-slate-800 text-white sm:rounded-2xl shadow-2xl">
          {quickViewCamera && (
            <div className="flex flex-col">
              <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-800 bg-slate-900/90">
                <div className="flex items-center gap-3">
                  <div
                    className={`h-3 w-3 rounded-full ${
                      (quickViewCamera.status === 'online' || quickViewCamera.is_online)
                        ? 'bg-green-500 animate-pulse'
                        : 'bg-red-500'
                    }`}
                  />
                  <div>
                    <h3 className="text-base font-semibold text-white flex items-center gap-2">
                      {quickViewCamera.name}
                      <Badge className="bg-blue-600/20 text-blue-400 border border-blue-500/30 text-[10px] font-mono uppercase">
                        {quickViewCamera.protocol.toUpperCase()} · Live Feed
                      </Badge>
                    </h3>
                    <p className="text-xs text-slate-400 flex items-center gap-1 mt-0.5">
                      <MapPin className="h-3 w-3" />
                      {quickViewCamera.location || quickViewCamera.location_description || 'Unassigned'}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 pr-6">
                  <Link
                    href={`/dashboard/cameras/${quickViewCamera.id}`}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-500 transition-colors shadow-sm"
                  >
                    <Settings className="h-3.5 w-3.5" />
                    Configure & AI Rules
                  </Link>
                </div>
              </div>

              <div className="relative aspect-video w-full bg-black">
                <StreamPlayer
                  url={getMjpegUrl(quickViewCamera.id, accessToken)}
                  title={quickViewCamera.name}
                  status={quickViewCamera.status || (quickViewCamera.is_online ? 'online' : 'offline')}
                  autoPlay={true}
                  className="h-full w-full object-contain"
                />
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
