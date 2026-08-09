import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

// jsdom has no layout engine, so scroll APIs the UI calls need stubbing.
Element.prototype.scrollIntoView = vi.fn();

afterEach(cleanup);
