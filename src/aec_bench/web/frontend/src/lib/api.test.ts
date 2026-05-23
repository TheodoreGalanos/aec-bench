// ABOUTME: Unit tests for the typed API client in api.ts.
// ABOUTME: Mocks global.fetch to verify URL construction and error handling.

import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  ApiError,
  fetchDashboard,
  fetchTriage,
  fetchViewerMeta,
  fetchViewerStep,
  fetchViewerState,
  fetchLeaderboard,
  fetchDatasetsList,
  fetchDatasetDetail,
  fetchLibraryList,
  fetchLibraryDetail,
  fetchSearch,
  fetchReviewQueue,
  fetchReviewTrial,
  submitAnnotation,
} from "./api";

// ---------------------------------------------------------------------------
// Fetch mock helpers
// ---------------------------------------------------------------------------

const mockFetch = vi.fn();
global.fetch = mockFetch;

function mockJsonResponse(data: any, status = 200) {
  mockFetch.mockResolvedValueOnce({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)),
  });
}

beforeEach(() => {
  mockFetch.mockReset();
});

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------

describe("fetchDashboard", () => {
  it("calls /api/dashboard? with no params", async () => {
    const payload = { experiments: [], total_trials: 0, total_experiments: 0, mean_reward: 0, annotated_count: 0 };
    mockJsonResponse(payload);
    const result = await fetchDashboard();
    expect(mockFetch).toHaveBeenCalledWith("/api/dashboard");
    expect(result).toEqual(payload);
  });

  it("includes sort param in the URL", async () => {
    mockJsonResponse({});
    await fetchDashboard({ sort: "name_asc" });
    expect(mockFetch).toHaveBeenCalledWith("/api/dashboard?sort=name_asc");
  });
});

// ---------------------------------------------------------------------------
// Triage
// ---------------------------------------------------------------------------

describe("fetchTriage", () => {
  it("calls /api/triage with no params", async () => {
    mockJsonResponse({ trials: [], trial_count: 0, annotations: {}, filters: {}, experiments: [], models: [] });
    await fetchTriage();
    expect(mockFetch).toHaveBeenCalledWith("/api/triage");
  });

  it("includes experiment filter param", async () => {
    mockJsonResponse({});
    await fetchTriage({ experiment: "exp-01" });
    expect(mockFetch).toHaveBeenCalledWith("/api/triage?experiment=exp-01");
  });

  it("omits undefined params from query string", async () => {
    mockJsonResponse({});
    await fetchTriage({ experiment: "exp-01", model: undefined });
    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain("experiment=exp-01");
    expect(url).not.toContain("model");
  });
});

// ---------------------------------------------------------------------------
// Viewer
// ---------------------------------------------------------------------------

describe("fetchViewerMeta", () => {
  it("calls the correct URL", async () => {
    mockJsonResponse({ trial_id: "t-1" });
    await fetchViewerMeta("exp-01", "t-1");
    expect(mockFetch).toHaveBeenCalledWith("/api/viewer/exp-01/t-1");
  });

  it("includes from_page param when provided", async () => {
    mockJsonResponse({});
    await fetchViewerMeta("exp-01", "t-1", { from_page: "triage" });
    expect(mockFetch).toHaveBeenCalledWith("/api/viewer/exp-01/t-1?from_page=triage");
  });
});

describe("fetchViewerStep", () => {
  it("calls the correct URL with step number", async () => {
    mockJsonResponse({ step_num: 0, messages: [] });
    await fetchViewerStep("exp-01", "t-1", 0);
    expect(mockFetch).toHaveBeenCalledWith("/api/viewer/exp-01/t-1/steps/0");
  });
});

describe("fetchViewerState", () => {
  it("calls the correct state URL", async () => {
    mockJsonResponse({ symbolic_state: {}, scratchpad_data: {} });
    await fetchViewerState("exp-01", "t-1");
    expect(mockFetch).toHaveBeenCalledWith("/api/viewer/exp-01/t-1/state");
  });
});

// ---------------------------------------------------------------------------
// ApiError on non-200
// ---------------------------------------------------------------------------

describe("ApiError", () => {
  it("is thrown on a 404 response", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: () => Promise.resolve({ detail: "not found" }),
      text: () => Promise.resolve('{"detail":"not found"}'),
    });
    await expect(fetchDashboard()).rejects.toThrow(ApiError);
  });

  it("includes status and detail on the error", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ detail: "internal error" }),
      text: () => Promise.resolve('{"detail":"internal error"}'),
    });
    try {
      await fetchDashboard();
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      expect((err as ApiError).status).toBe(500);
      expect((err as ApiError).detail).toBe("internal error");
    }
  });

  it("falls back to raw text when JSON parse fails", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 502,
      json: () => Promise.reject(new SyntaxError("bad json")),
      text: () => Promise.resolve("Bad Gateway"),
    });
    try {
      await fetchDashboard();
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      expect((err as ApiError).status).toBe(502);
      expect((err as ApiError).detail).toBe("Bad Gateway");
    }
  });
});

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------

describe("fetchSearch", () => {
  it("includes the query param", async () => {
    mockJsonResponse({
      query: "voltage",
      template_results: [],
      dataset_results: [],
      trial_results: [],
      experiment_results: [],
      workspace_results: [],
      total_results: 0,
    });
    await fetchSearch({ q: "voltage" });
    expect(mockFetch).toHaveBeenCalledWith("/api/search?q=voltage");
  });

  it("calls /api/search with no params", async () => {
    mockJsonResponse({});
    await fetchSearch();
    expect(mockFetch).toHaveBeenCalledWith("/api/search");
  });
});

// ---------------------------------------------------------------------------
// Leaderboard
// ---------------------------------------------------------------------------

describe("fetchLeaderboard", () => {
  it("calls /api/leaderboard with no params", async () => {
    mockJsonResponse({});
    await fetchLeaderboard();
    expect(mockFetch).toHaveBeenCalledWith("/api/leaderboard");
  });

  it("includes dataset param", async () => {
    mockJsonResponse({});
    await fetchLeaderboard({ dataset: "my-dataset" });
    expect(mockFetch).toHaveBeenCalledWith("/api/leaderboard?dataset=my-dataset");
  });
});

// ---------------------------------------------------------------------------
// Datasets
// ---------------------------------------------------------------------------

describe("fetchDatasetsList", () => {
  it("calls /api/datasets", async () => {
    mockJsonResponse({ datasets: [], total_datasets: 0, total_tasks: 0 });
    await fetchDatasetsList();
    expect(mockFetch).toHaveBeenCalledWith("/api/datasets");
  });
});

describe("fetchDatasetDetail", () => {
  it("calls the correct versioned URL", async () => {
    mockJsonResponse({});
    await fetchDatasetDetail("my-ds", "1.0.0");
    expect(mockFetch).toHaveBeenCalledWith("/api/datasets/my-ds/1.0.0");
  });

  it("includes tab param when provided", async () => {
    mockJsonResponse({});
    await fetchDatasetDetail("my-ds", "1.0.0", { tab: "results" });
    expect(mockFetch).toHaveBeenCalledWith("/api/datasets/my-ds/1.0.0?tab=results");
  });
});

// ---------------------------------------------------------------------------
// Library
// ---------------------------------------------------------------------------

describe("fetchLibraryList", () => {
  it("calls /api/library with no params", async () => {
    mockJsonResponse({});
    await fetchLibraryList();
    expect(mockFetch).toHaveBeenCalledWith("/api/library");
  });

  it("includes discipline param", async () => {
    mockJsonResponse({});
    await fetchLibraryList({ discipline: "electrical" });
    expect(mockFetch).toHaveBeenCalledWith("/api/library?discipline=electrical");
  });
});

describe("fetchLibraryDetail", () => {
  it("calls the correct URL", async () => {
    mockJsonResponse({});
    await fetchLibraryDetail("electrical", "voltage-drop");
    expect(mockFetch).toHaveBeenCalledWith("/api/library/electrical/voltage-drop");
  });
});

// ---------------------------------------------------------------------------
// Review
// ---------------------------------------------------------------------------

describe("fetchReviewQueue", () => {
  it("includes reviewer_id param", async () => {
    mockJsonResponse({ assignments: {} });
    await fetchReviewQueue({ reviewer_id: "user-1" });
    expect(mockFetch).toHaveBeenCalledWith("/api/review/queue?reviewer_id=user-1");
  });
});

describe("fetchReviewTrial", () => {
  it("calls the correct URL with reviewer_id", async () => {
    mockJsonResponse({ bundle: {} });
    await fetchReviewTrial("trial-abc", { reviewer_id: "user-1" });
    expect(mockFetch).toHaveBeenCalledWith("/api/review/trial/trial-abc?reviewer_id=user-1");
  });
});

// ---------------------------------------------------------------------------
// submitAnnotation (POST)
// ---------------------------------------------------------------------------

describe("submitAnnotation", () => {
  it("POSTs to /api/triage/annotate with JSON body", async () => {
    const responsePayload = { verdict: "good", notes: "looks fine", timestamp: "2024-01-01T00:00:00Z" };
    mockJsonResponse(responsePayload);
    const result = await submitAnnotation({
      trial_id: "t-1",
      experiment_id: "exp-01",
      verdict: "good",
      notes: "looks fine",
    });
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/triage/annotate",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ trial_id: "t-1", experiment_id: "exp-01", verdict: "good", notes: "looks fine" }),
      }),
    );
    expect(result).toEqual(responsePayload);
  });

  it("throws ApiError on non-200 response", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 422,
      json: () => Promise.resolve({ detail: "validation error" }),
      text: () => Promise.resolve('{"detail":"validation error"}'),
    });
    await expect(
      submitAnnotation({ trial_id: "t-1", experiment_id: "exp-01", verdict: "bad" }),
    ).rejects.toThrow(ApiError);
  });
});
