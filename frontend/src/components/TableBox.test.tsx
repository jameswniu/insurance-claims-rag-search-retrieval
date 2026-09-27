import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TableBox } from "@/components/TableBox";

function renderBox(tableWidth: number, boxWidth: number) {
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe = vi.fn();
      disconnect = vi.fn();
    },
  );
  vi.spyOn(HTMLElement.prototype, "scrollWidth", "get").mockReturnValue(tableWidth);
  vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(boxWidth);
  return render(
    <TableBox label="Rows">
      <table>
        <tbody>
          <tr>
            <td>4108452.79</td>
          </tr>
        </tbody>
      </table>
    </TableBox>,
  );
}

describe("a table's box", () => {
  it("takes the focus as a named region while its table scrolls sideways", () => {
    renderBox(820, 358);
    expect(screen.getByRole("region", { name: "Rows" })).toHaveAttribute("tabindex", "0");
  });

  it("is only a box while the table fits", () => {
    const { container } = renderBox(300, 358);
    expect(screen.queryByRole("region")).toBeNull();
    expect(container.querySelector(".table-wrap")).not.toHaveAttribute("tabindex");
  });
});
