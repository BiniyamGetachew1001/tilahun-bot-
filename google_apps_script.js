function doGet(e) {
  return ContentService.createTextOutput("OK");
}

function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var action = data.action;

    if (action === "ADD_REPORT") {
      var sh = getOrCreateSheet(ss, "Reports", [
        "Report ID", "Timestamp", "Shift", "Project Name", "Worker Name", "Role", "Work Completed", "Plan / Handover", "Blockers"
      ]);
      var d = data.data;
      sh.appendRow([d.id, d.timestamp, d.shift, d.project, d.worker_name, d.role, d.completed, d.plan, d.blockers]);
      styleTableSheet(sh, "#059669");
    }
    
    if (action === "ADD_MATERIAL") {
      var sh = getOrCreateSheet(ss, "MaterialRequests", [
        "MR Code", "Timestamp", "Project Name", "Worker Name", "Role", "Items Description", "Urgency", "Status", "Approved By", "Last Updated"
      ]);
      var d = data.data;
      sh.appendRow([d.mr_code, d.timestamp, d.project, d.worker_name, d.role, d.items, d.urgency, d.status, "", d.timestamp]);
      styleTableSheet(sh, "#D97706");
    }

    if (action === "UPDATE_MATERIAL") {
      var sh = ss.getSheetByName("MaterialRequests");
      if (sh) {
        var values = sh.getDataRange().getValues();
        for (var i = 1; i < values.length; i++) {
          if (values[i][0] === data.mr_code) {
            sh.getRange(i + 1, 8).setValue(data.status);
            sh.getRange(i + 1, 9).setValue(data.approved_by || "");
            sh.getRange(i + 1, 10).setValue(new Date().toISOString().replace('T', ' ').substr(0, 19));
            break;
          }
        }
      }
    }

    if (action === "FULL_SYNC") {
      saveTable(ss, "Projects", data.projects, [
        "Project Name", "Progress (%)", "Visual Progress", "Target Deadline", "Topic ID", "Status", "Created Date"
      ], "#2563EB");

      saveTable(ss, "Reports", data.reports, [
        "ID", "Timestamp", "Shift", "Project Name", "Worker Name", "Role", "Work Completed", "Plan / Handover", "Blockers"
      ], "#059669");

      saveTable(ss, "MaterialRequests", data.materials, [
        "MR Code", "Timestamp", "Project Name", "Worker Name", "Role", "Items Description", "Urgency", "Status", "Approved By", "Last Updated"
      ], "#D97706");

      saveTable(ss, "Issues", data.issues || [], [
        "Issue ID", "Timestamp", "Project Name", "Worker Name", "Description", "Severity", "Status", "Resolved At"
      ], "#E11D48");

      saveTable(ss, "Workers", data.workers, [
        "Telegram User ID", "Full Name", "Role", "Approved", "Admin Access", "Registration Date"
      ], "#7C3AED");

      createExecutiveDashboard(ss);
      
      var defaultSheet = ss.getSheetByName("Sheet1");
      if (defaultSheet && ss.getSheets().length > 1) {
        try { ss.deleteSheet(defaultSheet); } catch(e) {}
      }
    }

    return ContentService.createTextOutput("SUCCESS");
  } catch (err) {
    return ContentService.createTextOutput("ERROR: " + err.toString());
  }
}

function saveTable(ss, name, rows, customHeaders, tabColor) {
  var sh = getOrCreateSheet(ss, name);
  sh.clear();
  sh.setTabColor(tabColor);

  if (!rows || rows.length === 0) {
    sh.appendRow(customHeaders);
    styleTableSheet(sh, tabColor);
    return;
  }

  var rawKeys = Object.keys(rows[0]);
  var headers = customHeaders || rawKeys;
  sh.appendRow(headers);

  var allRows = [];
  for (var i = 0; i < rows.length; i++) {
    var r = rows[i];
    var rowVals = [];
    
    if (name === "Projects") {
      var pct = Number(r.progress_percent || 0);
      var sparklineFormula = '=IF(ISBLANK(B' + (i + 2) + '), "", SPARKLINE(B' + (i + 2) + ', {"charttype","bar"; "max",100; "color1", IF(B' + (i + 2) + '>=100, "#10B981", "#2563EB")}))';
      rowVals = [
        r.name || "",
        pct,
        sparklineFormula,
        r.deadline || "No deadline",
        r.topic_id || "",
        r.is_active ? "Active" : "Inactive",
        r.created_at || ""
      ];
    } else {
      for (var k = 0; k < rawKeys.length; k++) {
        var v = r[rawKeys[k]];
        rowVals.push(v != null ? v : "");
      }
    }
    allRows.push(rowVals);
  }

  if (allRows.length > 0) {
    sh.getRange(2, 1, allRows.length, allRows[0].length).setValues(allRows);
  }

  styleTableSheet(sh, tabColor);
}

function styleTableSheet(sh, tabColor) {
  var lastRow = Math.max(sh.getLastRow(), 1);
  var lastCol = Math.max(sh.getLastColumn(), 1);

  sh.setFrozenRows(1);

  var headerRange = sh.getRange(1, 1, 1, lastCol);
  headerRange.setBackground("#0F172A")
             .setFontColor("#FFFFFF")
             .setFontWeight("bold")
             .setFontFamily("Inter")
             .setFontSize(10)
             .setHorizontalAlignment("center")
             .setVerticalAlignment("middle");
  sh.setRowHeight(1, 38);

  if (lastRow > 1) {
    var dataRange = sh.getRange(2, 1, lastRow - 1, lastCol);
    dataRange.setFontFamily("Inter")
             .setFontSize(10)
             .setVerticalAlignment("middle");

    for (var r = 2; r <= lastRow; r++) {
      var rowRange = sh.getRange(r, 1, 1, lastCol);
      sh.setRowHeight(r, 28);
      if (r % 2 === 0) {
        rowRange.setBackground("#FFFFFF");
      } else {
        rowRange.setBackground("#F8FAFC");
      }
    }

    dataRange.setBorder(true, true, true, true, true, true, "#E2E8F0", SpreadsheetApp.BorderStyle.SOLID);
  }

  for (var c = 1; c <= lastCol; c++) {
    sh.autoResizeColumn(c);
    var colWidth = sh.getColumnWidth(c);
    if (colWidth < 110) {
      sh.setColumnWidth(c, 120);
    } else if (colWidth > 350) {
      sh.setColumnWidth(c, 350);
    }
  }

  applyBadgesFormatting(sh);
}

function applyBadgesFormatting(sh) {
  var rules = [];
  var lastRow = Math.max(sh.getLastRow(), 2);
  var lastCol = Math.max(sh.getLastColumn(), 1);
  var range = sh.getRange(2, 1, lastRow - 1, lastCol);

  rules.push(SpreadsheetApp.newConditionalFormatRule()
    .whenTextEqualTo("APPROVED")
    .setBackground("#DCFCE7").setFontColor("#15803D").setBold(true)
    .setRanges([range]).build());
  rules.push(SpreadsheetApp.newConditionalFormatRule()
    .whenTextEqualTo("Active")
    .setBackground("#DCFCE7").setFontColor("#15803D").setBold(true)
    .setRanges([range]).build());

  rules.push(SpreadsheetApp.newConditionalFormatRule()
    .whenTextEqualTo("PENDING")
    .setBackground("#FEF3C7").setFontColor("#B45309").setBold(true)
    .setRanges([range]).build());

  rules.push(SpreadsheetApp.newConditionalFormatRule()
    .whenTextEqualTo("REJECTED")
    .setBackground("#FEE2E2").setFontColor("#B91C1C").setBold(true)
    .setRanges([range]).build());
  rules.push(SpreadsheetApp.newConditionalFormatRule()
    .whenTextEqualTo("URGENT")
    .setBackground("#FEE2E2").setFontColor("#B91C1C").setBold(true)
    .setRanges([range]).build());

  rules.push(SpreadsheetApp.newConditionalFormatRule()
    .whenTextEqualTo("IN_TRANSIT")
    .setBackground("#DBEAFE").setFontColor("#1D4ED8").setBold(true)
    .setRanges([range]).build());

  rules.push(SpreadsheetApp.newConditionalFormatRule()
    .whenTextEqualTo("DAY")
    .setBackground("#FEF9C3").setFontColor("#A16207").setBold(true)
    .setRanges([range]).build());
  rules.push(SpreadsheetApp.newConditionalFormatRule()
    .whenTextEqualTo("NIGHT")
    .setBackground("#E0E7FF").setFontColor("#4338CA").setBold(true)
    .setRanges([range]).build());

  sh.setConditionalFormatRules(rules);
}

function createExecutiveDashboard(ss) {
  var dash = getOrCreateSheet(ss, "Executive Dashboard");
  dash.clear();
  dash.setTabColor("#0F172A");

  ss.setActiveSheet(dash);
  ss.moveActiveSheet(1);

  dash.getRange("A1:F2").merge()
      .setValue("TILAHUN ENGINEERING - SITE OPERATIONS EXECUTIVE DASHBOARD")
      .setBackground("#0F172A")
      .setFontColor("#FFFFFF")
      .setFontFamily("Inter")
      .setFontSize(13)
      .setFontWeight("bold")
      .setHorizontalAlignment("center")
      .setVerticalAlignment("middle");
  dash.setRowHeight(1, 28);
  dash.setRowHeight(2, 28);

  var nowStr = Utilities.formatDate(new Date(), "GMT+3", "yyyy-MM-dd HH:mm:ss");
  dash.getRange("A3:F3").merge()
      .setValue("Live Sync Status: Online  |  Last Synced: " + nowStr + " (EAT)")
      .setBackground("#1E293B")
      .setFontColor("#94A3B8")
      .setFontFamily("Inter")
      .setFontSize(9)
      .setHorizontalAlignment("center")
      .setVerticalAlignment("middle");
  dash.setRowHeight(3, 22);

  var kpis = [
    { cellTitle: "A5:A6", cellVal: "A7:A8", title: "ACTIVE PROJECTS", formula: '=IFERROR(COUNTA(Projects!A2:A), 0)', bg: "#EFF6FF", border: "#3B82F6" },
    { cellTitle: "B5:B6", cellVal: "B7:B8", title: "TOTAL REPORTS", formula: '=IFERROR(COUNTA(Reports!A2:A), 0)', bg: "#ECFDF5", border: "#10B981" },
    { cellTitle: "C5:C6", cellVal: "C7:C8", title: "PENDING REQUISITIONS", formula: '=IFERROR(COUNTIF(MaterialRequests!H2:H, "PENDING"), 0)', bg: "#FFFBEB", border: "#F59E0B" },
    { cellTitle: "D5:D6", cellVal: "D7:D8", title: "ACTIVE ISSUES", formula: '=IFERROR(COUNTIF(Issues!G2:G, "OPEN"), 0)', bg: "#FFF1F2", border: "#F43F5E" },
    { cellTitle: "E5:F6", cellVal: "E7:F8", title: "SITE WORKFORCE", formula: '=IFERROR(COUNTA(Workers!A2:A), 0)', bg: "#FAF5FF", border: "#8B5CF6" }
  ];

  for (var i = 0; i < kpis.length; i++) {
    var k = kpis[i];
    dash.getRange(k.cellTitle).merge()
        .setValue(k.title)
        .setBackground(k.bg)
        .setFontColor("#334155")
        .setFontFamily("Inter")
        .setFontSize(9)
        .setFontWeight("bold")
        .setHorizontalAlignment("center")
        .setVerticalAlignment("middle");
    
    dash.getRange(k.cellVal).merge()
        .setValue(k.formula)
        .setBackground(k.bg)
        .setFontColor(k.border)
        .setFontFamily("Inter")
        .setFontSize(20)
        .setFontWeight("bold")
        .setHorizontalAlignment("center")
        .setVerticalAlignment("middle");
  }

  dash.setRowHeight(5, 18);
  dash.setRowHeight(6, 18);
  dash.setRowHeight(7, 24);
  dash.setRowHeight(8, 24);

  dash.getRange("A10:F10").merge()
      .setValue("PROJECT PROGRESS TRACKER")
      .setBackground("#1E293B")
      .setFontColor("#FFFFFF")
      .setFontFamily("Inter")
      .setFontSize(10)
      .setFontWeight("bold")
      .setHorizontalAlignment("left")
      .setVerticalAlignment("middle");
  dash.setRowHeight(10, 30);

  var tableHeaders = ["Project Name", "Completion (%)", "Visual Progress Bar", "Target Deadline", "Topic ID", "Status"];
  dash.getRange("A11:F11").setValues([tableHeaders])
      .setBackground("#0F172A")
      .setFontColor("#FFFFFF")
      .setFontFamily("Inter")
      .setFontSize(9)
      .setFontWeight("bold")
      .setHorizontalAlignment("center")
      .setVerticalAlignment("middle");
  dash.setRowHeight(11, 28);

  for (var r = 1; r <= 8; r++) {
    var rowIdx = 11 + r;
    dash.setRowHeight(rowIdx, 26);
    dash.getRange("A" + rowIdx).setValue('=IFERROR(Projects!A' + (r + 1) + ', "")');
    dash.getRange("B" + rowIdx).setValue('=IFERROR(Projects!B' + (r + 1) + ', "")').setHorizontalAlignment("center");
    dash.getRange("C" + rowIdx).setValue('=IF(ISBLANK(A' + rowIdx + '), "", SPARKLINE(B' + rowIdx + ', {"charttype","bar"; "max",100; "color1", IF(B' + rowIdx + '>=100, "#10B981", "#2563EB")}))');
    dash.getRange("D" + rowIdx).setValue('=IFERROR(Projects!D' + (r + 1) + ', "")').setHorizontalAlignment("center");
    dash.getRange("E" + rowIdx).setValue('=IFERROR(Projects!E' + (r + 1) + ', "")').setHorizontalAlignment("center");
    dash.getRange("F" + rowIdx).setValue('=IFERROR(Projects!F' + (r + 1) + ', "")').setHorizontalAlignment("center");

    var rowRange = dash.getRange("A" + rowIdx + ":F" + rowIdx);
    rowRange.setFontFamily("Inter").setFontSize(9).setVerticalAlignment("middle");
    if (r % 2 === 0) {
      rowRange.setBackground("#F8FAFC");
    } else {
      rowRange.setBackground("#FFFFFF");
    }
  }

  dash.getRange("A11:F19").setBorder(true, true, true, true, true, true, "#CBD5E1", SpreadsheetApp.BorderStyle.SOLID);

  dash.setColumnWidth(1, 190);
  dash.setColumnWidth(2, 110);
  dash.setColumnWidth(3, 220);
  dash.setColumnWidth(4, 150);
  dash.setColumnWidth(5, 100);
  dash.setColumnWidth(6, 120);

  applyBadgesFormatting(dash);
}

function getOrCreateSheet(ss, sheetName) {
  var sheet = ss.getSheetByName(sheetName);
  if (!sheet) {
    sheet = ss.insertSheet(sheetName);
  }
  return sheet;
}
