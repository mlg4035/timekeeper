from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .db import ActivityRow, ActivityStore, now_local


def generate_today_report(
    store: ActivityStore,
    reports_dir: Path,
    task_assignments: dict[str, str] | None = None,
    api_base_url: str = "http://127.0.0.1:8765",
) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    now = now_local()
    date_local = now.date().isoformat()
    stamp = now.strftime("%Y%m%d_%H%M%S")
    initial_rows = [_row_to_dict(row) for row in store.get_entries_for_date(date_local)]
    available_dates = store.get_available_dates()
    html_path = reports_dir / f"report_{date_local}_{stamp}.html"
    _write_html(
        html_path,
        date_local,
        generated_at=now,
        task_assignments=task_assignments or {},
        api_base_url=api_base_url,
        initial_rows=initial_rows,
        available_dates=available_dates,
    )
    return html_path


def _write_html(
    path: Path,
    date_local: str,
    generated_at: datetime,
    task_assignments: dict[str, str],
    api_base_url: str,
    initial_rows: list[dict[str, str | int]],
    available_dates: list[str],
) -> None:
    task_assignments_json = json.dumps(task_assignments)
    api_base_url_json = json.dumps(api_base_url)
    initial_rows_json = json.dumps(initial_rows)
    available_dates_json = json.dumps(available_dates)
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TimeKeeper Daily Report - {date_local}</title>
  <style>
    body {{
      font-family: Arial, sans-serif;
      margin: 20px;
      color: #1f2937;
    }}
    h1, h2 {{
      margin-bottom: 10px;
    }}
    .meta {{
      color: #4b5563;
      margin-bottom: 14px;
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
      margin-bottom: 26px;
    }}
    th, td {{
      border: 1px solid #d1d5db;
      text-align: left;
      padding: 8px;
      font-size: 13px;
      vertical-align: top;
    }}
    th {{
      background: #f3f4f6;
    }}
    th.sortable {{
      cursor: pointer;
      user-select: none;
      position: relative;
      padding-right: 20px;
    }}
    th.sortable::after {{
      content: "↕";
      position: absolute;
      right: 6px;
      color: #9ca3af;
      font-size: 11px;
    }}
    th.sorted-asc::after {{
      content: "▲";
      color: #111827;
    }}
    th.sorted-desc::after {{
      content: "▼";
      color: #111827;
    }}
    tr.unassigned-row td {{
      background: #fef3c7;
    }}
    tr.assigned-row td {{
      background: #ecfeff;
    }}
    tr.unassigned-row td:last-child {{
      font-weight: 600;
      color: #92400e;
    }}
    tr.filtered-out {{
      display: none;
    }}
    tr.filtered-in td {{
      outline: 2px solid #0f766e;
      outline-offset: -2px;
    }}
    .legend-item {{
      cursor: pointer;
    }}
    .legend-item text {{
      fill: #111827;
      font-size: 11px;
    }}
    .legend-item.active text {{
      font-weight: 700;
      fill: #0f766e;
    }}
    .small {{
      font-size: 12px;
      color: #6b7280;
    }}
    .task-section {{
      display: flex;
      gap: 16px;
      align-items: flex-start;
      margin-bottom: 26px;
    }}
    .task-table-wrap {{
      flex: 0 0 44%;
      min-width: 360px;
    }}
    .task-chart-wrap {{
      flex: 1;
      min-width: 360px;
      border: 1px solid #d1d5db;
      border-radius: 8px;
      padding: 10px;
      background: #ffffff;
    }}
    #taskPieChart {{
      width: 100%;
      height: auto;
      max-height: 420px;
      display: block;
    }}
    .slice-label {{
      font-size: 12px;
      font-weight: 600;
      fill: #111827;
      paint-order: stroke;
      stroke: #ffffff;
      stroke-width: 3px;
      pointer-events: none;
    }}
  </style>
</head>
<body>
  <h1>TimeKeeper Daily Report</h1>
  <div class="meta">Date: <span id="reportDate">{date_local}</span> | Generated: {generated_at.isoformat()}</div>
  <div style="margin-bottom: 12px;">
    <label for="dateSelect">View date:</label>
    <select id="dateSelect"></select>
    <button id="loadDateButton">Load Selected Date</button>
    <button id="refreshButton">Refresh</button>
  </div>
  <div class="meta" id="saveStatus"></div>

  <h2>Chronological Entries</h2>
  <table id="chronological">
    <thead>
      <tr>
        <th data-sort="date">Timestamp</th>
        <th data-sort="text">Status</th>
        <th data-sort="text">Source Type</th>
        <th data-sort="text">Process</th>
        <th data-sort="text">Window Title</th>
        <th data-sort="text">Task</th>
        <th data-sort="number">Interval (min)</th>
      </tr>
    </thead>
    <tbody></tbody>
  </table>

  <h2>Totals by Task</h2>
  <div class="task-section">
    <div class="task-table-wrap">
      <table id="totalsByTask">
        <thead>
          <tr>
            <th data-sort="text">Task</th>
            <th data-sort="number">Estimated Minutes</th>
            <th data-sort="number">Entries</th>
          </tr>
        </thead>
        <tbody></tbody>
      </table>
    </div>
    <div class="task-chart-wrap">
      <svg id="taskPieChart" viewBox="0 0 520 380" role="img" aria-label="Task minutes pie chart"></svg>
    </div>
  </div>

  <h2>Totals by App and Window</h2>
  <table id="totals">
    <thead>
      <tr>
        <th data-sort="text">Process</th>
        <th data-sort="text">Window Title</th>
        <th data-sort="text">Status</th>
        <th data-sort="text">Source Type</th>
        <th data-sort="text">Task</th>
        <th data-sort="number">Estimated Minutes</th>
      </tr>
    </thead>
    <tbody></tbody>
  </table>

  <script>
    const API_BASE_URL = {api_base_url_json};
    const INITIAL_DATE = "{date_local}";
    const taskAssignments = {task_assignments_json};
    const EMBEDDED_INITIAL_ROWS = {initial_rows_json};
    const EMBEDDED_AVAILABLE_DATES = {available_dates_json};
    let reportRows = [];
    let activeTaskFilter = null;

    async function loadAssignmentsFromApi() {{
      if (!API_BASE_URL) {{
        return;
      }}
      try {{
        const response = await fetch(`${{API_BASE_URL}}/task-assignments`);
        if (!response.ok) {{
          return;
        }}
        const payload = await response.json();
        const assignments = payload.assignments || {{}};
        Object.keys(assignments).forEach((key) => {{
          taskAssignments[key] = assignments[key];
        }});
      }} catch (_error) {{
        // Keep embedded assignments if API is unavailable.
      }}
    }}

    async function loadAvailableDatesFromApi() {{
      if (!API_BASE_URL) {{
        throw new Error("API unavailable");
      }}
      const response = await fetch(`${{API_BASE_URL}}/dates`);
      if (!response.ok) {{
        throw new Error("Could not load dates.");
      }}
      const payload = await response.json();
      const dates = payload.dates || [];
      return Array.isArray(dates) ? dates : [];
    }}

    async function loadRowsForDateFromApi(dateValue) {{
      if (!API_BASE_URL) {{
        throw new Error("API unavailable");
      }}
      const response = await fetch(`${{API_BASE_URL}}/activity?date=${{encodeURIComponent(dateValue)}}`);
      if (!response.ok) {{
        throw new Error("Could not load activity for selected date.");
      }}
      const payload = await response.json();
      const rows = payload.rows || [];
      return Array.isArray(rows) ? rows : [];
    }}

    function renderChronological(rows) {{
      const tbody = document.querySelector("#chronological tbody");
      tbody.innerHTML = "";
      rows.forEach((row) => {{
        const processName = String(row.process_name || "");
        const windowTitle = String(row.window_title || "");
        const task = getTaskForRow(processName, windowTitle);
        const canAssignTask = Boolean(processName.trim() || windowTitle.trim());
        const tr = document.createElement("tr");
        tr.appendChild(makeCell(row.timestamp_local));
        tr.appendChild(makeCell(row.status));
        tr.appendChild(makeCell(row.source_type));
        tr.appendChild(makeCell(processName));
        tr.appendChild(makeCell(windowTitle));
        tr.appendChild(
          canAssignTask
            ? makeTaskCell({{
                processName,
                windowTitle,
                task,
              }})
            : makeTaskUnavailableCell()
        );
        tr.appendChild(makeCell(String(row.interval_minutes)));
        tbody.appendChild(tr);
      }});
    }}

    function computeTaskTotals(rows) {{
      const taskTotals = new Map();
      rows.forEach((row) => {{
        const processName = String(row.process_name || "");
        const windowTitle = String(row.window_title || "");
        const task = getTaskForRow(processName, windowTitle);
        const current = taskTotals.get(task) || {{ minutes: 0, rowCount: 0 }};
        current.minutes += Number(row.interval_minutes || 0);
        current.rowCount += 1;
        taskTotals.set(task, current);
      }});
      return taskTotals;
    }}

    function computeAppWindowTotals(rows) {{
      const totals = new Map();
      rows.forEach((row) => {{
        const processName = String(row.process_name || "");
        const windowTitle = String(row.window_title || "");
        const key = assignmentKey(processName, windowTitle);
        const minutes = Number(row.interval_minutes || 0);
        const status = String(row.status || "");
        const sourceType = String(row.source_type || "");
        const current = totals.get(key);
        if (!current) {{
          totals.set(key, {{
            processName,
            windowTitle,
            status,
            sourceType,
            minutes,
          }});
          return;
        }}
        current.minutes += minutes;
        if (current.status !== status || current.sourceType !== sourceType) {{
          current.status = "Various";
          current.sourceType = "Various";
        }}
      }});
      return [...totals.values()];
    }}

    function renderTotals(rows) {{
      const totalsRows = computeAppWindowTotals(rows).map((item) => ({{
        ...item,
        task: getTaskForRow(item.processName, item.windowTitle),
        minutes: Number(item.minutes || 0),
      }}));

      const tbody = document.querySelector("#totals tbody");
      if (!tbody) {{
        return;
      }}
      tbody.innerHTML = "";
      totalsRows
        .sort((a, b) => b.minutes - a.minutes)
        .forEach((item) => {{
          const tr = document.createElement("tr");
          tr.classList.add(item.task === "Unassigned" ? "unassigned-row" : "assigned-row");
          tr.dataset.task = item.task || "Unassigned";
          tr.appendChild(makeCell(item.processName));
          tr.appendChild(makeCell(item.windowTitle));
          tr.appendChild(makeCell(item.status));
          tr.appendChild(makeCell(item.sourceType));
          tr.appendChild(
            makeTaskCell({{
              processName: item.processName,
              windowTitle: item.windowTitle,
              task: item.task,
            }})
          );
          tr.appendChild(makeCell(String(item.minutes.toFixed(0))));
          tbody.appendChild(tr);
        }});

      applyTaskFilterToTotalsRows();
      renderTotalsByTask(rows);
    }}

    function renderTotalsByTask(rows) {{
      const taskTotals = computeTaskTotals(rows);

      const tbody = document.querySelector("#totalsByTask tbody");
      tbody.innerHTML = "";
      [...taskTotals.entries()]
        .sort((a, b) => b[1].minutes - a[1].minutes)
        .forEach(([task, values]) => {{
          const tr = document.createElement("tr");
          tr.appendChild(makeCell(task));
          tr.appendChild(makeCell(String(values.minutes.toFixed(0))));
          tr.appendChild(makeCell(String(values.rowCount)));
          tbody.appendChild(tr);
        }});

      renderTaskPieChart([...taskTotals.entries()]);
    }}

    function renderTaskPieChart(entries) {{
      const svg = document.getElementById("taskPieChart");
      if (!svg) {{
        return;
      }}
      svg.innerHTML = "";

      const chartEntries = entries
        .map(([task, values]) => ({{
          task,
          minutes: Number(values.minutes || 0),
        }}))
        .filter((item) => item.minutes > 0)
        .sort((a, b) => b.minutes - a.minutes);

      if (chartEntries.length === 0) {{
        const empty = document.createElementNS("http://www.w3.org/2000/svg", "text");
        empty.setAttribute("x", "260");
        empty.setAttribute("y", "190");
        empty.setAttribute("text-anchor", "middle");
        empty.setAttribute("fill", "#6b7280");
        empty.textContent = "No task data available";
        svg.appendChild(empty);
        return;
      }}

      const cx = 180;
      const cy = 190;
      const radius = 140;
      const totalMinutes = chartEntries.reduce((sum, item) => sum + item.minutes, 0);
      const palette = [
        "#2563eb", "#14b8a6", "#f59e0b", "#8b5cf6", "#ef4444",
        "#06b6d4", "#84cc16", "#f97316", "#ec4899", "#64748b"
      ];

      let startAngle = -Math.PI / 2;
      chartEntries.forEach((item, idx) => {{
        const fraction = item.minutes / totalMinutes;
        const angle = fraction * Math.PI * 2;
        const endAngle = startAngle + angle;
        const color = palette[idx % palette.length];

        const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        path.setAttribute("d", createSlicePath(cx, cy, radius, startAngle, endAngle));
        path.setAttribute("fill", color);
        path.setAttribute("stroke", "#ffffff");
        path.setAttribute("stroke-width", activeTaskFilter === item.task ? "3" : "2");
        if (activeTaskFilter && activeTaskFilter !== item.task) {{
          path.setAttribute("opacity", "0.3");
        }}
        path.setAttribute("title", `${{item.task}}: ${{Math.round(item.minutes)}} min`);
        svg.appendChild(path);

        if (fraction >= 0.04 || activeTaskFilter === item.task) {{
          const mid = (startAngle + endAngle) / 2;
          const labelRadius = radius * 0.62;
          const lx = cx + Math.cos(mid) * labelRadius;
          const ly = cy + Math.sin(mid) * labelRadius;
          const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
          label.setAttribute("x", String(lx));
          label.setAttribute("y", String(ly));
          label.setAttribute("text-anchor", "middle");
          label.setAttribute("dominant-baseline", "middle");
          label.setAttribute("class", "slice-label");
          if (activeTaskFilter && activeTaskFilter !== item.task) {{
            label.setAttribute("opacity", "0.35");
          }}
          label.textContent = `${{Math.round(item.minutes)}}m`;
          svg.appendChild(label);
        }}

        startAngle = endAngle;
      }});

      renderPieLegend(svg, chartEntries, palette);
    }}

    function renderPieLegend(svg, entries, palette) {{
      const startX = 340;
      let y = 38;
      entries.slice(0, 12).forEach((item, idx) => {{
        const color = palette[idx % palette.length];
        const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
        group.setAttribute("class", "legend-item");
        if (activeTaskFilter && activeTaskFilter === item.task) {{
          group.classList.add("active");
        }}
        group.addEventListener("click", () => toggleTaskFilter(item.task));

        const swatch = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        swatch.setAttribute("x", String(startX));
        swatch.setAttribute("y", String(y - 10));
        swatch.setAttribute("width", "12");
        swatch.setAttribute("height", "12");
        swatch.setAttribute("fill", color);
        group.appendChild(swatch);

        const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
        text.setAttribute("x", String(startX + 18));
        text.setAttribute("y", String(y));
        text.textContent = `${{item.task}} (${{Math.round(item.minutes)}}m)`;
        group.appendChild(text);
        svg.appendChild(group);
        y += 22;
      }});
    }}

    function createSlicePath(cx, cy, r, startAngle, endAngle) {{
      const x1 = cx + r * Math.cos(startAngle);
      const y1 = cy + r * Math.sin(startAngle);
      const x2 = cx + r * Math.cos(endAngle);
      const y2 = cy + r * Math.sin(endAngle);
      const largeArc = endAngle - startAngle > Math.PI ? 1 : 0;
      return [
        `M ${{cx}} ${{cy}}`,
        `L ${{x1}} ${{y1}}`,
        `A ${{r}} ${{r}} 0 ${{largeArc}} 1 ${{x2}} ${{y2}}`,
        "Z"
      ].join(" ");
    }}

    function makeCell(value) {{
      const td = document.createElement("td");
      td.textContent = String(value ?? "");
      return td;
    }}

    function makeTaskCell(item) {{
      const td = document.createElement("td");
      const select = document.createElement("select");
      getTaskOptions(item.task).forEach((taskName) => {{
        const option = document.createElement("option");
        option.value = taskName;
        option.textContent = taskName;
        if (taskName === item.task) {{
          option.selected = true;
        }}
        select.appendChild(option);
      }});

      const newTaskOption = document.createElement("option");
      newTaskOption.value = "__new__";
      newTaskOption.textContent = "New task...";
      select.appendChild(newTaskOption);

      select.addEventListener("change", async () => {{
        let selectedTask = select.value;
        if (selectedTask === "__new__") {{
          const createdTask = prompt("Enter new task name:");
          if (!createdTask || !createdTask.trim()) {{
            select.value = item.task;
            return;
          }}
          selectedTask = createdTask.trim();
        }}
        await applyTaskChange(item, selectedTask);
      }});

      td.appendChild(select);
      return td;
    }}

    function makeTaskUnavailableCell() {{
      const td = document.createElement("td");
      td.textContent = "N/A";
      td.classList.add("small");
      return td;
    }}

    async function applyTaskChange(item, taskName) {{
      item.task = taskName;
      setTaskForRow(item.processName, item.windowTitle, taskName);
      const result = await saveTaskAssignment(item.processName, item.windowTitle, taskName);
      if (!result.ok) {{
        setSaveStatus(`Could not save task assignment: ${{result.error}}`, true);
      }} else {{
        setSaveStatus("Task assignment saved.", false);
      }}
      await renderRows(reportRows, selectedDate());
      initSortableTable("totals");
      initSortableTable("totalsByTask");
      initSortableTable("chronological");
    }}

    async function saveTaskAssignment(processName, windowTitle, taskName) {{
      if (!API_BASE_URL) {{
        return {{ ok: false, error: "API unavailable" }};
      }}
      try {{
        const response = await fetch(`${{API_BASE_URL}}/task-assignments`, {{
          method: "POST",
          headers: {{
            "Content-Type": "application/json",
          }},
          body: JSON.stringify({{
            process_name: processName,
            window_title: windowTitle,
            task_name: taskName,
          }}),
        }});
        if (!response.ok) {{
          let message = `HTTP ${{response.status}}`;
          try {{
            const payload = await response.json();
            if (payload && payload.error) {{
              message = payload.error;
            }}
          }} catch (_parseError) {{
            // Keep default message.
          }}
          return {{ ok: false, error: message }};
        }}
        return {{ ok: true, error: "" }};
      }} catch (error) {{
        const message = error && error.message ? error.message : "Network request failed";
        return {{ ok: false, error: message }};
      }}
    }}

    function getTaskOptions(currentTask) {{
      const unique = new Set(["Unassigned"]);
      Object.values(taskAssignments).forEach((name) => {{
        if (name) {{
          unique.add(name);
        }}
      }});
      if (currentTask) {{
        unique.add(currentTask);
      }}
      return [...unique].sort((a, b) => a.localeCompare(b, undefined, {{ sensitivity: "base" }}));
    }}

    function getTaskForRow(processName, windowTitle) {{
      const key = assignmentKey(processName, windowTitle);
      return taskAssignments[key] || "Unassigned";
    }}

    function setTaskForRow(processName, windowTitle, taskName) {{
      const key = assignmentKey(processName, windowTitle);
      if (!taskName || taskName === "Unassigned") {{
        delete taskAssignments[key];
        return;
      }}
      taskAssignments[key] = taskName;
    }}

    function assignmentKey(processName, windowTitle) {{
      return `${{processName}}\\t${{windowTitle}}`;
    }}

    function setSaveStatus(message, isError) {{
      const status = document.getElementById("saveStatus");
      if (!status) {{
        return;
      }}
      status.textContent = message;
      status.style.color = isError ? "#b91c1c" : "#065f46";
    }}

    function toggleTaskFilter(taskName) {{
      activeTaskFilter = activeTaskFilter === taskName ? null : taskName;
      applyTaskFilterToTotalsRows();
      renderTotalsByTask(reportRows);
    }}

    function applyTaskFilterToTotalsRows() {{
      const rows = document.querySelectorAll("#totals tbody tr");
      rows.forEach((row) => {{
        row.classList.remove("filtered-in", "filtered-out");
        if (!activeTaskFilter) {{
          return;
        }}
        const rowTask = row.dataset.task || "Unassigned";
        if (rowTask === activeTaskFilter) {{
          row.classList.add("filtered-in");
        }} else {{
          row.classList.add("filtered-out");
        }}
      }});
    }}

    function populateDateSelect(dates) {{
      const select = document.getElementById("dateSelect");
      if (!select) {{
        return;
      }}
      const uniqueDates = [...new Set([INITIAL_DATE, ...dates])].sort().reverse();
      select.innerHTML = "";
      uniqueDates.forEach((dateValue) => {{
        const option = document.createElement("option");
        option.value = dateValue;
        option.textContent = dateValue;
        if (dateValue === INITIAL_DATE) {{
          option.selected = true;
        }}
        select.appendChild(option);
      }});
    }}

    function selectedDate() {{
      const select = document.getElementById("dateSelect");
      if (!select || !select.value) {{
        return INITIAL_DATE;
      }}
      return select.value;
    }}

    function setDisplayedDate(dateValue) {{
      const dateNode = document.getElementById("reportDate");
      if (dateNode) {{
        dateNode.textContent = dateValue;
      }}
      document.title = `TimeKeeper Daily Report - ${{dateValue}}`;
    }}

    function escapeHtml(value) {{
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }}

    function resetTableSortState(tableId) {{
      const table = document.getElementById(tableId);
      if (!table) {{
        return;
      }}
      delete table.dataset.sortIndex;
      delete table.dataset.sortDir;
      table.querySelectorAll("thead th").forEach((header) => {{
        header.classList.remove("sorted-asc", "sorted-desc");
      }});
    }}

    function initSortableTable(tableId) {{
      const table = document.getElementById(tableId);
      if (!table || table.dataset.sortInit === "1") {{
        return;
      }}
      const headers = table.querySelectorAll("thead th");
      headers.forEach((header, index) => {{
        header.classList.add("sortable");
        header.addEventListener("click", () => {{
          const sortType = header.dataset.sort || "text";
          sortTable(table, index, sortType);
        }});
      }});
      table.dataset.sortInit = "1";
    }}

    function sortTable(table, columnIndex, sortType) {{
      const tbody = table.querySelector("tbody");
      if (!tbody) {{
        return;
      }}
      const rows = [...tbody.querySelectorAll("tr")];
      const previousIndex = Number(table.dataset.sortIndex || -1);
      const previousDir = table.dataset.sortDir || "asc";
      const direction = previousIndex === columnIndex && previousDir === "asc" ? "desc" : "asc";

      rows.sort((a, b) => compareCells(a, b, columnIndex, sortType, direction));
      rows.forEach((row) => tbody.appendChild(row));

      table.dataset.sortIndex = String(columnIndex);
      table.dataset.sortDir = direction;
      updateSortIndicators(table, columnIndex, direction);
    }}

    function compareCells(rowA, rowB, columnIndex, sortType, direction) {{
      const a = (rowA.children[columnIndex]?.textContent || "").trim();
      const b = (rowB.children[columnIndex]?.textContent || "").trim();
      let result = 0;
      if (sortType === "number") {{
        const aNum = Number(a);
        const bNum = Number(b);
        result = (isNaN(aNum) ? 0 : aNum) - (isNaN(bNum) ? 0 : bNum);
      }} else if (sortType === "date") {{
        const aDate = Date.parse(a);
        const bDate = Date.parse(b);
        result = (isNaN(aDate) ? 0 : aDate) - (isNaN(bDate) ? 0 : bDate);
      }} else {{
        result = a.localeCompare(b, undefined, {{ sensitivity: "base" }});
      }}
      return direction === "asc" ? result : -result;
    }}

    function updateSortIndicators(table, columnIndex, direction) {{
      table.querySelectorAll("thead th").forEach((header, index) => {{
        header.classList.remove("sorted-asc", "sorted-desc");
        if (index === columnIndex) {{
          header.classList.add(direction === "asc" ? "sorted-asc" : "sorted-desc");
        }}
      }});
    }}

    async function renderRows(rows, dateValue) {{
      const filteredRows = rows.filter((row) => !isIgnoredSystemRow(row));
      reportRows = filteredRows;
      activeTaskFilter = null;
      renderTotals(filteredRows);
      renderChronological(filteredRows);
      resetTableSortState("totals");
      resetTableSortState("totalsByTask");
      resetTableSortState("chronological");
      initSortableTable("totals");
      initSortableTable("totalsByTask");
      initSortableTable("chronological");
      setDisplayedDate(dateValue);
    }}

    function isIgnoredSystemRow(row) {{
      const sourceType = String(row.source_type || "").toLowerCase();
      const status = String(row.status || "").toUpperCase();
      const process = String(row.process_name || "").trim();
      const title = String(row.window_title || "").trim();
      if (sourceType === "system") {{
        return true;
      }}
      if (status === "LOCKED" || status === "IDLE") {{
        return true;
      }}
      if (!process && !title) {{
        return true;
      }}
      return false;
    }}

    document.getElementById("loadDateButton").addEventListener("click", async () => {{
      const dateValue = selectedDate();
      try {{
        const rows = await loadRowsForDateFromApi(dateValue);
        await renderRows(rows, dateValue);
        setSaveStatus(`Loaded data for ${{dateValue}}.`, false);
      }} catch (_error) {{
        setSaveStatus("Could not load selected date. Keep TimeKeeper running.", true);
      }}
    }});

    document.getElementById("refreshButton").addEventListener("click", async () => {{
      const refreshButton = document.getElementById("refreshButton");
      const dateValue = selectedDate();
      if (refreshButton) {{
        refreshButton.disabled = true;
      }}
      try {{
        await loadAssignmentsFromApi();
        const dates = await loadAvailableDatesFromApi();
        populateDateSelect(dates);
        const select = document.getElementById("dateSelect");
        if (select) {{
          select.value = dateValue;
        }}
        const rows = await loadRowsForDateFromApi(dateValue);
        await renderRows(rows, dateValue);
        setSaveStatus(`Refreshed data for ${{dateValue}}.`, false);
      }} catch (_error) {{
        setSaveStatus("Could not refresh. Keep TimeKeeper running.", true);
      }} finally {{
        if (refreshButton) {{
          refreshButton.disabled = false;
        }}
      }}
    }});

    (async () => {{
      try {{
        await loadAssignmentsFromApi();
        const dates = await loadAvailableDatesFromApi();
        populateDateSelect(dates);
        const initialRows = await loadRowsForDateFromApi(INITIAL_DATE);
        await renderRows(initialRows, INITIAL_DATE);
      }} catch (_error) {{
        populateDateSelect(EMBEDDED_AVAILABLE_DATES);
        await renderRows(EMBEDDED_INITIAL_ROWS, INITIAL_DATE);
        setSaveStatus(
          "Loaded embedded snapshot. Keep TimeKeeper running for live date switching and task-save sync.",
          true
        );
      }}
    }})();
  </script>
</body>
</html>
"""
    with path.open("w", encoding="utf-8") as file:
        file.write(html)


def _row_to_dict(row: ActivityRow) -> dict[str, str | int]:
    return {
        "timestamp_local": row.timestamp_local,
        "date_local": row.date_local,
        "status": row.status,
        "source_type": row.source_type,
        "window_title": row.window_title,
        "process_name": row.process_name,
        "url": row.url,
        "domain": row.domain,
        "interval_minutes": row.interval_minutes,
    }
