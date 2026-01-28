import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Layout from "./Layout";

describe("Layout", () => {
  const renderLayout = (initialRoute = "/") =>
    render(
      <MemoryRouter initialEntries={[initialRoute]}>
        <Layout />
      </MemoryRouter>
    );

  it("renders the sidebar with app title", () => {
    renderLayout();
    expect(screen.getByText("Fitbit Raw")).toBeInTheDocument();
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
  });

  it("renders all navigation links", () => {
    renderLayout();
    expect(screen.getByText("Overview")).toBeInTheDocument();
    expect(screen.getByText("Heart Rate")).toBeInTheDocument();
    expect(screen.getByText("Sleep")).toBeInTheDocument();
    expect(screen.getByText("Activity")).toBeInTheDocument();
    expect(screen.getByText("Correlations")).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("has links pointing to correct routes", () => {
    renderLayout();
    const overviewLink = screen.getByText("Overview").closest("a");
    expect(overviewLink).toHaveAttribute("href", "/");

    const heartRateLink = screen.getByText("Heart Rate").closest("a");
    expect(heartRateLink).toHaveAttribute("href", "/heart-rate");

    const sleepLink = screen.getByText("Sleep").closest("a");
    expect(sleepLink).toHaveAttribute("href", "/sleep");

    const activityLink = screen.getByText("Activity").closest("a");
    expect(activityLink).toHaveAttribute("href", "/activity");

    const correlationsLink = screen.getByText("Correlations").closest("a");
    expect(correlationsLink).toHaveAttribute("href", "/correlations");

    const settingsLink = screen.getByText("Settings").closest("a");
    expect(settingsLink).toHaveAttribute("href", "/settings");
  });

  it("highlights the active route link", () => {
    renderLayout("/sleep");
    const sleepLink = screen.getByText("Sleep").closest("a");
    expect(sleepLink?.className).toContain("active");
  });
});
