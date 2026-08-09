"use client";

import { useEffect, useRef, useState } from "react";
import { Panel } from "./Panel";
import { fetchChatHistory, sendChat } from "@/lib/api";
import type { ChatMessage } from "@/lib/types";

type Props = {
  onCollapse: () => void;
  onActions: () => Promise<void>;
};

const GREETING: ChatMessage = {
  id: "greeting",
  role: "assistant",
  content:
    "I am Ally. Ask me about your positions, or tell me what to trade and I will place the order.",
};

export function Chat({ onCollapse, onActions }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([GREETING]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  // Messages are persisted server side, so a reload resumes the conversation.
  useEffect(() => {
    fetchChatHistory()
      .then((history) => {
        if (history.length === 0) return;
        // Keep anything the user sent while the history was still in flight.
        setMessages((prev) => (prev.length > 1 ? prev : [GREETING, ...history]));
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages, busy]);

  async function send(event: React.FormEvent) {
    event.preventDefault();
    const text = draft.trim();
    if (!text || busy) return;

    setMessages((prev) => [
      ...prev,
      { id: `u-${prev.length}`, role: "user", content: text },
    ]);
    setDraft("");
    setBusy(true);

    try {
      const reply = await sendChat(text);
      setMessages((prev) => [
        ...prev,
        {
          id: `a-${prev.length}`,
          role: "assistant",
          content: reply.message,
          actions: reply.actions,
        },
      ]);
      if (reply.actions.length > 0) await onActions();
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: `e-${prev.length}`,
          role: "assistant",
          content:
            err instanceof Error ? err.message : "The assistant is unreachable.",
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel
      title="Ally"
      testId="chat-panel"
      stat={
        <button
          type="button"
          data-testid="chat-collapse"
          onClick={onCollapse}
          className="px-1 text-muted hover:text-accent"
          aria-label="Collapse assistant"
        >
          &raquo;
        </button>
      }
    >
      <div
        data-testid="chat-messages"
        className="scroll-thin min-h-0 flex-1 space-y-3 overflow-y-auto p-3"
      >
        {messages.map((message) => (
          <div key={message.id} data-testid={`chat-message-${message.role}`}>
            <span
              className={`text-[0.5625rem] tracking-[0.18em] ${
                message.role === "user" ? "text-blue" : "text-accent"
              }`}
            >
              {message.role === "user" ? "YOU" : "ALLY"}
            </span>
            <p className="font-sans text-[0.8125rem] leading-relaxed text-ink">
              {message.content}
            </p>
            {message.actions?.length ? (
              <ul className="mt-1.5 space-y-1">
                {message.actions.map((action, index) => (
                  <li
                    key={index}
                    data-testid="chat-action"
                    className={`border-l-2 bg-panel-hi px-2 py-1 text-[0.6875rem] ${
                      action.ok
                        ? "border-up text-muted"
                        : "border-down text-down"
                    }`}
                  >
                    {action.label}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ))}
        {busy ? (
          <p
            data-testid="chat-loading"
            className="text-[0.6875rem] tracking-[0.18em] text-dim"
          >
            ALLY IS THINKING
          </p>
        ) : null}
        <div ref={endRef} />
      </div>

      <form onSubmit={send} className="flex flex-none border-t border-rule">
        <input
          data-testid="chat-input"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Ask about the book, or place an order"
          aria-label="Message the assistant"
          className="min-w-0 flex-1 bg-transparent px-3 py-2.5 font-sans text-[0.8125rem] placeholder:text-dim focus:outline-none"
        />
        <button
          type="submit"
          data-testid="chat-send"
          disabled={busy}
          className="m-1.5 rounded-xs bg-purple px-3 text-[0.6875rem] tracking-[0.16em] text-ink hover:brightness-125 disabled:opacity-50"
        >
          SEND
        </button>
      </form>
    </Panel>
  );
}
