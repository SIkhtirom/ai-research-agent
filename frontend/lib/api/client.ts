// Backend API base URL. Precedence:
//   1. NEXT_PUBLIC_API_URL      e.g. "https://your-tunnel.ngrok.io" (origin only)
//   2. NEXT_PUBLIC_API_BASE_URL (legacy) e.g. "https://your-tunnel.ngrok.io/api/v1"
//   3. Local dev fallback - never relied on when a public tunnel is active.
// The env values are inlined by Next.js at start time; expose.sh injects the
// tunnel URL so remote testers hit the backend that is actually reachable.
const API_ORIGIN = (
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "http://127.0.0.1:8000"
)
  .trim()
  .replace(/\/+$/, "");
const API_BASE_URL = API_ORIGIN.endsWith("/api/v1")
  ? API_ORIGIN
  : `${API_ORIGIN}/api/v1`;

if (!process.env.NEXT_PUBLIC_API_URL && !process.env.NEXT_PUBLIC_API_BASE_URL) {
  console.warn(
    `[api] NEXT_PUBLIC_API_URL not set - defaulting to local dev API: ${API_BASE_URL}`,
  );
}

class ApiError extends Error {
  constructor(
    public readonly statusCode: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!response.ok) {
    const errorPayload = await response.json().catch(() => null);
    const message = errorPayload?.detail ?? `Request failed with status ${response.status}`;
    throw new ApiError(response.status, message);
  }

  return (await response.json()) as T;
}

export function get<T>(path: string): Promise<T> {
  return request<T>(path, { method: "GET" });
}

export function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function del<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { method: "DELETE" });
  if (!response.ok) {
    const errorPayload = await response.json().catch(() => null);
    const message = errorPayload?.detail ?? `Request failed with status ${response.status}`;
    throw new ApiError(response.status, message);
  }
  return (await response.json()) as T;
}

export async function uploadFilesWithProgress<T>(
  path: string,
  files: File[],
  sessionId: number | undefined,
  onProgress: (percent: number) => void,
): Promise<T> {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  const query = sessionId !== undefined ? `?session_id=${sessionId}` : "";

  return new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE_URL}${path}${query}`);

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        const percent = Math.round((event.loaded / event.total) * 100);
        onProgress(Math.min(percent, 99));
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as T);
        } catch {
          reject(new ApiError(xhr.status, "Response tidak valid dari server."));
        }
      } else {
        let message = `Request failed with status ${xhr.status}`;
        try {
          const payload = JSON.parse(xhr.responseText);
          if (payload?.detail) message = payload.detail;
        } catch {
          // keep the fallback message
        }
        reject(new ApiError(xhr.status, message));
      }
    };

    xhr.onerror = () => {
      reject(new ApiError(0, "Koneksi gagal. Periksa koneksi internet Anda lalu coba lagi."));
    };

    xhr.ontimeout = () => {
      reject(new ApiError(0, "Upload melebihi batas waktu. Coba lagi."));
    };
    xhr.timeout = 0;
    xhr.send(formData);
  });
}

export async function downloadFile(
  path: string,
): Promise<{ blob: Blob; filename: string }> {
  const response = await fetch(`${API_BASE_URL}${path}`, { method: "GET" });

  if (!response.ok) {
    const errorPayload = await response.json().catch(() => null);
    const message = errorPayload?.detail ?? `Request failed with status ${response.status}`;
    throw new ApiError(response.status, message);
  }

  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const match = disposition.match(/filename="?([^";]+)"?/);
  const filename = match ? match[1] : "export";
  return { blob, filename };
}

export async function uploadFile<T>(path: string, file: File, sessionId?: number): Promise<T> {
  const formData = new FormData();
  formData.append("file", file);
  const query = sessionId !== undefined ? `?session_id=${sessionId}` : "";
  const response = await fetch(`${API_BASE_URL}${path}${query}`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const errorPayload = await response.json().catch(() => null);
    const message = errorPayload?.detail ?? `Request failed with status ${response.status}`;
    throw new ApiError(response.status, message);
  }

  return (await response.json()) as T;
}

export async function uploadFileWithProgress<T>(
  path: string,
  file: File,
  sessionId: number | undefined,
  onProgress: (percent: number) => void,
): Promise<T> {
  const formData = new FormData();
  formData.append("file", file);
  const query = sessionId !== undefined ? `?session_id=${sessionId}` : "";

  return new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE_URL}${path}${query}`);

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        const percent = Math.round((event.loaded / event.total) * 100);
        onProgress(Math.min(percent, 99));
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as T);
        } catch {
          reject(new ApiError(xhr.status, "Response tidak valid dari server."));
        }
      } else {
        let message = `Request failed with status ${xhr.status}`;
        try {
          const payload = JSON.parse(xhr.responseText);
          if (payload?.detail) message = payload.detail;
        } catch {
          // keep the fallback message
        }
        reject(new ApiError(xhr.status, message));
      }
    };

    xhr.onerror = () => {
      reject(new ApiError(0, "Koneksi gagal. Periksa koneksi internet Anda lalu coba lagi."));
    };

    xhr.ontimeout = () => {
      reject(new ApiError(0, "Upload melebihi batas waktu. Coba lagi."));
    };
    xhr.timeout = 0;
    xhr.send(formData);
  });
}

export const apiClient = {
  get,
  post,
  del,
  uploadFile,
  uploadFileWithProgress,
  uploadFilesWithProgress,
  downloadFile,
};
