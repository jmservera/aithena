import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { IntlWrapper } from "./test-intl-wrapper";
import BackupDashboardPage from "../pages/BackupDashboardPage";
import {
  tierHealthColor,
  formatBytes,
  formatDuration,
} from "../hooks/backups";
import type { TierStatus } from "../hooks/backups";

/* ---- mock data ---- */

const mockTiers: TierStatus[] = [
  {
    tier: "critical",
    last_backup: "2025-01-15T10:00:00Z",
    age_hours: 2,
    rpo_hours: 4,
    size: 1048576,
    status: "completed",
  },
  {
    tier: "high",
    last_backup: "2025-01-14T08:00:00Z",
    age_hours: 20,
    rpo_hours: 12,
    size: 5242880,
    status: "completed",
  },
  {
    tier: "medium",
    last_backup: null,
    age_hours: 0,
    rpo_hours: 24,
    size: 0,
    status: "pending",
  },
];

const mockBackups = [
  {
    id: "b-1",
    timestamp: "2025-01-15T10:00:00Z",
    tier: "critical",
    status: "completed",
    size: 1048576,
    components: [
      { name: "solr", size: 800000, status: "completed" },
      { name: "redis", size: 248576, status: "completed" },
    ],
    duration_seconds: 45,
  },
  {
    id: "b-2",
    timestamp: "2025-01-14T08:00:00Z",
    tier: "high",
    status: "failed",
    size: 0,
    components: [],
    error: "Disk full",
  },
];

function createMockFetch() {
  return vi.fn().mockImplementation((url: string) => {
    if (typeof url === "string" && url.includes("/v1/admin/backups/status")) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ tiers: mockTiers }),
      });
    }
    if (typeof url === "string" && url.includes("/v1/admin/backups")) {
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({ backups: mockBackups, total: mockBackups.length }),
      });
    }
    if (typeof url === "string" && url.includes("/v1/admin/restore/test")) {
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            status: "completed",
            message: "Test OK",
            components_restored: ["solr"],
            duration_seconds: 10,
          }),
      });
    }
    if (typeof url === "string" && url.includes("/v1/admin/restore")) {
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            status: "completed",
            message: "Restore OK",
            components_restored: ["solr", "redis"],
            duration_seconds: 30,
          }),
      });
    }
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve({}),
    });
  });
}

function renderPage() {
  return render(
    <MemoryRouter>
      <IntlWrapper>
        <BackupDashboardPage />
      </IntlWrapper>
    </MemoryRouter>,
  );
}

/* ---- component tests ---- */

describe("BackupDashboardPage", () => {
  let mockFetch: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    mockFetch = createMockFetch();
    vi.stubGlobal("fetch", mockFetch);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows loading state initially", () => {
    renderPage();
    expect(screen.getByText(/Loading backup data/)).toBeInTheDocument();
  });

  it("renders tier status cards after loading", async () => {
    renderPage();
    await waitFor(() => {
      expect(
        screen.getByText("Critical", { selector: "h4" }),
      ).toBeInTheDocument();
    });
    expect(screen.getByText("High", { selector: "h4" })).toBeInTheDocument();
    expect(
      screen.getByText("Medium", { selector: "h4" }),
    ).toBeInTheDocument();
  });

  it("renders backup history table", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("2025-01-15T10:00:00Z")).toBeInTheDocument();
    });
    expect(screen.getByText("2025-01-14T08:00:00Z")).toBeInTheDocument();
  });

  it("shows Restore button only for completed backups", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("2025-01-15T10:00:00Z")).toBeInTheDocument();
    });
    const restoreButtons = screen.getAllByText("Restore");
    expect(restoreButtons).toHaveLength(1);
  });

  it("shows Backup Now section with tier selector", async () => {
    renderPage();
    await waitFor(() => {
      expect(
        screen.getByText("Backup Now", { selector: "h3" }),
      ).toBeInTheDocument();
    });
    expect(screen.getByLabelText("Select tier:")).toBeInTheDocument();
  });

  it("displays error message on fetch failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("Network error")),
    );
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });
  });

  it("can sort backup history by clicking column header", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("2025-01-15T10:00:00Z")).toBeInTheDocument();
    });
    const tierHeader = screen.getByText(/^Tier/);
    await user.click(tierHeader);
    expect(tierHeader.textContent).toContain("\u25BC");
  });

  it("opens restore wizard when Restore button is clicked", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("2025-01-15T10:00:00Z")).toBeInTheDocument();
    });
    const restoreBtn = screen.getByText("Restore");
    await user.click(restoreBtn);
    expect(screen.getByText("Restore Wizard")).toBeInTheDocument();
  });

  it("shows backup details in restore wizard select step", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("2025-01-15T10:00:00Z")).toBeInTheDocument();
    });
    await user.click(screen.getByText("Restore"));
    expect(
      screen.getByText(
        "You are about to restore from the following backup:",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("b-1")).toBeInTheDocument();
  });

  it("can navigate through restore wizard steps", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("2025-01-15T10:00:00Z")).toBeInTheDocument();
    });
    await user.click(screen.getByText("Restore"));
    await user.click(screen.getByText("Next"));
    expect(
      screen.getByText("The following components will be restored:"),
    ).toBeInTheDocument();
    await user.click(screen.getByText("Next"));
    expect(
      screen.getByText(
        "This will overwrite current data with the backup contents.",
      ),
    ).toBeInTheDocument();
  });

  it("can go back in restore wizard", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("2025-01-15T10:00:00Z")).toBeInTheDocument();
    });
    await user.click(screen.getByText("Restore"));
    await user.click(screen.getByText("Next"));
    expect(
      screen.getByText("The following components will be restored:"),
    ).toBeInTheDocument();
    await user.click(screen.getByText("Back"));
    expect(
      screen.getByText(
        "You are about to restore from the following backup:",
      ),
    ).toBeInTheDocument();
  });

  it("can trigger restore and shows result", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("2025-01-15T10:00:00Z")).toBeInTheDocument();
    });
    await user.click(screen.getByText("Restore"));
    await user.click(screen.getByText("Next"));
    await user.click(screen.getByText("Next"));
    await user.click(screen.getByText("Restore Now"));
    await waitFor(() => {
      expect(screen.getByText("Restore OK")).toBeInTheDocument();
    });
    expect(screen.getByText("2 component(s) restored")).toBeInTheDocument();
  });

  it("can trigger test restore", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("2025-01-15T10:00:00Z")).toBeInTheDocument();
    });
    await user.click(screen.getByText("Restore"));
    await user.click(screen.getByText("Next"));
    await user.click(screen.getByText("Next"));
    await user.click(screen.getByText("Test Restore"));
    await waitFor(() => {
      expect(screen.getByText("Test OK")).toBeInTheDocument();
    });
  });

  it("can close restore wizard with Cancel", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("2025-01-15T10:00:00Z")).toBeInTheDocument();
    });
    await user.click(screen.getByText("Restore"));
    expect(screen.getByText("Restore Wizard")).toBeInTheDocument();
    await user.click(screen.getByText("Cancel"));
    expect(screen.queryByText("Restore Wizard")).not.toBeInTheDocument();
  });

  it("shows refresh button", async () => {
    renderPage();
    await waitFor(() => {
      expect(
        screen.getByText("Critical", { selector: "h4" }),
      ).toBeInTheDocument();
    });
    expect(screen.getByText(/Refresh/)).toBeInTheDocument();
  });
});

/* ---- utility function tests ---- */

describe("tierHealthColor", () => {
  it("returns green when within RPO", () => {
    const tier: TierStatus = {
      tier: "critical",
      last_backup: "2025-01-15",
      age_hours: 2,
      rpo_hours: 4,
      size: 100,
      status: "completed",
    };
    expect(tierHealthColor(tier)).toBe("green");
  });

  it("returns yellow when nearing RPO", () => {
    const tier: TierStatus = {
      tier: "high",
      last_backup: "2025-01-15",
      age_hours: 10,
      rpo_hours: 12,
      size: 100,
      status: "completed",
    };
    expect(tierHealthColor(tier)).toBe("yellow");
  });

  it("returns red when past RPO", () => {
    const tier: TierStatus = {
      tier: "high",
      last_backup: "2025-01-15",
      age_hours: 25,
      rpo_hours: 12,
      size: 100,
      status: "completed",
    };
    expect(tierHealthColor(tier)).toBe("red");
  });

  it("returns red for failed status", () => {
    const tier: TierStatus = {
      tier: "medium",
      last_backup: "2025-01-15",
      age_hours: 1,
      rpo_hours: 24,
      size: 100,
      status: "failed",
    };
    expect(tierHealthColor(tier)).toBe("red");
  });
});

describe("formatBytes", () => {
  it("formats zero bytes", () => {
    expect(formatBytes(0)).toBe("0 B");
  });
  it("formats megabytes", () => {
    expect(formatBytes(1048576)).toBe("1.0 MB");
  });
});

describe("formatDuration", () => {
  it("formats seconds only", () => {
    expect(formatDuration(45)).toBe("45s");
  });
  it("formats minutes and seconds", () => {
    expect(formatDuration(125)).toBe("2m 5s");
  });
  it("formats exact minutes", () => {
    expect(formatDuration(120)).toBe("2m");
  });
});
