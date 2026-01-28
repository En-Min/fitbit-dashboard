import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import DateRangePicker from "./DateRangePicker";

describe("DateRangePicker", () => {
  const defaultProps = {
    startDate: "2024-06-01",
    endDate: "2024-06-30",
    onChange: vi.fn(),
  };

  it("renders start and end date inputs with correct values", () => {
    render(<DateRangePicker {...defaultProps} />);
    const inputs = screen.getAllByDisplayValue(/2024-06/);
    expect(inputs).toHaveLength(2);
  });

  it("renders preset buttons", () => {
    render(<DateRangePicker {...defaultProps} />);
    expect(screen.getByText("Today")).toBeInTheDocument();
    expect(screen.getByText("7d")).toBeInTheDocument();
    expect(screen.getByText("30d")).toBeInTheDocument();
    expect(screen.getByText("90d")).toBeInTheDocument();
    expect(screen.getByText("1y")).toBeInTheDocument();
  });

  it("calls onChange when start date input changes", () => {
    const onChange = vi.fn();
    render(<DateRangePicker {...defaultProps} onChange={onChange} />);
    const startInput = screen.getByDisplayValue("2024-06-01");
    fireEvent.change(startInput, { target: { value: "2024-05-15" } });
    expect(onChange).toHaveBeenCalledWith("2024-05-15", "2024-06-30");
  });

  it("calls onChange when end date input changes", () => {
    const onChange = vi.fn();
    render(<DateRangePicker {...defaultProps} onChange={onChange} />);
    const endInput = screen.getByDisplayValue("2024-06-30");
    fireEvent.change(endInput, { target: { value: "2024-07-15" } });
    expect(onChange).toHaveBeenCalledWith("2024-06-01", "2024-07-15");
  });

  it("calls onChange with computed dates when a preset is clicked", () => {
    const onChange = vi.fn();
    render(<DateRangePicker {...defaultProps} onChange={onChange} />);
    fireEvent.click(screen.getByText("7d"));
    expect(onChange).toHaveBeenCalled();
    const [start, end] = onChange.mock.calls[0];
    // The end date should be today, start should be 7 days before
    expect(end).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(start).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(new Date(end).getTime() - new Date(start).getTime()).toBe(
      7 * 24 * 60 * 60 * 1000
    );
  });

  it("highlights the active preset button", () => {
    const onChange = vi.fn();
    render(<DateRangePicker {...defaultProps} onChange={onChange} />);
    const btn30d = screen.getByText("30d");
    fireEvent.click(btn30d);
    expect(btn30d.className).toContain("active");
  });

  it("clears active preset when date input changes manually", () => {
    const onChange = vi.fn();
    render(<DateRangePicker {...defaultProps} onChange={onChange} />);

    // Activate a preset first
    fireEvent.click(screen.getByText("7d"));
    const btn7d = screen.getByText("7d");
    expect(btn7d.className).toContain("active");

    // Manually change date — should clear active preset
    const startInput = screen.getByDisplayValue("2024-06-01");
    fireEvent.change(startInput, { target: { value: "2024-05-01" } });

    // The component re-renders with new props but activePreset should be null
    // Since we're testing the callback, the preset button should lose active class
    // after the manual change (activePreset set to null)
    expect(btn7d.className).not.toContain("active");
  });

  it("renders the 'to' separator", () => {
    render(<DateRangePicker {...defaultProps} />);
    expect(screen.getByText("to")).toBeInTheDocument();
  });
});
