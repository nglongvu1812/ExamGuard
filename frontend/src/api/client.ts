export interface HealthResponse {
  status: string;
  app_name: string;
  app_version: string;
  db_ok: boolean;
  db_journal_mode: string;
  data_dir_writable: boolean;
  server_time_utc: string;
}

export interface NetworkInterfaceInfo {
  name: string;
  ip: string;
  url: string;
  kind: "wifi" | "ethernet" | "hotspot" | "other";
  recommended: boolean;
}

export interface NetworkStatusResponse {
  port: number;
  selected_url: string;
  qr_svg: string;
  interfaces: NetworkInterfaceInfo[];
  firewall_guide: string[];
  offline_ready: boolean;
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    let detail = `Lỗi máy chủ (${response.status})`;
    try {
      const data = (await response.json()) as { detail?: string };
      if (data.detail) detail = data.detail;
    } catch {
      // ignore json parse failure
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export const systemApi = {
  getHealth(): Promise<HealthResponse> {
    return fetchJson<HealthResponse>("/api/v1/health");
  },
  getNetworkStatus(selectedIp?: string): Promise<NetworkStatusResponse> {
    const query = selectedIp ? `?selected_ip=${encodeURIComponent(selectedIp)}` : "";
    return fetchJson<NetworkStatusResponse>(`/api/v1/system/network${query}`);
  },
};
