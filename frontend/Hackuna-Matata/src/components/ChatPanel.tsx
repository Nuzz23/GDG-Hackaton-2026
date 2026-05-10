import { useState } from 'react';

/** Each "friend" is a colored dot + an initial. Mirrors the design mockup
 *  where Paola/Nadia/Gianni show up as P / N / G with green/gray/red status. */
const FRIENDS: { id: string; initial: string; color: string; name: string; status: 'online' | 'idle' | 'busy' }[] = [
  { id: 'p', initial: 'P', color: '#27ae60', name: 'Paola',  status: 'online' },
  { id: 'n', initial: 'N', color: '#95a5a6', name: 'Nadia',  status: 'idle' },
  { id: 'g', initial: 'G', color: '#e74c3c', name: 'Gianni', status: 'busy' },
];

type Msg =
  | { from: 'friend'; friendId: string; text: string }
  | { from: 'me'; text: string };

const SEED_MESSAGES: Msg[] = [
  { from: 'friend', friendId: 'p', text: 'Hai già finito i ripassi sul capitolo 1?' },
  { from: 'friend', friendId: 'n', text: 'Stavo guardando il sotto capitolo, non capisco il passaggio centrale 🤔' },
  { from: 'friend', friendId: 'g', text: 'Aspetta che ti scrivo, il prof aveva fatto un esempio diverso.' },
];

/**
 * Mock chat — entirely cosmetic, no backend. Pre-canned starter messages
 * from the three "friends" + an input that lets the user push their own
 * messages onto the list (rendered on the right with a blue WhatsApp-style
 * bubble). The header has a collapse chevron, an Invite button and the
 * status-dot row from the mockup.
 */
export function ChatPanel() {
  const [open, setOpen] = useState(true);
  const [draft, setDraft] = useState('');
  const [messages, setMessages] = useState<Msg[]>(SEED_MESSAGES);

  const sendMessage = () => {
    const text = draft.trim();
    if (!text) return;
    setMessages((prev) => [...prev, { from: 'me', text }]);
    setDraft('');
  };

  return (
    <div style={{
      background: 'white', border: '1px solid #e6e8eb', borderRadius: 10,
      display: 'flex', flexDirection: 'column', minHeight: 0,
      // When collapsed we let the panel auto-shrink to header height; when
      // open we let it claim its share of the column via flex:1.
      flex: open ? 1 : '0 0 auto',
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '8px 10px', borderBottom: open ? '1px solid #eef0f2' : 'none',
      }}>
        <button
          onClick={() => setOpen(o => !o)}
          aria-label={open ? 'Collapse chat' : 'Expand chat'}
          style={{
            display: 'flex', alignItems: 'center', gap: 4,
            background: '#f5f7f9', border: '1px solid #d8dde2',
            borderRadius: 6, padding: '4px 8px',
            cursor: 'pointer', fontSize: 12, fontWeight: 600, color: '#234',
          }}
        >
          <span style={{ fontSize: 10 }}>{open ? '∧' : '∨'}</span> Chat
        </button>
        <button style={{
          background: 'white', border: '1px solid #d8dde2', borderRadius: 6,
          padding: '4px 10px', cursor: 'pointer', fontSize: 12, fontWeight: 600,
          color: '#234',
        }}>
          Invite
        </button>
        {/* Status dots — purely decorative. */}
        <div style={{ display: 'flex', gap: 3, marginLeft: 'auto' }}>
          {FRIENDS.map(f => (
            <span
              key={f.id}
              title={`${f.name} (${f.status})`}
              style={{
                width: 12, height: 12, borderRadius: '50%', background: f.color,
                border: '2px solid white', boxShadow: '0 0 0 1px #d8dde2',
                marginLeft: -4,
              }}
            />
          ))}
        </div>
      </div>

      {/* Body — only when open */}
      {open && (
        <>
          <div style={{
            flex: 1, minHeight: 0, overflowY: 'auto',
            padding: 10, display: 'flex', flexDirection: 'column', gap: 8,
            background: '#fbfcfd',
          }}>
            {messages.map((m, i) => {
              if (m.from === 'me') {
                return <MyBubble key={i} text={m.text} />;
              }
              const friend = FRIENDS.find((f) => f.id === m.friendId) ?? FRIENDS[0];
              return <Bubble key={i} friend={friend} text={m.text} />;
            })}
          </div>

          {/* Input */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '8px 10px', borderTop: '1px solid #eef0f2',
            background: 'white',
          }}>
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); sendMessage(); } }}
              placeholder="Scrivi un messaggio"
              style={{
                flex: 1, border: 'none', outline: 'none', fontSize: 13,
                background: 'transparent',
              }}
            />
            <button
              onClick={sendMessage}
              disabled={!draft.trim()}
              style={{
                background: draft.trim() ? '#3498db' : '#cfd5db',
                color: 'white', border: 'none', borderRadius: 6,
                padding: '4px 10px', fontSize: 12, fontWeight: 600,
                cursor: draft.trim() ? 'pointer' : 'not-allowed',
              }}
            >
              Send
            </button>
          </div>
        </>
      )}
    </div>
  );
}

// ─── Sub-components ────────────────────────────────────────────────────────

function FriendDot({
  friend, size = 26,
}: {
  friend: { initial: string; color: string };
  size?: number;
}) {
  return (
    <span style={{
      width: size, height: size, borderRadius: '50%',
      background: friend.color, color: 'white',
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      fontWeight: 700, fontSize: Math.round(size * 0.45),
      flexShrink: 0,
    }}>
      {friend.initial}
    </span>
  );
}

function Bubble({
  friend, text,
}: {
  friend: typeof FRIENDS[number];
  text: string;
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6 }}>
      <FriendDot friend={friend} />
      <div style={{
        background: tint(friend.color), color: '#234',
        padding: '6px 10px', borderRadius: 8, fontSize: 12,
        lineHeight: 1.35, maxWidth: '78%',
      }}>
        {text}
      </div>
    </div>
  );
}

/** My own message — right-aligned, blue WhatsApp-style bubble. */
function MyBubble({ text }: { text: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
      <div style={{
        background: '#3498db', color: 'white',
        padding: '6px 10px', borderRadius: 8, fontSize: 12,
        lineHeight: 1.35, maxWidth: '78%',
        // Squared-off corner toward the bottom-right, like WhatsApp's "tail" side.
        borderBottomRightRadius: 2,
      }}>
        {text}
      </div>
    </div>
  );
}

/** Soft pastel of the friend color so chat bubbles stay legible. */
function tint(hex: string): string {
  // Naive 30% → 70% mix with white for a pastel feel.
  const m = hex.match(/^#([0-9a-f]{6})$/i);
  if (!m) return hex;
  const v = parseInt(m[1], 16);
  const r = (v >> 16) & 0xff, g = (v >> 8) & 0xff, b = v & 0xff;
  const mix = (c: number) => Math.round(c * 0.3 + 255 * 0.7);
  return `rgb(${mix(r)}, ${mix(g)}, ${mix(b)})`;
}
