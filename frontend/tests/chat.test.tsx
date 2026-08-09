import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Chat } from "@/components/Chat";
import { fetchChatHistory, sendChat } from "@/lib/api";

vi.mock("@/lib/api", () => ({ sendChat: vi.fn(), fetchChatHistory: vi.fn() }));

const mockSend = vi.mocked(sendChat);
const mockHistory = vi.mocked(fetchChatHistory);

describe("Chat", () => {
  // Block body on purpose: a hook that returns a function is a teardown hook,
  // and mockReset returns the mock itself.
  beforeEach(() => {
    mockSend.mockReset();
    mockHistory.mockReset();
    mockHistory.mockResolvedValue([]);
  });

  it("shows the reply and keeps the user message in the transcript", async () => {
    mockSend.mockResolvedValue({ message: "You hold two positions.", actions: [] });
    render(<Chat onCollapse={vi.fn()} onActions={vi.fn()} />);

    await userEvent.type(screen.getByTestId("chat-input"), "How am I doing?");
    await userEvent.click(screen.getByTestId("chat-send"));

    expect(await screen.findByText("You hold two positions.")).toBeInTheDocument();
    expect(screen.getByText("How am I doing?")).toBeInTheDocument();
    expect(screen.getByTestId("chat-input")).toHaveValue("");
  });

  it("shows a loading indicator until the reply lands", async () => {
    let resolve: (value: { message: string; actions: [] }) => void = () => {};
    mockSend.mockReturnValue(
      new Promise((done) => {
        resolve = done;
      }),
    );
    render(<Chat onCollapse={vi.fn()} onActions={vi.fn()} />);

    await userEvent.type(screen.getByTestId("chat-input"), "hello");
    await userEvent.click(screen.getByTestId("chat-send"));
    expect(screen.getByTestId("chat-loading")).toBeInTheDocument();

    resolve({ message: "Hi.", actions: [] });
    await waitFor(() =>
      expect(screen.queryByTestId("chat-loading")).not.toBeInTheDocument(),
    );
  });

  it("lists executed actions inline and refreshes the portfolio", async () => {
    const onActions = vi.fn().mockResolvedValue(undefined);
    mockSend.mockResolvedValue({
      message: "Bought 5 AAPL.",
      actions: [
        { kind: "trade", label: "BUY 5 AAPL", ok: true },
        { kind: "trade", label: "BUY 900 NVDA rejected: insufficient cash", ok: false },
      ],
    });
    render(<Chat onCollapse={vi.fn()} onActions={onActions} />);

    await userEvent.type(screen.getByTestId("chat-input"), "buy 5 aapl");
    await userEvent.click(screen.getByTestId("chat-send"));

    const actions = await screen.findAllByTestId("chat-action");
    expect(actions).toHaveLength(2);
    expect(actions[1]).toHaveTextContent("insufficient cash");
    await waitFor(() => expect(onActions).toHaveBeenCalled());
  });

  it("restores the persisted transcript, with its actions, on load", async () => {
    mockHistory.mockResolvedValue([
      { id: "history-0", role: "user", content: "buy 5 aapl" },
      {
        id: "history-1",
        role: "assistant",
        content: "Bought 5 AAPL.",
        actions: [{ kind: "trade", label: "BUY 5 AAPL", ok: true }],
      },
    ]);
    render(<Chat onCollapse={vi.fn()} onActions={vi.fn()} />);

    expect(await screen.findByText("buy 5 aapl")).toBeInTheDocument();
    expect(screen.getByText("Bought 5 AAPL.")).toBeInTheDocument();
    expect(screen.getByTestId("chat-action")).toHaveTextContent("BUY 5 AAPL");
  });

  it("keeps the greeting when there is nothing to restore", async () => {
    render(<Chat onCollapse={vi.fn()} onActions={vi.fn()} />);
    await waitFor(() => expect(mockHistory).toHaveBeenCalled());
    expect(screen.getAllByTestId("chat-message-assistant")).toHaveLength(1);
  });

  it("surfaces a transport failure as an assistant message", async () => {
    mockSend.mockRejectedValue(new Error("Chat is unavailable"));
    render(<Chat onCollapse={vi.fn()} onActions={vi.fn()} />);

    await userEvent.type(screen.getByTestId("chat-input"), "hello");
    await userEvent.click(screen.getByTestId("chat-send"));

    expect(await screen.findByText("Chat is unavailable")).toBeInTheDocument();
  });
});
