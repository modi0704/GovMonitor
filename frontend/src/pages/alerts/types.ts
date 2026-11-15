export interface NotificationItem {
  id: string;
  type: string;
  title: string;
  body: string;
  link: string;
  created_at: string;
  read_at: string | null;
}

export interface NotificationList {
  results: NotificationItem[];
  unread: number;
}

export const UNREAD_POLL_MS = 60_000;
