// Time helpers for the dashboard. Source timestamps arrive as explicit UTC
// ISO strings; `new Date(...)` parses them in the browser's local timezone, so
// relative labels and clocks always reflect the client's local offset (WIB).

export function isValidIso(value: string | undefined | null): boolean {
  if (!value) return false;
  const timestamp = new Date(value).getTime();
  return !Number.isNaN(timestamp);
}

export function formatRelativeTime(
  isoString: string,
  now: number = Date.now(),
): string {
  const timestamp = new Date(isoString).getTime();
  if (Number.isNaN(timestamp)) return "Baru saja";
  const diffMs = Math.max(0, now - timestamp);
  const seconds = Math.floor(diffMs / 1000);
  if (seconds < 45) return "Baru saja";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} menit lalu`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} jam lalu`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days} hari lalu`;
  return new Date(timestamp).toLocaleDateString("id-ID", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function formatLocalClock(
  isoString: string,
  now: number = Date.now(),
): string {
  const timestamp = new Date(isoString).getTime();
  if (Number.isNaN(timestamp)) return "";
  const date = new Date(timestamp);
  const today = new Date(now);
  const sameDay = date.toDateString() === today.toDateString();
  if (sameDay) {
    return `Baru saja · ${date.toLocaleTimeString("id-ID", {
      hour: "2-digit",
      minute: "2-digit",
    })}`;
  }
  const time = date.toLocaleTimeString("id-ID", {
    hour: "2-digit",
    minute: "2-digit",
  });
  const isYesterday =
    new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime() -
      new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime() ===
    86400000;
  if (isYesterday) return `Kemarin, ${time}`;
  return `${date.toLocaleDateString("id-ID", {
    day: "2-digit",
    month: "short",
  })}, ${time}`;
}
