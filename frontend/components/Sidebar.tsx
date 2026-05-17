import type { ConversationListItem } from "@/lib/types";
import styles from "./Sidebar.module.css";

interface SidebarProps {
  conversations: ConversationListItem[];
  activeId: string | null;
  isLoading: boolean;
  isOpen: boolean;
  onToggle: () => void;
  onSelect: (id: string) => void;
  onNew: () => void;
}

// ── Icons ─────────────────────────────────────────────────────────

function ComposeIcon() {
  return (
    <svg
      width="15"
      height="15"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {/* Document outline */}
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      {/* Pencil */}
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
    </svg>
  );
}

function SidebarPanelIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {/* Outer window rectangle */}
      <rect x="3" y="3" width="18" height="18" rx="2" />
      {/* Vertical divider — the sidebar column */}
      <path d="M9 3v18" />
    </svg>
  );
}

// ── Time grouping ─────────────────────────────────────────────────

const GROUP_ORDER = ["Hoy", "Ayer", "Últimos 7 días", "Últimos 30 días", "Anterior"];

function timeGroup(iso: string): string {
  const diffDays = Math.floor(
    (Date.now() - new Date(iso).getTime()) / 86_400_000,
  );
  if (diffDays < 1)  return "Hoy";
  if (diffDays < 2)  return "Ayer";
  if (diffDays < 7)  return "Últimos 7 días";
  if (diffDays < 30) return "Últimos 30 días";
  return "Anterior";
}

function groupConversations(
  conversations: ConversationListItem[],
): { label: string; items: ConversationListItem[] }[] {
  const map = new Map<string, ConversationListItem[]>();
  for (const conv of conversations) {
    const label = timeGroup(conv.updated_at);
    if (!map.has(label)) map.set(label, []);
    map.get(label)!.push(conv);
  }
  return GROUP_ORDER
    .filter((label) => map.has(label))
    .map((label) => ({ label, items: map.get(label)! }));
}

// ── Component ─────────────────────────────────────────────────────

export function Sidebar({
  conversations,
  activeId,
  isLoading,
  isOpen,
  onToggle,
  onSelect,
  onNew,
}: SidebarProps) {
  const groups = groupConversations(conversations);

  return (
    <aside className={styles.sidebar}>

      {/* ── Top bar ── */}
      <div className={isOpen ? styles.topBar : styles.topBarCollapsed}>
        {isOpen && <span className={styles.title}>Conversaciones</span>}
        <button
          className={styles.toggleBtn}
          type="button"
          onClick={onToggle}
          aria-label={isOpen ? "Colapsar panel" : "Expandir panel"}
        >
          <SidebarPanelIcon />
        </button>
      </div>

      {/* ── New conversation button ── */}
      {isOpen ? (
        <div className={styles.newBtnWrap}>
          <button className={styles.newBtn} type="button" onClick={onNew}>
            <ComposeIcon />
            Nueva conversación
          </button>
        </div>
      ) : (
        <div className={styles.collapsedNewWrap}>
          <button
            className={styles.collapsedNewBtn}
            type="button"
            onClick={onNew}
            aria-label="Nueva conversación"
          >
            <ComposeIcon />
          </button>
        </div>
      )}

      {/* ── Conversation list ── */}
      {isOpen && (
        <div className={styles.list}>

          {isLoading && conversations.length === 0 && (
            <div className={styles.skeletonList}>
              {[68, 80, 55, 72, 60].map((w, i) => (
                <div key={i} className={styles.skeletonItem}>
                  <div className={styles.skeletonLine} style={{ width: `${w}%` }} />
                  <div className={styles.skeletonLine} style={{ width: "30%" }} />
                </div>
              ))}
            </div>
          )}

          {!isLoading && conversations.length === 0 && (
            <p className={styles.empty}>
              Sin conversaciones aún.
              <br />
              Empieza una nueva arriba.
            </p>
          )}

          {groups.map(({ label, items }) => (
            <div key={label} className={styles.group}>
              <p className={styles.groupLabel}>{label}</p>
              {items.map((conv) => {
                const isActive = conv.id === activeId;
                return (
                  <button
                    key={conv.id}
                    className={isActive ? `${styles.item} ${styles.itemActive}` : styles.item}
                    type="button"
                    onClick={() => onSelect(conv.id)}
                    aria-current={isActive ? "page" : undefined}
                  >
                    <span className={styles.itemTitle}>{conv.title}</span>
                    <span className={styles.itemMeta}>{conv.message_count} msg</span>
                  </button>
                );
              })}
            </div>
          ))}

        </div>
      )}

    </aside>
  );
}
